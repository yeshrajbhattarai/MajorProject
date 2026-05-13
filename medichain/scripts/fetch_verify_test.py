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

print(f"Consent: {consent.consent_id}  Owner: {bundle['owner_hospital']}  total_records: {bundle['total_records']}")
print(f"bundle_hash (from build): {bundle['bundle_hash']}")

# Recompute bundle using transfer canonicaliser
records_for_hashing = [ {k:v for k,v in r.items() if k!='stored_hash'} for r in bundle['records'] ]
data_for_hashing = {
    'consent_id': bundle['consent_id'],
    'patient_id': bundle['patient_id'],
    'owner_hospital': bundle['owner_hospital'],
    'records': records_for_hashing,
}
recomputed_bundle = _compute_transfer_hash(data_for_hashing)
print(f"recomputed_bundle (transfer canonicaliser): {recomputed_bundle}")
print('bundle_match_transfer:', recomputed_bundle == bundle['bundle_hash'])

print('\nPer-record comparisons:')
for r in bundle['records']:
    rid = r.get('record_id')
    stored = r.get('stored_hash')
    rec_for_hash = {k:v for k,v in r.items() if k!='stored_hash'}
    rec_transfer = _compute_transfer_hash(rec_for_hash)
    rec_payload = _payload_hash(rec_for_hash)
    meta = MedicalRecordMeta.objects.filter(record_id=rid).order_by('-version').first()
    db_hash = meta.sha256_hash if meta else None

    out = {
        'record_id': rid,
        'stored_hash_in_bundle': stored,
        'db_stored_hash': db_hash,
        'recomputed_transfer_hash': rec_transfer,
        'recomputed_payload_hash': rec_payload,
        'transfer_matches_stored': rec_transfer == stored,
        'payload_matches_stored': rec_payload == stored,
        'payload_matches_db': rec_payload == db_hash,
    }
    print(json.dumps(out, indent=2))

print('\nDone')
