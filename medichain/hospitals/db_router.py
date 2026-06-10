import threading
from django.conf import settings
from .hospital_db import get_db_alias

_thread_local = threading.local()


def _is_postgresql():
    return 'postgresql' in settings.DATABASES['default']['ENGINE']


def set_hospital_db(hospital_id):
    _thread_local.hospital_id = str(hospital_id) if hospital_id else None


def get_hospital_db():
    return getattr(_thread_local, 'hospital_id', None)


def clear_hospital_db():
    if hasattr(_thread_local, 'hospital_id'):
        delattr(_thread_local, 'hospital_id')


class HospitalDBRouter:
    """Route hospital-local models to dynamic hospital_* databases (MySQL)
    or default database (PostgreSQL)."""

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'hospital_local':
            if _is_postgresql():
                return 'default'
            hospital_id = get_hospital_db()
            if not hospital_id:
                return None
            return get_db_alias(hospital_id)
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'hospital_local':
            if _is_postgresql():
                return 'default'
            hospital_id = get_hospital_db()
            if not hospital_id:
                return None
            return get_db_alias(hospital_id)
        return 'default'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'hospital_local':
            if _is_postgresql():
                return db == 'default'  # allow on default for PostgreSQL
            return db.startswith('hospital_')  # MySQL: per-hospital DBs only
        if db.startswith('hospital_'):
            return False
        return db == 'default'