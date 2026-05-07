import hashlib
import json

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import ConsentRequest
from .serializers import (
    ConsentRequestSerializer,
    ConsentCreateSerializer,
    PatientDecisionSerializer,
    HospitalDecisionSerializer,
)
from hospitals.models import Hospital, Patient, MedicalRecordMeta
from auditlog.utils import log_action


# ─────────────────────────────────────────────────────────────────────────────
# HELPER  — extract hospital identity from JWT payload
# ─────────────────────────────────────────────────────────────────────────────

def get_hospital_from_payload(request):
    """
    Reads the JWT payload attached by MediChainJWTAuthentication and returns
    the verified Hospital object (or an error Response).

    Allowed callers:
      - hospital_admin  → full consent access
      - staff (doctor / nurse) → consent access; technicians are blocked
    """
    payload = getattr(request, 'user_payload', None)

    if payload is None:
        return None, Response({"error": "Authentication required"}, status=401)

    user_type = payload.get('user_type')

    if user_type == 'hospital_admin':
        hospital_id = payload.get('hospital_id')

    elif user_type == 'staff':
        role = payload.get('staff_role')
        if role not in ['doctor', 'nurse']:
            return None, Response(
                {"error": "Unauthorized — only doctors and nurses can perform this action"},
                status=403,
            )
        hospital_id = payload.get('hospital_id')

    else:
        return None, Response(
            {"error": "Only hospital users can perform this action"},
            status=403,
        )

    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return None, Response({"error": "Hospital not found"}, status=401)

    if hospital.account_status != 'active':
        return None, Response({"error": "Hospital account is not active"}, status=403)

    return hospital, None


# ─────────────────────────────────────────────────────────────────────────────
# HELPER  — build a canonical, deterministic SHA-256 hash of a record payload
# ─────────────────────────────────────────────────────────────────────────────

def _compute_transfer_hash(record_payload: dict) -> str:
    """
    Produces a stable SHA-256 fingerprint of the transferred record payload.

    Rules:
      - Keys are sorted alphabetically so insertion order never matters.
      - The JSON is serialised without extra whitespace (compact separators).
      - Non-serialisable values (Decimal, date, uuid …) fall back to str().

    The same function is called both when *sending* and when *verifying*, so
    any byte-level difference in the received data will cause a mismatch.
    """
    canonical = json.dumps(
        record_payload,
        sort_keys=True,
        separators=(',', ':'),
        default=str,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# HELPER  — build the transferable record bundle for a patient
# ─────────────────────────────────────────────────────────────────────────────

def _build_record_bundle(consent: ConsentRequest):
    """
    Looks up all MedicalRecordMeta rows for this patient that belong to the
    owning hospital and assembles a structured bundle that is safe to transfer.

    Returns: (bundle_dict, error_string_or_None)
    """
    # Resolve the owning hospital so we can scope the lookup correctly.
    try:
        owning_hospital = Hospital.objects.get(
            hospital_name=consent.requested_to_hospital
        )
    except Hospital.DoesNotExist:
        return None, "Owning hospital not found in MediChain"

    # Resolve the patient. consent.patient_id is a CharField (UUID string).
    try:
        patient = Patient.objects.get(id=consent.patient_id)
    except Patient.DoesNotExist:
        return None, "Patient not found"

    # Fetch the latest version of every distinct record the owning hospital
    # holds for this patient. We use the teammate's MedicalRecordMeta table
    # which already stores the SHA-256 hash at write time.
    meta_rows = (
        MedicalRecordMeta.objects
        .filter(
            hospital=owning_hospital,
            patient_id=patient.id,
        )
        .select_related('lab_request', 'lab_request__lab', 'lab_request__requested_by')
        .order_by('record_id', '-version')
    )

    # Deduplicate: keep only the latest version per logical record_id.
    seen = {}
    for meta in meta_rows:
        key = str(meta.record_id)
        if key not in seen:
            seen[key] = meta
    latest_metas = list(seen.values())

    if not latest_metas:
        return None, "No medical records found for this patient at the owning hospital"

    # Build one entry per record.
    records = []
    for meta in latest_metas:
        lab_request = meta.lab_request
        lab_info = None
        if lab_request and lab_request.lab:
            lab_info = {
                "lab_type": lab_request.lab.lab_type,
                "lab_name": lab_request.lab.name,
            }

        entry = {
            "record_id":           str(meta.record_id),
            "version":             meta.version,
            "record_type":         meta.record_type,
            "created_at":          meta.created_at.isoformat() if meta.created_at else None,
            "updated_at":          meta.updated_at.isoformat() if meta.updated_at else None,
            "lab":                 lab_info,
            # Clinical fields from the linked lab request (owning hospital's copy).
            "diagnosis":           lab_request.diagnosis if lab_request else None,
            "treatment_plan":      lab_request.treatment_plan if lab_request else None,
            "notes":               lab_request.notes if lab_request else None,
            "chest_pain_type":     lab_request.chest_pain_type if lab_request else None,
            # Custom / extra fields stored in the meta row itself.
            "custom_field_values": meta.custom_field_values or {},
            # The hash that was computed and stored when the record was originally
            # written by the owning hospital's technician / doctor.
            "stored_hash":         meta.sha256_hash,
        }
        records.append(entry)

    # The transfer bundle is the object we will hash end-to-end.
    # It intentionally excludes per-record stored_hash values so the bundle
    # hash covers the actual data content, not the stored hashes.
    data_for_hashing = {
        "consent_id":     str(consent.consent_id),
        "patient_id":     str(consent.patient_id),
        "owner_hospital": consent.requested_to_hospital,
        "records": [
            {k: v for k, v in entry.items() if k != "stored_hash"}
            for entry in records
        ],
    }
    bundle_hash = _compute_transfer_hash(data_for_hashing)

    return {
        "consent_id":       str(consent.consent_id),
        "patient_id":       str(consent.patient_id),
        "patient_name":     patient.full_name,
        "owner_hospital":   consent.requested_to_hospital,
        "records":          records,
        # Transfer-level hash — covers all record data in this bundle.
        # The receiver must recompute this to confirm nothing was altered in transit.
        "bundle_hash":      bundle_hash,
        "total_records":    len(records),
    }, None


# ─────────────────────────────────────────────────────────────────────────────
# HOSPITAL DIRECTORY  — list all active hospitals except the caller's
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def hospital_directory(request):
    """Returns all active hospitals the requester can target for a consent."""
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    hospitals = (
        Hospital.objects
        .filter(account_status='active')
        .exclude(hospital_name=hospital.hospital_name)
        .values('hospital_name', 'city', 'state')
    )
    return Response(list(hospitals), status=200)


# ─────────────────────────────────────────────────────────────────────────────
# PATIENT SEARCH  — phone-number lookup for the consent form
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def patient_search(request):
    """Find patients by 10-digit phone number for use in the consent form."""
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    phone = request.query_params.get('phone', '').strip()
    if not phone or len(phone) != 10 or not phone.isdigit():
        return Response({"error": "Provide a valid 10-digit phone number."}, status=400)

    patients = Patient.objects.filter(phone=phone).select_related('registered_by')
    results = [
        {
            "patient_id":    str(p.id),
            "full_name":     p.full_name,
            "phone":         p.phone,
            "registered_at": p.registered_by.hospital_name if p.registered_by else "Unknown",
        }
        for p in patients
    ]
    return Response(results, status=200)


# ─────────────────────────────────────────────────────────────────────────────
# CONSENT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def create_consent(request):
    """
    Create a new consent request.
    The requesting hospital identity is taken from the JWT — the body value
    is overridden so no hospital can impersonate another.
    """
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    data = request.data.copy()
    data['requesting_hospital'] = hospital.hospital_name

    serializer = ConsentCreateSerializer(data=data)
    if serializer.is_valid():
        consent = serializer.save()
        log_action('CONSENT_CREATED', hospital.hospital_name, consent.consent_id)
        return Response(ConsentRequestSerializer(consent).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(['GET'])
@permission_classes([AllowAny])
def view_consent(request):
    """Dev-only: list every consent record without auth. Remove before prod."""
    consents = ConsentRequest.objects.all().order_by('-created_at')
    return Response(ConsentRequestSerializer(consents, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def sent_requests(request):
    """List consent requests sent by the authenticated hospital."""
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    consents = ConsentRequest.objects.filter(
        requesting_hospital=hospital.hospital_name
    ).order_by('-created_at')
    return Response(ConsentRequestSerializer(consents, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def received_requests(request):
    """List consent requests received by the authenticated hospital."""
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    consents = ConsentRequest.objects.filter(
        requested_to_hospital=hospital.hospital_name
    ).order_by('-created_at')
    return Response(ConsentRequestSerializer(consents, many=True).data)


@api_view(['GET', 'DELETE'])
@permission_classes([AllowAny])
def consent_detail(request, consent_id):
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    if request.method == 'GET':
        consent = get_object_or_404(ConsentRequest, consent_id=consent_id)
        return Response(ConsentRequestSerializer(consent).data)

    # DELETE path
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if hospital.hospital_name != consent.requesting_hospital:
        return Response(
            {"error": "Unauthorized — only the requesting hospital can delete"},
            status=403,
        )
    if consent.request_status != 'PENDING':
        return Response(
            {"error": "Cannot delete an approved or rejected consent"},
            status=400,
        )

    log_action(
        'CONSENT_DELETED',
        hospital.hospital_name,
        consent.consent_id,
        extra_info=(
            f"Consent between {consent.requesting_hospital} "
            f"and {consent.requested_to_hospital}"
        ),
    )
    consent.delete()
    return Response({"message": "Consent deleted successfully"}, status=200)


@api_view(['PATCH'])
@permission_classes([AllowAny])
def patient_decision(request, consent_id):
    """Patient approves or rejects a PENDING consent request."""
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if consent.request_status != 'PENDING':
        return Response({"error": "Consent already finalised"}, status=400)
    if consent.patient_choice != 'PENDING':
        return Response({"error": "Patient has already responded"}, status=400)

    serializer = PatientDecisionSerializer(consent, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        action = (
            'PATIENT_APPROVED'
            if request.data.get('patient_choice') == 'APPROVED'
            else 'PATIENT_REJECTED'
        )
        log_action(action, hospital.hospital_name, consent.consent_id)
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['PATCH'])
@permission_classes([AllowAny])
def hospital_decision(request, consent_id):
    """
    Owning hospital approves or rejects.  Identity is verified against the JWT
    so no other hospital can approve on behalf of the record owner.
    """
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if hospital.hospital_name != consent.requested_to_hospital:
        return Response(
            {"error": "Unauthorized — you are not the owning hospital"},
            status=403,
        )
    if consent.request_status != 'PENDING':
        return Response({"error": "Consent already finalised"}, status=400)
    if consent.hospital_choice != 'PENDING':
        return Response({"error": "Hospital has already responded"}, status=400)

    serializer = HospitalDecisionSerializer(consent, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        action = (
            'HOSPITAL_APPROVED'
            if request.data.get('hospital_choice') == 'APPROVED'
            else 'HOSPITAL_REJECTED'
        )
        log_action(action, hospital.hospital_name, consent.consent_id)
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


# ─────────────────────────────────────────────────────────────────────────────
# RECORD TRANSFER  — fetch_record (owning hospital serves the data)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def fetch_record(request, consent_id):
    """
    Fetch the real medical records for a patient after a four-step check:

      1. JWT authentication  — confirms the caller is a valid MediChain hospital.
      2. Consent exists      — the ConsentRequest row must be present.
      3. Consent is APPROVED — both patient and owning hospital have approved.
      4. Requester matches   — only the hospital that raised the consent can pull.

    On success the endpoint returns the full record bundle **plus** a
    SHA-256 bundle_hash covering all transferred data.  The requesting hospital
    should store this hash and later use POST /verify-hash/ to confirm the data
    they received has not been altered.

    The per-record `stored_hash` fields are also included so the requester can
    independently verify each individual record against the owning hospital's
    original write-time hash.
    """
    # ── Step 1: authenticate ──────────────────────────────────────────────────
    hospital, error = get_hospital_from_payload(request)
    if error:
        # Log before returning — even failed attempts should be auditable.
        log_action('RECORD_ACCESS_ATTEMPT', 'unauthenticated', consent_id)
        return error

    log_action('RECORD_ACCESS_ATTEMPT', hospital.hospital_name, consent_id)

    # ── Step 2: consent exists ────────────────────────────────────────────────
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    # ── Step 3: consent must be APPROVED ─────────────────────────────────────
    if consent.request_status != 'APPROVED':
        log_action('RECORD_ACCESS_DENIED', hospital.hospital_name, consent_id,
                   extra_info=f"Consent status: {consent.request_status}")
        return Response(
            {"error": "Consent is not approved. Both the patient and the owning hospital must approve before records can be shared."},
            status=403,
        )

    # ── Step 4: only the requesting hospital may pull ─────────────────────────
    if hospital.hospital_name != consent.requesting_hospital:
        log_action('RECORD_ACCESS_DENIED', hospital.hospital_name, consent_id,
                   extra_info="Caller is not the requesting hospital")
        return Response(
            {"error": "Unauthorized — only the requesting hospital can fetch this record"},
            status=403,
        )

    # ── Build the real record bundle ──────────────────────────────────────────
    bundle, bundle_error = _build_record_bundle(consent)
    if bundle_error:
        log_action('RECORD_ACCESS_FAILED', hospital.hospital_name, consent_id,
                   extra_info=bundle_error)
        return Response({"error": bundle_error}, status=404)

    log_action('RECORD_ACCESS_SUCCESS', hospital.hospital_name, consent.consent_id)

    return Response({
        **bundle,
        # Remind the caller of the verification endpoint.
        "verify_url": f"/api/consent/{consent_id}/verify-hash/",
        "instructions": (
            "Store the bundle_hash. After receiving this response, POST the "
            "records array back to verify_url to confirm data integrity."
        ),
    }, status=200)


# ─────────────────────────────────────────────────────────────────────────────
# HASH VERIFICATION  — verify_hash (requesting hospital confirms integrity)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_hash(request, consent_id):
    """
    Integrity check endpoint — called by the **requesting** hospital after it
    has received and optionally stored the transferred records.

    Expected POST body:
    {
        "records":     [ ... ],        // the records array exactly as received
        "bundle_hash": "<hex string>"  // the bundle_hash value from fetch_record
    }

    The server recomputes the SHA-256 over the submitted records using the
    same canonical serialisation as fetch_record.  It also cross-checks each
    record's submitted data against the stored_hash that was saved by the
    owning hospital at write time (in MedicalRecordMeta.sha256_hash).

    Response shape:
    {
        "bundle_integrity": {
            "submitted_hash":  "<hex>",
            "recomputed_hash": "<hex>",
            "match":           true | false
        },
        "record_integrity": [
            {
                "record_id":       "...",
                "stored_hash":     "<hex>",   // owning hospital's write-time hash
                "recomputed_hash": "<hex>",   // hash of the data we were sent
                "match":           true | false,
                "tampered":        false | true
            },
            ...
        ],
        "overall_verified": true | false,
        "summary": "All records verified. No tampering detected."
    }
    """
    # ── Authenticate ──────────────────────────────────────────────────────────
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    # ── The requesting hospital may only verify its own consents ──────────────
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if hospital.hospital_name != consent.requesting_hospital:
        return Response(
            {"error": "Unauthorized — only the requesting hospital can verify this consent's records"},
            status=403,
        )

    if consent.request_status != 'APPROVED':
        return Response(
            {"error": "Consent is not approved"},
            status=403,
        )

    # ── Validate request body ─────────────────────────────────────────────────
    submitted_records = request.data.get('records')
    submitted_bundle_hash = request.data.get('bundle_hash', '').strip()

    if not submitted_records or not isinstance(submitted_records, list):
        return Response(
            {"error": "'records' must be a non-empty list (the records array from fetch_record)"},
            status=400,
        )
    if not submitted_bundle_hash:
        return Response(
            {"error": "'bundle_hash' is required (the value returned by fetch_record)"},
            status=400,
        )

    # ── Re-compute the bundle hash from submitted data ────────────────────────
    # Strip stored_hash from each entry (it was not included when hashing on send).
    records_for_hashing = [
        {k: v for k, v in rec.items() if k != 'stored_hash'}
        for rec in submitted_records
    ]
    data_for_hashing = {
        "consent_id":     str(consent.consent_id),
        "patient_id":     str(consent.patient_id),
        "owner_hospital": consent.requested_to_hospital,
        "records":        records_for_hashing,
    }
    recomputed_bundle_hash = _compute_transfer_hash(data_for_hashing)
    bundle_match = recomputed_bundle_hash == submitted_bundle_hash

    # ── Per-record integrity check ────────────────────────────────────────────
    # For each record the requester submitted, recompute the content hash and
    # compare against the stored_hash that the owning hospital saved when the
    # technician originally created the record.

    # Prefetch stored hashes from MedicalRecordMeta to avoid N+1 queries.
    submitted_record_ids = [
        r.get('record_id') for r in submitted_records if r.get('record_id')
    ]
    stored_meta_map = {
        str(meta.record_id): meta
        for meta in MedicalRecordMeta.objects.filter(
            record_id__in=submitted_record_ids
        ).order_by('record_id', '-version')
        # We only need the latest version's hash per record_id; the dict
        # comprehension above naturally keeps the first (latest) hit because
        # we ordered by -version.
    }

    record_integrity_results = []
    all_records_verified = True

    for rec in submitted_records:
        record_id = rec.get('record_id', '')

        # Recompute hash of the submitted record data (excluding stored_hash).
        rec_data_for_hashing = {k: v for k, v in rec.items() if k != 'stored_hash'}
        recomputed_record_hash = _compute_transfer_hash(rec_data_for_hashing)

        # The stored_hash sent by fetch_record is the owning hospital's
        # write-time hash of the payload (computed by _payload_hash in services.py).
        # We compare the recomputed transfer hash against it as a cross-check.
        submitted_stored_hash = rec.get('stored_hash', '')

        # Also look up what MedicalRecordMeta says the hash should be.
        meta = stored_meta_map.get(record_id)
        db_stored_hash = meta.sha256_hash if meta else None

        # Primary verification: does the recomputed transfer hash match the
        # submitted stored_hash?  This tells us whether the data content
        # matches what was signed at write time.
        transfer_match = bool(submitted_stored_hash) and (
            recomputed_record_hash == submitted_stored_hash
        )

        # Secondary verification: does the DB-stored hash match what was sent?
        db_match = bool(db_stored_hash) and (db_stored_hash == submitted_stored_hash)

        record_verified = transfer_match  # primary signal
        if not record_verified:
            all_records_verified = False

        record_integrity_results.append({
            "record_id":            record_id,
            "record_type":          rec.get('record_type'),
            "version":              rec.get('version'),
            "submitted_stored_hash": submitted_stored_hash,
            "db_stored_hash":       db_stored_hash,
            "recomputed_hash":      recomputed_record_hash,
            "transfer_match":       transfer_match,
            "db_match":             db_match,
            # tampered = data does NOT match the owning hospital's stored hash
            "tampered":             not transfer_match,
            "status": "✓ Verified" if transfer_match else "✗ TAMPERED or CORRUPTED",
        })

    overall_verified = bundle_match and all_records_verified

    # ── Audit log ─────────────────────────────────────────────────────────────
    if overall_verified:
        log_action(
            'HASH_VERIFIED_SUCCESS',
            hospital.hospital_name,
            consent_id,
            extra_info=f"bundle_hash={recomputed_bundle_hash[:16]}…",
        )
        summary = "All records verified. No tampering detected."
    else:
        tampered_ids = [
            r['record_id'] for r in record_integrity_results if r['tampered']
        ]
        log_action(
            'HASH_VERIFIED_FAILED',
            hospital.hospital_name,
            consent_id,
            extra_info=f"Tampered records: {tampered_ids}",
        )
        summary = (
            "WARNING: Integrity check failed. "
            f"{'Bundle hash mismatch. ' if not bundle_match else ''}"
            f"{len(tampered_ids)} record(s) appear tampered: {tampered_ids}"
        )

    return Response({
        "bundle_integrity": {
            "submitted_hash":  submitted_bundle_hash,
            "recomputed_hash": recomputed_bundle_hash,
            "match":           bundle_match,
        },
        "record_integrity":  record_integrity_results,
        "overall_verified":  overall_verified,
        "summary":           summary,
    }, status=200)