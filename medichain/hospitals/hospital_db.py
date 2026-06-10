import uuid

from django.conf import settings
from django.core.management import call_command
from django.db import connections
from django.db.utils import OperationalError


def _is_postgresql():
    engine = settings.DATABASES['default']['ENGINE']
    return 'postgresql' in engine


def get_db_alias(hospital_id):
    """Return deterministic DB alias for a hospital UUID."""
    key = str(hospital_id).replace('-', '')[:8]
    return f"hospital_{key}"


def _get_db_name(hospital_id):
    key = str(hospital_id).replace('-', '')[:8]
    return f"medichain_h_{key}"


def register_db(hospital_id):
    """Register runtime DB config for one hospital if not already present."""
    # On PostgreSQL, everything uses the default DB
    if _is_postgresql():
        return 'default'

    alias = get_db_alias(hospital_id)
    if alias in settings.DATABASES:
        return alias

    default_db = settings.DATABASES['default'].copy()
    test_name = str(default_db.get('NAME') or '')
    if test_name.startswith('test_'):
        default_db['NAME'] = test_name
    else:
        default_db['NAME'] = _get_db_name(hospital_id)
    settings.DATABASES[alias] = default_db
    return alias


def create_hospital_database(hospital_id):
    """Create hospital-specific DB, register alias, and migrate hospital_local app."""
    # On PostgreSQL, migrations already ran during build — nothing to do
    if _is_postgresql():
        return 'default'

    default_name = str(connections['default'].settings_dict.get('NAME') or '')
    if default_name.startswith('test_'):
        return 'default'

    db_name = _get_db_name(hospital_id)
    alias = register_db(hospital_id)

    default_conn = connections['default']
    with default_conn.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")

    call_command('migrate', 'hospital_local', database=alias, interactive=False)
    return alias


def ensure_db_exists(hospital_id):
    """Ensure runtime registration exists and the physical DB is present."""
    # On PostgreSQL, always use default
    if _is_postgresql():
        return 'default'

    default_name = str(connections['default'].settings_dict.get('NAME') or '')
    if default_name.startswith('test_'):
        return 'default'

    alias = register_db(hospital_id)

    try:
        connections[alias].ensure_connection()
    except OperationalError as exc:
        # MySQL 1049 = Unknown database
        if exc.args and len(exc.args) >= 1 and exc.args[0] == 1049:
            return create_hospital_database(hospital_id)
        raise

    return alias