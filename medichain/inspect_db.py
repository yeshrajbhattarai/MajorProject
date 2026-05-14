#!/usr/bin/env python
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medichain.settings')
django.setup()

from django.db import connection
from auditlog.models import AuditLog

print("=== AuditLog Model Fields ===")
for field in AuditLog._meta.get_fields():
    print(f"  {field.name}: {field.__class__.__name__}")

print("\n=== Database Schema ===")
with connection.cursor() as cursor:
    cursor.execute("DESC auditlog_auditlog")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[0]}: {col[1]}")

print("\n=== Sample Log Entry (Raw) ===")
log = AuditLog.objects.first()
if log:
    print(f"  log_id: {log.log_id}")
    print(f"  action: {log.action}")
    print(f"  scope_hospitals (type): {type(log.scope_hospitals)}")
    print(f"  scope_hospitals (value): {log.scope_hospitals}")
    print(f"  scope_hospitals (repr): {repr(log.scope_hospitals)}")

print("\n=== Trying to Create Test Log ===")
test_log = AuditLog.objects.create(
    action='TEST_ACTION',
    performed_by='test_hospital',
    scope_hospitals=['Hospital A', 'Hospital B']
)
print(f"Created test log {test_log.log_id}")
print(f"  scope_hospitals after save: {test_log.scope_hospitals}")
print(f"  scope_hospitals (repr): {repr(test_log.scope_hospitals)}")

# Refetch from DB
test_log.refresh_from_db()
print(f"  scope_hospitals after refresh: {test_log.scope_hospitals}")
print(f"  scope_hospitals (repr): {repr(test_log.scope_hospitals)}")

# Clean up
test_log.delete()
