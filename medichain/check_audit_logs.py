#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medichain.settings')
django.setup()

from django.db import connection

print("=== audit_logs Table Schema ===")
with connection.cursor() as cursor:
    cursor.execute("DESC audit_logs")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[0]:20s} {col[1]:30s} {col[2]:5s} {col[3]:10s}")

print("\n=== Sample Records from audit_logs ===")
with connection.cursor() as cursor:
    # Get raw SQL to see actual values
    cursor.execute("""
    SELECT log_id, action, performed_by, scope_hospitals
    FROM audit_logs
    ORDER BY timestamp DESC
    LIMIT 5;
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(f"  action={row[1]:20s} | performed_by={row[2]:30s} | scope={row[3]}")
