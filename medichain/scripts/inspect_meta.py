import json
import sys

from consentmanagement.views import _build_record_bundle
from consentmanagement.models import ConsentRequest
from hospitals.models import MedicalRecordMeta, Hospital

consent = ConsentRequest.objects.filter(request_status='APPROVED').first()
if not consent:
    print('No APPROVED consent'); sys.exit(0)

bundle, err = _build_record_bundle(consent)
if err:
    print('build error', err); sys.exit(1)

for r in bundle['records']:
    rid = r['record_id']
    print('\nRecord:', rid)
    metas = MedicalRecordMeta.objects.filter(record_id=rid).order_by('-version')
    for m in metas:
        hosp_name = m.hospital.hospital_name if m.hospital else 'UNKNOWN'
        print('  hospital:', hosp_name, 'version:', m.version, 'sha:', m.sha256_hash)

print('\nDone')
