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
    PatientConsentSerializer,
)
from hospitals.models import Hospital, Patient, MedicalRecordMeta
from hospitals.services import _payload_hash
from hospitals.db_router import clear_hospital_db, set_hospital_db
from hospitals.hospital_db import ensure_db_exists
from hospitals.lab_table_manager import (
    ensure_lab_tables,
    extract_custom_values_from_row,
    fetch_latest_record,
    fetch_record_history,
)
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
    Produce a stable SHA-256 fingerprint of the transferred payload using
    the same canonicalisation rules used at write-time. This ensures the
    bundle-level hash and per-record hash computations are consistent across
    sender, MediChain and receiver.
    """
    # Delegate to the hospital write-time canonicaliser so both write and
    # verify paths use identical JSON canonicalisation.
    return _payload_hash(record_payload)


def _serialize_record_payload(meta: MedicalRecordMeta) -> dict:
    """Return the owning hospital's stored record snapshot for UI display."""
    lab_request = meta.lab_request
    if not lab_request or not lab_request.lab:
        return {
            "record_id": str(meta.record_id),
            "version": meta.version,
            "record_type": meta.record_type,
            "created_at": meta.created_at.isoformat() if meta.created_at else None,
            "updated_at": meta.updated_at.isoformat() if meta.updated_at else None,
            "hospital_name": meta.hospital.hospital_name if meta.hospital else None,
            "patient_id": str(meta.patient_id),
            "recorded_by_id": str(meta.recorded_by_id),
            "lab": None,
            "doctor_inputs": {},
            "measurements": {},
            "custom_field_values": meta.custom_field_values or {},
        }

    hospital_id = str(meta.hospital_id)
    db_alias = ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)
    try:
        ensure_lab_tables(db_alias, lab_request.lab)

        stored_row = fetch_latest_record(db_alias, lab_request.lab, meta.record_id)
        if not stored_row:
            history_rows = list(fetch_record_history(db_alias, lab_request.lab, meta.record_id))
            stored_row = history_rows[-1] if history_rows else None

        custom_field_values = {}
        if stored_row:
            custom_field_values = extract_custom_values_from_row(stored_row, lab_request.lab) or {}

        return {
            "record_id": str(meta.record_id),
            "version": getattr(stored_row, 'version', meta.version),
            "record_type": meta.record_type,
            "created_at": getattr(stored_row, 'created_at', meta.created_at).isoformat() if getattr(stored_row, 'created_at', None) else (meta.created_at.isoformat() if meta.created_at else None),
            "updated_at": getattr(stored_row, 'updated_at', meta.updated_at).isoformat() if getattr(stored_row, 'updated_at', None) else (meta.updated_at.isoformat() if meta.updated_at else None),
            "hospital_name": meta.hospital.hospital_name if meta.hospital else None,
            "patient_id": str(getattr(stored_row, 'patient_id', meta.patient_id)),
            "recorded_by_id": str(getattr(stored_row, 'recorded_by_id', meta.recorded_by_id)),
            "row_id": getattr(stored_row, 'row_id', None),
            "lab": {
                "lab_type": lab_request.lab.lab_type,
                "lab_name": lab_request.lab.name,
            },
            "doctor_inputs": {
                "diagnosis": getattr(stored_row, 'diagnosis', lab_request.diagnosis),
                "treatment_plan": getattr(stored_row, 'treatment_plan', lab_request.treatment_plan),
                "notes": getattr(stored_row, 'notes', lab_request.notes),
                "chest_pain_type": getattr(stored_row, 'chest_pain_type', lab_request.chest_pain_type),
            },
            "measurements": {
                "age": getattr(stored_row, 'age', None),
                "gender": getattr(stored_row, 'gender', None),
            },
            "custom_field_values": custom_field_values or (meta.custom_field_values or {}),
        }
    finally:
        clear_hospital_db()


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

        record_payload = _serialize_record_payload(meta)

        # For medical records, fetch the NurseQueueItem to get attachment files
        attachments = {}
        if meta.record_type == 'medical':
            from hospitals.models import NurseQueueItem
            nurse_item = NurseQueueItem.objects.filter(finalized_record_id=meta.record_id).first()
            if nurse_item:
                if nurse_item.handwritten_file:
                    attachments['handwritten_file_url'] = nurse_item.handwritten_file.url
                if nurse_item.doctor_medical_record_file:
                    attachments['doctor_medical_record_file_url'] = nurse_item.doctor_medical_record_file.url

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
            # Doctor attachment URLs (for medical records)
            "attachments":         attachments,
            "record_payload":      record_payload,
        }

        # Include both hashes in the transfer payload:
        # - local_stored_hash: the write-time hash persisted by the owning hospital
        # - recomputed_hash: freshly recomputed right before transfer from record_payload
        local_stored_hash = meta.sha256_hash
        recomputed_hash = _compute_transfer_hash(record_payload)
        entry["local_stored_hash"] = local_stored_hash
        entry["recomputed_hash"] = recomputed_hash
        # Keep legacy key for backward compatibility with older clients.
        entry["stored_hash"] = local_stored_hash

        records.append(entry)

    # The transfer bundle is the object we will hash end-to-end.
    # Include both record data and hash fields so any in-transit mutation is
    # detected by bundle hash verification on the receiver side.
    data_for_hashing = {
        "consent_id":     str(consent.consent_id),
        "patient_id":     str(consent.patient_id),
        "owner_hospital": consent.requested_to_hospital,
        "records":        records,
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

    # Reuse the same row when an earlier request for this pair was rejected.
    patient_id = str(data.get('patient_id', '')).strip()
    requested_to_hospital = str(data.get('requested_to_hospital', '')).strip()
    existing = None
    if patient_id and requested_to_hospital:
        existing = ConsentRequest.objects.filter(
            patient_id=patient_id,
            requesting_hospital=hospital.hospital_name,
            requested_to_hospital=requested_to_hospital,
        ).first()

    if existing:
        if existing.request_status == 'REJECTED':
            record_id = str(data.get('record_id', '')).strip() or None
            existing.record_id = record_id
            existing.patient_choice = 'PENDING'
            existing.hospital_choice = 'PENDING'
            existing.request_status = 'PENDING'
            existing.save()
            log_action(
                'CONSENT_CREATED',
                hospital.hospital_name,
                existing.consent_id,
                extra_info='Re-request created from previously rejected consent',
                scope_hospitals=[existing.requesting_hospital, existing.requested_to_hospital],
            )
            return Response(ConsentRequestSerializer(existing).data, status=200)

        if existing.request_status == 'PENDING':
            return Response(
                {
                    'error': (
                        'A consent request is already pending for this '
                        'patient and hospital pair.'
                    )
                },
                status=400,
            )

        return Response(
            {
                'error': (
                    'A consent for this patient and hospital pair is already '
                    'approved. Create a new pair or revoke the existing flow '
                    'before requesting again.'
                )
            },
            status=400,
        )

    serializer = ConsentCreateSerializer(data=data)
    if serializer.is_valid():
        consent = serializer.save()
        log_action(
            'CONSENT_CREATED',
            hospital.hospital_name,
            consent.consent_id,
            scope_hospitals=[consent.requesting_hospital, consent.requested_to_hospital],
        )
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
        scope_hospitals=[consent.requesting_hospital, consent.requested_to_hospital],
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
    payload = getattr(request, 'user_payload', None)
    if not payload:
        return Response(
            {"error": "Authentication required"},
            status=401
        )

    if payload.get('user_type') != 'patient':
        return Response(
            {"error": "Only patients can perform this action"},
            status=403
        )

    payload_patient_id = str(payload.get('patient_id', '')).strip()
    if not payload_patient_id:
        return Response(
            {"error": "Patient identity missing in token"},
            status=401
        )

    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if payload_patient_id != str(consent.patient_id):
        return Response(
            {"error": "Unauthorized — this consent does not belong to you"},
            status=403
        )

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
        log_action(
            action,
            f"patient:{payload_patient_id}",
            consent.consent_id,
            scope_hospitals=[consent.requesting_hospital, consent.requested_to_hospital],
        )
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
        log_action(
            action,
            hospital.hospital_name,
            consent.consent_id,
            scope_hospitals=[consent.requesting_hospital, consent.requested_to_hospital],
        )
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
                   extra_info=f"Consent status: {consent.request_status}",
                   scope_hospitals=[consent.requesting_hospital, consent.requested_to_hospital])
        return Response(
            {"error": "Consent is not approved. Both the patient and the owning hospital must approve before records can be shared."},
            status=403,
        )

    # ── Step 4: only the requesting hospital may pull ─────────────────────────
    if hospital.hospital_name != consent.requesting_hospital:
        log_action('RECORD_ACCESS_DENIED', hospital.hospital_name, consent_id,
                   extra_info="Caller is not the requesting hospital",
                   scope_hospitals=[consent.requesting_hospital, consent.requested_to_hospital])
        return Response(
            {"error": "Unauthorized — only the requesting hospital can fetch this record"},
            status=403,
        )

    # ── Build the real record bundle ──────────────────────────────────────────
    bundle, bundle_error = _build_record_bundle(consent)
    if bundle_error:
        log_action('RECORD_ACCESS_FAILED', hospital.hospital_name, consent_id,
                   extra_info=bundle_error,
                   scope_hospitals=[consent.requesting_hospital, consent.requested_to_hospital])
        return Response({"error": bundle_error}, status=404)

    log_action(
        'RECORD_ACCESS_SUCCESS',
        hospital.hospital_name,
        consent.consent_id,
        scope_hospitals=[consent.requesting_hospital, consent.requested_to_hospital],
    )

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

        The server recomputes the SHA-256 over the submitted bundle exactly as
        sent by fetch_record, then validates each record using three hashes:
            - local_stored_hash (sent by owning hospital)
            - recomputed_hash   (freshly recomputed by owning hospital at send time)
            - db_stored_hash    (authoritative hash in MediChain MedicalRecordMeta)

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
                "local_stored_hash": "<hex>", // from sending hospital DB
                "recomputed_hash":   "<hex>", // recomputed by sender pre-transfer
                "db_stored_hash":    "<hex>", // MediChain authoritative hash
                "triple_match":      true | false,
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
    # Hash the full records payload exactly as transferred.
    data_for_hashing = {
        "consent_id":     str(consent.consent_id),
        "patient_id":     str(consent.patient_id),
        "owner_hospital": consent.requested_to_hospital,
        "records":        submitted_records,
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
    # Scope the lookup to the owning hospital so we compare against the
    # same MedicalRecordMeta rows that were used when building the bundle.
    stored_meta_map = {}
    for meta in MedicalRecordMeta.objects.filter(
        record_id__in=submitted_record_ids,
        hospital__hospital_name=consent.requested_to_hospital,
    ).order_by('record_id', '-version'):
        key = str(meta.record_id)
        if key not in stored_meta_map:
            stored_meta_map[key] = meta
    # We ordered by record_id, -version and kept the first occurrence per
    # record_id so the dict contains the latest version for each record.

    record_integrity_results = []
    all_records_verified = True

    for rec in submitted_records:
        record_id = rec.get('record_id', '')

        submitted_local_stored_hash = rec.get('local_stored_hash') or rec.get('stored_hash', '')
        submitted_recomputed_hash = rec.get('recomputed_hash', '')
        meta = stored_meta_map.get(record_id)
        db_stored_hash = meta.sha256_hash if meta else None

        local_vs_db_match = bool(db_stored_hash) and (submitted_local_stored_hash == db_stored_hash)
        recomputed_vs_db_match = bool(db_stored_hash) and (submitted_recomputed_hash == db_stored_hash)
        local_vs_recomputed_match = bool(submitted_local_stored_hash) and (
            submitted_local_stored_hash == submitted_recomputed_hash
        )
        triple_match = local_vs_db_match and recomputed_vs_db_match and local_vs_recomputed_match

        record_verified = triple_match
        if not record_verified:
            all_records_verified = False

        record_integrity_results.append({
            "record_id":            record_id,
            "record_type":          rec.get('record_type'),
            "version":              rec.get('version'),
            "local_stored_hash":    submitted_local_stored_hash,
            "recomputed_hash":      submitted_recomputed_hash,
            "db_stored_hash":       db_stored_hash,
            "local_vs_db_match":    local_vs_db_match,
            "recomputed_vs_db_match": recomputed_vs_db_match,
            "local_vs_recomputed_match": local_vs_recomputed_match,
            "triple_match":         triple_match,
            # tampered = any mismatch among sender local hash, sender recompute,
            # and MediChain authoritative hash.
            "tampered":             not triple_match,
            "status": "✓ Verified" if triple_match else "✗ TAMPERED or CORRUPTED",
        })

    overall_verified = bundle_match and all_records_verified

    # ── Audit log ─────────────────────────────────────────────────────────────
    if overall_verified:
        log_action(
            'HASH_VERIFIED_SUCCESS',
            hospital.hospital_name,
            consent_id,
            extra_info=f"bundle_hash={recomputed_bundle_hash[:16]}…",
            scope_hospitals=[consent.requesting_hospital, consent.requested_to_hospital],
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
            scope_hospitals=[consent.requesting_hospital, consent.requested_to_hospital],
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
    
    
    
# PAtient consent
@api_view(['GET'])
@permission_classes([AllowAny])
def patient_consents(request):
    """
    Returns all consent requests belonging to the logged-in patient.
    """

    payload = getattr(request, 'user_payload', None)

    if not payload:
        return Response(
            {"error": "Authentication required"},
            status=401
        )

    if payload.get('user_type') != 'patient':
        return Response(
            {"error": "Only patients can access this endpoint"},
            status=403
        )

    patient_id = payload.get('patient_id')

    consents = ConsentRequest.objects.filter(
        patient_id=patient_id
    ).order_by('-created_at')

    serializer = PatientConsentSerializer(
        consents,
        many=True
    )

    return Response(serializer.data, status=200)