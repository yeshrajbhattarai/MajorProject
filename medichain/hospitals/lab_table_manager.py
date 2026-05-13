import re
from collections import OrderedDict

from django.db import connections
from types import SimpleNamespace


DEFAULT_RECORD_COLUMNS = OrderedDict([
    ('row_id', 'CHAR(36) PRIMARY KEY'),
    ('record_id', 'CHAR(36) NOT NULL UNIQUE'),
    ('lab_request_id', 'CHAR(36) NOT NULL UNIQUE'),
    ('patient_id', 'CHAR(36) NOT NULL'),
    ('hospital_id', 'CHAR(36) NOT NULL'),
    ('recorded_by_id', 'CHAR(36) NOT NULL'),
    ('version', 'INT NOT NULL DEFAULT 1'),
    ('is_latest', 'TINYINT(1) NOT NULL DEFAULT 1'),
    ('sha256_hash', 'CHAR(64) NOT NULL'),
    ('created_at', 'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP'),
    ('updated_at', 'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
    ('diagnosis', 'LONGTEXT NOT NULL'),
    ('treatment_plan', 'LONGTEXT NOT NULL'),
    ('notes', 'LONGTEXT NULL'),
    ('chest_pain_type', 'VARCHAR(20) NOT NULL'),
    ('age', 'INT NOT NULL'),
    ('gender', 'VARCHAR(10) NOT NULL'),
])

DEFAULT_VERSION_COLUMNS = OrderedDict([
    ('version_row_id', 'CHAR(36) PRIMARY KEY'),
    ('record_id', 'CHAR(36) NOT NULL'),
    ('version_number', 'INT NOT NULL'),
    ('changed_by_id', 'CHAR(36) NOT NULL'),
    ('change_reason', 'LONGTEXT NULL'),
    ('changed_at', 'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP'),
    ('row_id', 'CHAR(36) NOT NULL'),
    ('lab_request_id', 'CHAR(36) NOT NULL'),
    ('patient_id', 'CHAR(36) NOT NULL'),
    ('hospital_id', 'CHAR(36) NOT NULL'),
    ('recorded_by_id', 'CHAR(36) NOT NULL'),
    ('version', 'INT NOT NULL'),
    ('is_latest', 'TINYINT(1) NOT NULL'),
    ('sha256_hash', 'CHAR(64) NOT NULL'),
    ('diagnosis', 'LONGTEXT NOT NULL'),
    ('treatment_plan', 'LONGTEXT NOT NULL'),
    ('notes', 'LONGTEXT NULL'),
    ('chest_pain_type', 'VARCHAR(20) NOT NULL'),
    ('age', 'INT NOT NULL'),
    ('gender', 'VARCHAR(10) NOT NULL'),
])


def slugify(value):
    return re.sub(r'[^a-z0-9]+', '_', (value or '').strip().lower()).strip('_')


def lab_record_table_name(lab_id):
    return f"lab_record_{str(lab_id).replace('-', '')[:12]}"


def lab_version_table_name(lab_id):
    return f"lab_record_version_{str(lab_id).replace('-', '')[:12]}"


def _column_sql_for_field(field):
    field_type = (field.get('type') or 'text').strip().lower()
    required = bool(field.get('required', False))
    null_sql = 'NOT NULL' if required else 'NULL'

    if field_type in {'text', 'textarea'}:
        return f'LONGTEXT {null_sql}'
    if field_type == 'integer':
        return f'INT {null_sql}'
    if field_type in {'number', 'decimal'}:
        return f'DECIMAL(18,6) {null_sql}'
    if field_type == 'date':
        return f'DATE {null_sql}'
    if field_type == 'choice':
        return f'VARCHAR(255) {null_sql}'
    if field_type == 'boolean':
        return f'TINYINT(1) {null_sql}'
    return f'LONGTEXT {null_sql}'


def build_lab_columns(lab):
    columns = OrderedDict(DEFAULT_RECORD_COLUMNS)
    for field in lab.custom_field_schema or []:
        key = field.get('key') or slugify(field.get('label'))
        if not key:
            continue
        columns[key] = _column_sql_for_field(field)
    return columns


def build_lab_version_columns(lab):
    columns = OrderedDict(DEFAULT_VERSION_COLUMNS)
    for field in lab.custom_field_schema or []:
        key = field.get('key') or slugify(field.get('label'))
        if not key:
            continue
        columns[key] = _column_sql_for_field(field)
    return columns


def _create_table_sql(table_name, columns):
    column_sql = ',\n        '.join([f'`{name}` {definition}' for name, definition in columns.items()])
    return f'CREATE TABLE IF NOT EXISTS `{table_name}` (\n        {column_sql}\n    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'


def _existing_columns(db_alias, table_name):
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

    alter_sql = ',\n        '.join([f'ADD COLUMN `{name}` {definition}' for name, definition in missing_columns])
    sql = f'ALTER TABLE `{table_name}`\n        {alter_sql}'

    with connections[db_alias].cursor() as cursor:
        cursor.execute(sql)


def ensure_lab_tables(db_alias, lab):
    record_table = lab_record_table_name(lab.id)
    version_table = lab_version_table_name(lab.id)
    record_sql = _create_table_sql(record_table, build_lab_columns(lab))
    version_sql = _create_table_sql(version_table, build_lab_version_columns(lab))

    with connections[db_alias].cursor() as cursor:
        cursor.execute(record_sql)
        cursor.execute(version_sql)

    _sync_missing_columns(db_alias, record_table, build_lab_columns(lab))
    _sync_missing_columns(db_alias, version_table, build_lab_version_columns(lab))

    return record_table, version_table


def compile_record_values(request_obj, technician_data, custom_values=None):
    custom_values = custom_values or {}
    request_custom = request_obj.custom_field_values or {}
    merged_custom = {**request_custom, **custom_values}

    row = {
        'row_id': technician_data.get('row_id'),
        'record_id': technician_data.get('record_id'),
        'lab_request_id': str(request_obj.id),
        'patient_id': str(request_obj.patient_id),
        'hospital_id': str(request_obj.patient.registered_by_id),
        'recorded_by_id': technician_data.get('recorded_by_id'),
        'version': technician_data.get('version', 1),
        'is_latest': 1 if technician_data.get('is_latest', True) else 0,
        'sha256_hash': technician_data.get('sha256_hash'),
        'diagnosis': request_obj.diagnosis,
        'treatment_plan': request_obj.treatment_plan,
        'notes': request_obj.notes,
        'chest_pain_type': request_obj.chest_pain_type,
        'age': technician_data.get('age'),
        'gender': technician_data.get('gender'),
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
    columns = list(row.keys())
    placeholders = ', '.join(['%s'] * len(columns))
    sql = f"INSERT INTO `{table_name}` ({', '.join(f'`{col}`' for col in columns)}) VALUES ({placeholders})"
    with connections[db_alias].cursor() as cursor:
        cursor.execute(sql, [row[column] for column in columns])


def _update_rows(db_alias, table_name, set_clause, params):
    sql = f"UPDATE `{table_name}` SET {set_clause}"
    with connections[db_alias].cursor() as cursor:
        cursor.execute(sql, params)


def fetch_latest_record(db_alias, lab, record_id):
    table_name = lab_record_table_name(lab.id)
    try:
        return _fetch_one(
            db_alias,
            f"SELECT * FROM `{table_name}` WHERE record_id = %s AND is_latest = 1 ORDER BY version DESC LIMIT 1",
            [str(record_id)],
        )
    except Exception:
        return None


def fetch_record_version(db_alias, lab, record_id, version_number):
    table_name = lab_version_table_name(lab.id)
    try:
        record = _fetch_one(
            db_alias,
            f"SELECT * FROM `{table_name}` WHERE record_id = %s AND version_number = %s LIMIT 1",
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
            f"SELECT * FROM `{current_table}` WHERE record_id = %s AND version = %s LIMIT 1",
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
    table_clauses = []
    params = [str(patient_id)]
    for lab_id in lab_ids:
        table_clauses.append(f"SELECT * FROM `{lab_record_table_name(lab_id)}` WHERE patient_id = %s AND is_latest = 1")
    sql = ' UNION ALL '.join(table_clauses) + ' ORDER BY updated_at DESC'
    try:
        return _fetch_all(db_alias, sql, params * len(lab_ids))
    except Exception:
        return []


def fetch_record_history(db_alias, lab, record_id):
    table_name = lab_version_table_name(lab.id)
    try:
        history = _fetch_all(
            db_alias,
            f"SELECT * FROM `{table_name}` WHERE record_id = %s ORDER BY version_number ASC",
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
            f"SELECT * FROM `{current_table}` WHERE record_id = %s ORDER BY version DESC LIMIT 1",
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
    table_name = lab_record_table_name(lab.id)
    update_columns = [column for column in row.keys() if column not in {'row_id', 'record_id'}]
    set_clause = ', '.join([f'`{column}` = %s' for column in update_columns])
    params = [row[column] for column in update_columns]
    params.append(str(record_id))
    with connections[db_alias].cursor() as cursor:
        cursor.execute(f"UPDATE `{table_name}` SET {set_clause} WHERE record_id = %s", params)
        return cursor.rowcount


def insert_version(db_alias, lab, row):
    _insert_row(db_alias, lab_version_table_name(lab.id), row)


def mark_record_not_latest(db_alias, lab, record_id):
    table_name = lab_record_table_name(lab.id)
    with connections[db_alias].cursor() as cursor:
        cursor.execute(
            f"UPDATE `{table_name}` SET is_latest = 0 WHERE record_id = %s AND is_latest = 1",
            [str(record_id)],
        )


def serialize_custom_fields(schema, values):
    result = {}
    for field in schema or []:
        key = field.get('key')
        if key and key in values:
            result[key] = values[key]
    return result
