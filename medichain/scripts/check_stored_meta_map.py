import json
import sys

from consentmanagement.views import _build_record_bundle
from consentmanagement.models import ConsentRequest
from hospitals.models import MedicalRecordMeta

consent = ConsentRequest.objects.filter(request_status='APPROVED').first()
if not consent:
    print('No APPROVED consent'); sys.exit(0)

bundle, err = _build_record_bundle(consent)
if err:
    print('build error', err); sys.exit(1)

submitted_record_ids = [ r.get('record_id') for r in bundle['records'] if r.get('record_id') ]
stored_meta_map = {}
for meta in MedicalRecordMeta.objects.filter(record_id__in=submitted_record_ids, hospital__hospital_name=consent.requested_to_hospital).order_by('record_id', '-version'):
    key = str(meta.record_id)
    if key not in stored_meta_map:
        stored_meta_map[key] = meta

print('Bundle stored_hashes:')
for r in bundle['records']:
    print(' ', r['record_id'], r.get('stored_hash'))

print('\nSelected metas:')
for k,v in stored_meta_map.items():
    print(' ', k, v.version, v.sha256_hash, 'hospital=', v.hospital.hospital_name)

print('\nAll metas for these records:')
for rid in submitted_record_ids:
    print('\nRecord', rid)
    for m in MedicalRecordMeta.objects.filter(record_id=rid).order_by('-version'):
        print('   v', m.version, m.sha256_hash, 'hospital=', m.hospital.hospital_name)

print('\nDone')
