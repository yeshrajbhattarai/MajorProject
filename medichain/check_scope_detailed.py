#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medichain.settings')
django.setup()

from django.db import connection

print("=== All PATIENT_APPROVED, HOSPITAL_APPROVED, CONSENT_CREATED logs ===")
with connection.cursor() as cursor:
    cursor.execute("""
    SELECT log_id, action, performed_by, scope_hospitals, timestamp
    FROM audit_logs
    WHERE action IN ('PATIENT_APPROVED', 'HOSPITAL_APPROVED', 'CONSENT_CREATED')
    ORDER BY timestamp DESC;
    """)
    rows = cursor.fetchall()
    print(f"Found {len(rows)} records\n")
    for row in rows:
        log_id, action, performed_by, scope, timestamp = row
        print(f"  {timestamp} | {action:20s} | {performed_by:30s} | scope={scope}")

print("\n=== Checking if ANY record has non-empty scope_hospitals ===")
with connection.cursor() as cursor:
    cursor.execute("""
    SELECT COUNT(*), action
    FROM audit_logs
    WHERE JSON_LENGTH(scope_hospitals) > 0
    GROUP BY action;
    """)
    rows = cursor.fetchall()
    print(f"Records with non-empty scope by action:")
    for count, action in rows:
        print(f"  {action}: {count}")
