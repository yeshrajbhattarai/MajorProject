#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medichain.settings')
django.setup()

from consentmanagement.models import ConsentRequest

print("=== Resetting Consent Requests to PENDING ===\n")

# Get all approved/rejected consents
consents = ConsentRequest.objects.exclude(request_status='PENDING')
print(f"Found {consents.count()} non-pending consents\n")

if consents.count() > 0:
    for consent in consents:
        print(f"Resetting consent {consent.consent_id}")
        print(f"  Patient: {consent.patient_id}")
        print(f"  Requesting: {consent.requesting_hospital}")
        print(f"  Requested To: {consent.requested_to_hospital}")
        print(f"  Status: {consent.request_status} → PENDING")
        
        consent.request_status = 'PENDING'
        consent.patient_choice = 'PENDING'
        consent.hospital_choice = 'PENDING'
        consent.save()
        print()
    
    print(f"✓ Reset {consents.count()} consents to PENDING")
else:
    print("No consents to reset - all are already PENDING")
