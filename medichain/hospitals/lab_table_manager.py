import re
from collections import OrderedDict

from django.conf import settings
from django.db import connections
from types import SimpleNamespace


# ─── DB Detection ─────────────────────────────────────────────────────────────

def _is_postgresql(db_alias='default'):
    engine = settings.DATABASES.get(db_alias, settings.DATABASES['default'])['ENGINE']
    return 'postgresql' in engine


def _q(name, db_alias='default'):
    """Quote an identifier with backticks (MySQL) or double quotes (PostgreSQL)."""
    if _is_postgresql(db_alias):
        return f'"{name}"'
    return f'`{name}`'


# ─── Column Definitions ───────────────────────────────────────────────────────

def _col(mysql_def, db_alias='default'):
    """Translate a MySQL column definition to PostgreSQL if needed."""
    if not _is_postgresql(db_alias):
        return mysql_def
    result = mysql_def
    result = result.replace('LONGTEXT', 'TEXT')
    result = result.replace('TINYINT(1)', 'SMALLINT')
    result = result.replace('DATETIME', 'TIMESTAMP')
    # Remove MySQL-only ON UPDATE clause
    result = re.sub(r'\s+ON UPDATE CURRENT_TIMESTAMP', '', result)
    return result


DEFAULT_RECORD_COLUMNS = OrderedDict([
    ('row_id',          'CHAR(36) PRIMARY KEY'),
    ('record_id',       'CHAR(36) NOT NULL UNIQUE'),
    ('lab_request_id',  'CHAR(36) NOT NULL UNIQUE'),
    ('patient_id',      'CHAR(36) NOT NULL'),
    ('hospital_id',     'CHAR(36) NOT NULL'),
    ('recorded_by_id',  'CHAR(36) NOT NULL'),
    ('version',         'INT NOT NULL DEFAULT 1'),
    ('is_latest',       'TINYINT(1) NOT NULL DEFAULT 1'),
    ('sha256_hash',     'CHAR(64) NOT NULL'),
    ('created_at',      'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP'),
    ('updated_at',      'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
    ('diagnosis',       'LONGTEXT NOT NULL'),
    ('treatment_plan',  'LONGTEXT NOT NULL'),
    ('notes',           'LONGTEXT NULL'),
    ('chest_pain_type', 'VARCHAR(20) NOT NULL'),
    ('age',             'INT NOT NULL'),
    ('gender',          'VARCHAR(10) NOT NULL'),
])

DEFAULT_VERSION_COLUMNS = OrderedDict([
    ('version_row_id',  'CHAR(36) PRIMARY KEY'),
    ('record_id',       'CHAR(36) NOT NULL'),
    ('version_number',  'INT NOT NULL'),
    ('changed_by_id',   'CHAR(36) NOT NULL'),
    ('change_reason',   'LONGTEXT NULL'),
    ('changed_at',      'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP'),
    ('row_id',          'CHAR(36) NOT NULL'),
    ('lab_request_id',  'CHAR(36) NOT NULL'),
    ('patient_id',      'CHAR(36) NOT NULL'),
    ('hospital_id',     'CHAR(36) NOT NULL'),
    ('recorded_by_id',  'CHAR(36) NOT NULL'),
    ('version',         'INT NOT NULL'),
    ('is_latest',       'TINYINT(1) NOT NULL'),
    ('sha256_hash',     'CHAR(64) NOT NULL'),
    ('diagnosis',       'LONGTEXT NOT NULL'),
    ('treatment_plan',  'LONGTEXT NOT NULL'),
    ('notes',           'LONGTEXT NULL'),
    ('chest_pain_type', 'VARCHAR(20) NOT NULL'),
    ('age',             'INT NOT NULL'),
    ('gender',          'VARCHAR(10) NOT NULL'),
])


def slugify(value):
    return re.sub(r'[^a-z0-9]+', '_', (value or '').strip().lower()).strip('_')


def lab_record_table_name(lab_id):
    return f"lab_record_{str(lab_id).replace('-', '')[:12]}"


def lab_version_table_name(lab_id):
    return f"lab_record_version_{str(lab_id).replace('-', '')[:12]}"


def _column_sql_for_field(field, db_alias='default'):
    field_type = (field.get('type') or 'text').strip().lower()
    required = bool(field.get('required', False))
    null_sql = 'NOT NULL' if required else 'NULL'

    pg = _is_postgresql(db_alias)

    if field_type in {'text', 'textarea'}:
        return f'{"TEXT" if pg else "LONGTEXT"} {null_sql}'
    if field_type == 'integer':
        return f'INT {null_sql}'
    if field_type in {'number', 'decimal'}:
        return f'DECIMAL(18,6) {null_sql}'
    if field_type == 'date':
        return f'DATE {null_sql}'
    if field_type == 'choice':
        return f'VARCHAR(255) {null_sql}'
    if field_type == 'boolean':
        return f'{"SMALLINT" if pg else "TINYINT(1)"} {null_sql}'
    return f'{"TEXT" if pg else "LONGTEXT"} {null_sql}'


def build_lab_columns(lab, db_alias='default'):
    columns = OrderedDict()
    for name, definition in DEFAULT_RECORD_COLUMNS.items():
        columns[name] = _col(definition, db_alias)
    for field in lab.custom_field_schema or []:
        key = field.get('key') or slugify(field.get('label'))
        if not key:
            continue
        columns[key] = _column_sql_for_field(field, db_alias)
    return columns


def build_lab_version_columns(lab, db_alias='default'):
    columns = OrderedDict()
    for name, definition in DEFAULT_VERSION_COLUMNS.items():
        columns[name] = _col(definition, db_alias)
    for field in lab.custom_field_schema or []:
        key = field.get('key') or slugify(field.get('label'))
        if not key:
            continue
        columns[key] = _column_sql_for_field(field, db_alias)
    return columns


def _create_table_sql(table_name, columns, db_alias='default'):
    q = lambda n: _q(n, db_alias)
    column_sql = ',\n        '.join([f'{q(name)} {definition}' for name, definition in columns.items()])
    if _is_postgresql(db_alias):
        return f'CREATE TABLE IF NOT EXISTS {q(table_name)} (\n        {column_sql}\n    )'
    return f'CREATE TABLE IF NOT EXISTS {q(table_name)} (\n        {column_sql}\n    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'


def _existing_columns(db_alias, table_name):
    if _is_postgresql(db_alias):
        with connections[db_alias].cursor() as cursor:
            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s AND table_schema = 'public'",
                [table_name],
            )
            return {row[0] for row in cursor.fetchall()}
    else:
        with connections[db_alias].cursor() as cursor:
            cursor.execute(f'SHOW COLUMNS FROM `{table_name}`')
            return {row[0] for row in cursor.fetchall()}


def _sync_missing_columns(db_alias, table_name, desired_columns):
    try:
        current_columns = _existing_columns(db_alias, table_name)
    except Exception:
        return

    missing_columns = [
        (name, definition)
        for name, definition in desired_columns.items()
        if name not in current_columns
    ]

    if not missing_columns:
        return

    q = lambda n: _q(n, db_alias)
    alter_sql = ',\n        '.join([f'ADD COLUMN {q(name)} {definition}' for name, definition in missing_columns])
    sql = f'ALTER TABLE {q(table_name)}\n        {alter_sql}'

    with connections[db_alias].cursor() as cursor:
        cursor.execute(sql)


def ensure_lab_tables(db_alias, lab):
    record_table  = lab_record_table_name(lab.id)
    version_table = lab_version_table_name(lab.id)
    record_cols   = build_lab_columns(lab, db_alias)
    version_cols  = build_lab_version_columns(lab, db_alias)
    record_sql    = _create_table_sql(record_table,  record_cols,  db_alias)
    version_sql   = _create_table_sql(version_table, version_cols, db_alias)

    with connections[db_alias].cursor() as cursor:
        cursor.execute(record_sql)
        cursor.execute(version_sql)

    _sync_missing_columns(db_alias, record_table,  record_cols)
    _sync_missing_columns(db_alias, version_table, version_cols)

    return record_table, version_table


def compile_record_values(request_obj, technician_data, custom_values=None):
    custom_values = custom_values or {}
    request_custom = request_obj.custom_field_values or {}
    merged_custom = {**request_custom, **custom_values}

    row = {
        'row_id':          technician_data.get('row_id'),
        'record_id':       technician_data.get('record_id'),
        'lab_request_id':  str(request_obj.id),
        'patient_id':      str(request_obj.patient_id),
        'hospital_id':     str(request_obj.patient.registered_by_id),
        'recorded_by_id':  technician_data.get('recorded_by_id'),
        'version':         technician_data.get('version', 1),
        'is_latest':       1 if technician_data.get('is_latest', True) else 0,
        'sha256_hash':     technician_data.get('sha256_hash'),
        'diagnosis':       request_obj.diagnosis,
        'treatment_plan':  request_obj.treatment_plan,
        'notes':           request_obj.notes,
        'chest_pain_type': request_obj.chest_pain_type,
        'age':             technician_data.get('age'),
        'gender':          technician_data.get('gender'),
    }
    row.update(merged_custom)
    return row


def extract_custom_values_from_row(row, lab):
    reserved_keys = set(DEFAULT_RECORD_COLUMNS.keys()) | {'row_id'}
    schema_keys = [field.get('key') or slugify(field.get('label')) for field in (lab.custom_field_schema or [])]
    custom_values = {}
    for key in schema_keys:
        if not key or key in reserved_keys:
            continue
        value = getattr(row, key, None)
        if value is not None:
            custom_values[key] = value
    return custom_values


def _cursor_rows(cursor):
    columns = [col[0] for col in cursor.description]
    return [SimpleNamespace(**dict(zip(columns, row))) for row in cursor.fetchall()]


def _fetch_one(db_alias, sql, params):
    with connections[db_alias].cursor() as cursor:
        cursor.execute(sql, params)
        rows = _cursor_rows(cursor)
    return rows[0] if rows else None


def _fetch_all(db_alias, sql, params):
    with connections[db_alias].cursor() as cursor:
        cursor.execute(sql, params)
        return _cursor_rows(cursor)


def _insert_row(db_alias, table_name, row):
    q = lambda n: _q(n, db_alias)
    columns = list(row.keys())
    placeholders = ', '.join(['%s'] * len(columns))
    sql = f"INSERT INTO {q(table_name)} ({', '.join(q(col) for col in columns)}) VALUES ({placeholders})"
    with connections[db_alias].cursor() as cursor:
        cursor.execute(sql, [row[column] for column in columns])


def fetch_latest_record(db_alias, lab, record_id):
    q = lambda n: _q(n, db_alias)
    table_name = lab_record_table_name(lab.id)
    try:
        return _fetch_one(
            db_alias,
            f"SELECT * FROM {q(table_name)} WHERE record_id = %s AND is_latest = 1 ORDER BY version DESC LIMIT 1",
            [str(record_id)],
        )
    except Exception:
        return None


def fetch_record_version(db_alias, lab, record_id, version_number):
    q = lambda n: _q(n, db_alias)
    table_name = lab_version_table_name(lab.id)
    try:
        record = _fetch_one(
            db_alias,
            f"SELECT * FROM {q(table_name)} WHERE record_id = %s AND version_number = %s LIMIT 1",
            [str(record_id), int(version_number)],
        )
        if record:
            return record
    except Exception:
        pass

    try:
        current_table = lab_record_table_name(lab.id)
        record = _fetch_one(
            db_alias,
            f"SELECT * FROM {q(current_table)} WHERE record_id = %s AND version = %s LIMIT 1",
            [str(record_id), int(version_number)],
        )
        if record:
            return record
    except Exception:
        pass

    if int(version_number) == 1:
        latest = fetch_latest_record(db_alias, lab, record_id)
        if latest:
            return latest
    return None


def fetch_patient_latest_records(db_alias, lab_ids, patient_id):
    if not lab_ids:
        return []
    q = lambda n: _q(n, db_alias)
    table_clauses = []
    params = [str(patient_id)]
    for lab_id in lab_ids:
        table_clauses.append(f"SELECT * FROM {q(lab_record_table_name(lab_id))} WHERE patient_id = %s AND is_latest = 1")
    sql = ' UNION ALL '.join(table_clauses) + ' ORDER BY updated_at DESC'
    try:
        return _fetch_all(db_alias, sql, params * len(lab_ids))
    except Exception:
        return []


def fetch_record_history(db_alias, lab, record_id):
    q = lambda n: _q(n, db_alias)
    table_name = lab_version_table_name(lab.id)
    try:
        history = _fetch_all(
            db_alias,
            f"SELECT * FROM {q(table_name)} WHERE record_id = %s ORDER BY version_number ASC",
            [str(record_id)],
        )
        if history:
            return history
    except Exception:
        pass

    try:
        current_table = lab_record_table_name(lab.id)
        current = _fetch_one(
            db_alias,
            f"SELECT * FROM {q(current_table)} WHERE record_id = %s ORDER BY version DESC LIMIT 1",
            [str(record_id)],
        )
        if current:
            return [current]
    except Exception:
        pass
    return []


def insert_record(db_alias, lab, row):
    _insert_row(db_alias, lab_record_table_name(lab.id), row)


def update_record(db_alias, lab, record_id, row):
    q = lambda n: _q(n, db_alias)
    table_name = lab_record_table_name(lab.id)
    update_columns = [column for column in row.keys() if column not in {'row_id', 'record_id'}]
    set_clause = ', '.join([f'{q(column)} = %s' for column in update_columns])
    params = [row[column] for column in update_columns]
    params.append(str(record_id))
    with connections[db_alias].cursor() as cursor:
        cursor.execute(f"UPDATE {q(table_name)} SET {set_clause} WHERE record_id = %s", params)
        return cursor.rowcount


def insert_version(db_alias, lab, row):
    _insert_row(db_alias, lab_version_table_name(lab.id), row)


def mark_record_not_latest(db_alias, lab, record_id):
    q = lambda n: _q(n, db_alias)
    table_name = lab_record_table_name(lab.id)
    with connections[db_alias].cursor() as cursor:
        cursor.execute(
            f"UPDATE {q(table_name)} SET is_latest = 0 WHERE record_id = %s AND is_latest = 1",
            [str(record_id)],
        )


def serialize_custom_fields(schema, values):
    result = {}
    for field in schema or []:
        key = field.get('key')
        if key and key in values:
            result[key] = values[key]
    return result