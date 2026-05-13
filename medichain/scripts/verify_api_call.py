import json
import sys

from rest_framework.test import APIRequestFactory
from consentmanagement.views import _build_record_bundle, verify_hash
from consentmanagement.models import ConsentRequest
from hospitals.models import Hospital

consent = ConsentRequest.objects.filter(request_status='APPROVED').first()
if not consent:
    print("No APPROVED ConsentRequest found")
    sys.exit(0)

bundle, err = _build_record_bundle(consent)
if err:
    print('build error', err); sys.exit(1)

factory = APIRequestFactory()
body = {'records': bundle['records'], 'bundle_hash': bundle['bundle_hash']}
request = factory.post(f'/api/consent/{consent.consent_id}/verify-hash/', body, format='json')
# Attach a user_payload that corresponds to the requesting hospital
req_hospital = Hospital.objects.get(hospital_name=consent.requesting_hospital)
request.user_payload = {
    'user_type': 'staff',
    'staff_role': 'doctor',
    'hospital_id': req_hospital.id,
}

response = verify_hash(request, consent.consent_id)
print('Status:', response.status_code)
try:
    print(json.dumps(response.data, indent=2))
except Exception:
    print(response.data)
