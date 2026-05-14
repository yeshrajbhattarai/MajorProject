#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medichain.settings')
django.setup()

from django.db import connection, connections
from auditlog.models import AuditLog

print("=== Database Configuration ===")
for alias, config in connections.databases.items():
    print(f"  {alias}: {config['ENGINE']} - {config['NAME']}")

print("\n=== All Tables in Default DB ===")
with connections['default'].cursor() as cursor:
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    for (table,) in tables:
        print(f"  {table}")

print("\n=== Checking for auditlog_auditlog ===")
with connections['default'].cursor() as cursor:
    try:
        cursor.execute("DESC auditlog_auditlog")
        print("  Table EXISTS")
    except Exception as e:
        print(f"  Table does NOT exist: {e}")

print("\n=== Django Migrations ===")
from django.core.management import execute_from_command_line
import sys
original_argv = sys.argv
try:
    sys.argv = ['manage.py', 'showmigrations', 'auditlog']
    execute_from_command_line(sys.argv)
finally:
    sys.argv = original_argv
