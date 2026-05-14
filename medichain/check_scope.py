#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medichain.settings')
django.setup()

from auditlog.models import AuditLog

print("=== Recent HOSPITAL_APPROVED and CONSENT_CREATED logs ===")
recent = AuditLog.objects.filter(action__in=['HOSPITAL_APPROVED', 'CONSENT_CREATED']).order_by('-timestamp')[:5]
for log in recent:
    print(f'{log.timestamp} | {log.action:20s} | scope={log.scope_hospitals}')

print("\n=== Recent RECORD_ACCESS_ATTEMPT logs ===")
recent_access = AuditLog.objects.filter(action='RECORD_ACCESS_ATTEMPT').order_by('-timestamp')[:3]
for log in recent_access:
    print(f'{log.timestamp} | {log.action:20s} | scope={log.scope_hospitals}')
