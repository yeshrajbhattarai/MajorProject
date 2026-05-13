import json
import sys

from consentmanagement.views import _build_record_bundle, _compute_transfer_hash
from hospitals.services import _payload_hash
from consentmanagement.models import ConsentRequest
from hospitals.models import MedicalRecordMeta

consent = ConsentRequest.objects.filter(request_status='APPROVED').first()
if not consent:
    print("No APPROVED ConsentRequest found in DB")
    sys.exit(0)

bundle, err = _build_record_bundle(consent)
if err:
    print("_build_record_bundle error:", err)
    sys.exit(1)

submitted_records = bundle['records']
submitted_bundle_hash = bundle['bundle_hash']

# recompute bundle
records_for_hashing = [ {k:v for k,v in r.items() if k!='stored_hash'} for r in submitted_records ]
data_for_hashing = {
    'consent_id': bundle['consent_id'],
    'patient_id': bundle['patient_id'],
    'owner_hospital': bundle['owner_hospital'],
    'records': records_for_hashing,
}
recomputed_bundle_hash = _compute_transfer_hash(data_for_hashing)
bundle_match = recomputed_bundle_hash == submitted_bundle_hash

submitted_record_ids = [ r.get('record_id') for r in submitted_records if r.get('record_id') ]
stored_meta_map = {}
for meta in MedicalRecordMeta.objects.filter(record_id__in=submitted_record_ids, hospital__hospital_name=bundle['owner_hospital']).order_by('record_id', '-version'):
    key = str(meta.record_id)
    if key not in stored_meta_map:
        stored_meta_map[key] = meta

record_integrity_results = []
all_records_verified = True

for rec in submitted_records:
    record_id = rec.get('record_id','')
    rec_data_for_hashing = {k:v for k,v in rec.items() if k!='stored_hash'}
    recomputed_transfer_hash = _compute_transfer_hash(rec_data_for_hashing)
    submitted_stored_hash = rec.get('stored_hash','')
    meta = stored_meta_map.get(record_id)
    db_stored_hash = meta.sha256_hash if meta else None

    db_match = bool(db_stored_hash) and (db_stored_hash == submitted_stored_hash)
    if not db_match:
        all_records_verified = False

    record_integrity_results.append({
        'record_id': record_id,
        'record_type': rec.get('record_type'),
        'version': rec.get('version'),
        'submitted_stored_hash': submitted_stored_hash,
        'db_stored_hash': db_stored_hash,
        'recomputed_hash': recomputed_transfer_hash,
        'transfer_match': False,
        'db_match': db_match,
        'tampered': not db_match,
        'status': '✓ Verified' if db_match else '✗ TAMPERED or CORRUPTED',
    })

overall_verified = bundle_match and all_records_verified

response = {
    'bundle_integrity': {
        'submitted_hash': submitted_bundle_hash,
        'recomputed_hash': recomputed_bundle_hash,
        'match': bundle_match,
    },
    'record_integrity': record_integrity_results,
    'overall_verified': overall_verified,
    'summary': 'All records verified. No tampering detected.' if overall_verified else 'WARNING: Integrity check failed.'
}

print(json.dumps(response, indent=2))
