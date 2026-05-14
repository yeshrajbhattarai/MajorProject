#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medichain.settings')
django.setup()

from consentmanagement.models import ConsentRequest

print("=== Deleting Consent Requests ===\n")

# Get all consents
consents = ConsentRequest.objects.all()
print(f"Found {consents.count()} consent(s)\n")

if consents.count() > 0:
    for consent in consents:
        print(f"Deleting consent {consent.consent_id}")
        print(f"  Patient: {consent.patient_id}")
        print(f"  Requesting: {consent.requesting_hospital}")
        print(f"  Requested To: {consent.requested_to_hospital}")
        print(f"  Status: {consent.request_status}")
        
        consent.delete()
        print()
    
    print(f"✓ Deleted {consents.count()} consent(s)")
else:
    print("No consents to delete")
