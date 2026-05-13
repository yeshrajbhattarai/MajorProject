import json
import sys
from types import SimpleNamespace

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

body = {'records': bundle['records'], 'bundle_hash': bundle['bundle_hash']}
req_hospital = Hospital.objects.get(hospital_name=consent.requesting_hospital)
request = SimpleNamespace(data=body, user_payload={
    'user_type': 'staff',
    'staff_role': 'doctor',
    'hospital_id': req_hospital.id,
})

response = verify_hash(request, consent.consent_id)
print('Status:', response.status_code)
print(json.dumps(response.data, indent=2))
