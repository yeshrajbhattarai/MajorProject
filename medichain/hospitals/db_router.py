import threading

from .hospital_db import get_db_alias

_thread_local = threading.local()


def set_hospital_db(hospital_id):
    _thread_local.hospital_id = str(hospital_id) if hospital_id else None


def get_hospital_db():
    return getattr(_thread_local, 'hospital_id', None)


def clear_hospital_db():
    if hasattr(_thread_local, 'hospital_id'):
        delattr(_thread_local, 'hospital_id')


class HospitalDBRouter:
    """Route hospital-local models to dynamic hospital_* databases."""

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'hospital_local':
            hospital_id = get_hospital_db()
            if not hospital_id:
                return None
            return get_db_alias(hospital_id)
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'hospital_local':
            hospital_id = get_hospital_db()
            if not hospital_id:
                return None
            return get_db_alias(hospital_id)
        return 'default'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'hospital_local':
            return db.startswith('hospital_')
        if db.startswith('hospital_'):
            return False
        return db == 'default'
