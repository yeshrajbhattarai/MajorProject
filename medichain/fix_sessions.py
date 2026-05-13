#!/usr/bin/env python
"""
Fix broken sessions by clearing all sessions.
Sessions will be recreated when user logs in again.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medichain.settings')
django.setup()

from django.contrib.sessions.models import Session
from hospitals.models import Hospital

# Get a valid hospital
valid_hospital = Hospital.objects.get(hospital_name='Samarpan Hospital')
print(f"Valid hospital found: {valid_hospital.hospital_name} ({valid_hospital.id})")

# Clear all sessions
deleted_count = 0
for session in Session.objects.all():
    session.delete()
    deleted_count += 1

print(f"Cleared {deleted_count} corrupted sessions.")
print("\nPlease log in again. Your sessions will be recreated with valid hospital IDs.")
