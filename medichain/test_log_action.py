#!/usr/bin/env python
import os
import django
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medichain.settings')
django.setup()

from auditlog.utils import log_action
from auditlog.models import AuditLog
from django.db import connection

print("=== Testing log_action() with scope_hospitals ===\n")

# Create a test consent ID
test_consent_id = uuid.uuid4()

# Call log_action with scope
print(f"Calling: log_action('TEST_ACTION', 'TestHospital', consent_id={test_consent_id},")
print(f"                    scope_hospitals=['Hospital A', 'Hospital B'])\n")

log_action(
    action='TEST_ACTION',
    performed_by='TestHospital',
    consent_id=test_consent_id,
    scope_hospitals=['Hospital A', 'Hospital B']
)

print("Log created. Checking database...\n")

# Query directly from database
with connection.cursor() as cursor:
    cursor.execute("""
    SELECT log_id, action, performed_by, scope_hospitals
    FROM audit_logs
    WHERE action = 'TEST_ACTION'
    ORDER BY timestamp DESC
    LIMIT 1;
    """)
    row = cursor.fetchone()
    if row:
        log_id, action, performed_by, scope_hospitals = row
        print(f"  log_id: {log_id}")
        print(f"  action: {action}")
        print(f"  performed_by: {performed_by}")
        print(f"  scope_hospitals (raw): {scope_hospitals}")
        print(f"  scope_hospitals (repr): {repr(scope_hospitals)}")
    else:
        print("  No record found!")

# Also try ORM query
print("\nUsing ORM query:")
log_obj = AuditLog.objects.filter(action='TEST_ACTION').first()
if log_obj:
    print(f"  log_id: {log_obj.log_id}")
    print(f"  scope_hospitals: {log_obj.scope_hospitals}")
    print(f"  scope_hospitals (type): {type(log_obj.scope_hospitals)}")
    print(f"  scope_hospitals (repr): {repr(log_obj.scope_hospitals)}")
else:
    print("  No record found!")
