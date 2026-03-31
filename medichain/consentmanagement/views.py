from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import ConsentRequest
from .serializers import (
    ConsentRequestSerializer,
    ConsentCreateSerializer,
    PatientDecisionSerializer,
    HospitalDecisionSerializer
)
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from hospitals.models import Hospital
from auditlog.utils import log_action


#? ── HELPER ──────────────────────────────────────────────────────────────────

# Extracts hospital identity from the JWT payload and returns the Hospital object.
#! TODO: Add check for token expiry edge cases if JWT middleware doesn't handle it
def get_hospital_from_payload(request):
    payload = getattr(request, 'user_payload', None)

    if payload is None:
        return None, Response({"error": "Authentication required"}, status=401)

    if payload.get('user_type') != 'hospital':
        return None, Response({"error": "Only hospitals can perform this action"}, status=403)

    if payload.get('account_status') != 'active':
        return None, Response({"error": "Hospital account is not active"}, status=403)

    try:
        hospital = Hospital.objects.get(id=payload.get('hospital_id'))
    except Hospital.DoesNotExist:
        return None, Response({"error": "Hospital not found"}, status=401)

    return hospital, None


#? ── HOSPITAL DIRECTORY ───────────────────────────────────────────────────────

# Returns all active hospitals except the requesting one — used for selecting a target hospital.
#! TODO: Add pagination when hospital count grows large
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hospital_directory(request):
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    hospitals = Hospital.objects.filter(
        account_status='active'
    ).exclude(
        hospital_name=hospital.hospital_name
    ).values('hospital_name', 'city', 'state')

    return Response(list(hospitals), status=200)


#? ── CONSENT MANAGEMENT APIs ──────────────────────────────────────────────────
# Creates a new consent request — requesting hospital is taken from token, not request body.
#! TODO: Notify the patient and owning hospital when a new request is created
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_consent(request):
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


# Returns all consent records — for development and admin inspection only.
#! TODO: Remove or restrict behind admin-only auth before production
@api_view(['GET'])
@permission_classes([AllowAny])
def view_consent(request):
    consents = ConsentRequest.objects.all().order_by('-created_at')
    serializer = ConsentRequestSerializer(consents, many=True)
    return Response(serializer.data)


# Returns all consent requests sent by the authenticated hospital.
#! TODO: Add date range filtering support
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sent_requests(request):
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    consents = ConsentRequest.objects.filter(
        requesting_hospital=hospital.hospital_name
    ).order_by('-created_at')
    serializer = ConsentRequestSerializer(consents, many=True)
    return Response(serializer.data)


# Returns all consent requests received by the authenticated hospital.
#! TODO: Add date range filtering support
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def received_requests(request):
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    consents = ConsentRequest.objects.filter(
        requested_to_hospital=hospital.hospital_name
    ).order_by('-created_at')
    serializer = ConsentRequestSerializer(consents, many=True)
    return Response(serializer.data)


# Returns full details of a single consent request by ID.
#! TODO: Add auth so only involved hospitals or the patient can view this
@api_view(['GET'])
@permission_classes([AllowAny])
def consent_detail(request, consent_id):
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)
    serializer = ConsentRequestSerializer(consent)
    return Response(serializer.data)


# Allows the patient to approve or reject a pending consent request.
#! TODO: Add patient JWT authentication — currently this endpoint has no auth
@api_view(['PATCH'])
@permission_classes([AllowAny])
def patient_decision(request, consent_id):
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if consent.request_status != 'PENDING':
        return Response({"error": "Consent already finalized"}, status=400)

    if consent.patient_choice != 'PENDING':
        return Response({"error": "Patient already responded"}, status=400)

    serializer = PatientDecisionSerializer(consent, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        action = 'PATIENT_APPROVED' if request.data.get('patient_choice') == 'APPROVED' else 'PATIENT_REJECTED'
        log_action(action, f"Patient of consent {consent_id}", consent.consent_id)
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


# Allows the owning hospital to approve or reject — verified against token identity.
#! TODO: Notify the requesting hospital once a decision is made
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def hospital_decision(request, consent_id):
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if hospital.hospital_name != consent.requested_to_hospital:
        return Response({"error": "Unauthorized - you are not the owner hospital"}, status=403)

    if consent.request_status != 'PENDING':
        return Response({"error": "Consent already finalized"}, status=400)

    if consent.hospital_choice != 'PENDING':
        return Response({"error": "Hospital already responded"}, status=400)

    serializer = HospitalDecisionSerializer(consent, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        action = 'HOSPITAL_APPROVED' if request.data.get('hospital_choice') == 'APPROVED' else 'HOSPITAL_REJECTED'
        log_action(action, hospital.hospital_name, consent.consent_id)
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


# Deletes a pending consent — only the hospital that created it can delete it.
#! TODO: Add a soft delete option to preserve audit history instead of hard delete
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_consent(request, consent_id):
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error

    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if hospital.hospital_name != consent.requesting_hospital:
        return Response({"error": "Unauthorized - only requesting hospital can delete"}, status=403)

    if consent.request_status != 'PENDING':
        return Response({"error": "Cannot delete approved/rejected consent"}, status=400)

    log_action('CONSENT_DELETED', hospital.hospital_name, consent.consent_id,
        extra_info=f"Consent between {consent.requesting_hospital} and {consent.requested_to_hospital}")
    consent.delete()
    return Response({"message": "Consent deleted successfully"}, status=200)


#? ── HOSPITAL API COMMUNICATION ───────────────────────────────────────────────

# Fetches a patient record after a 4-step authorization check — auth, consent exists, approved, requester matches.
#! TODO: Replace dummy record with real fetch from teammate's medical records module
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fetch_record(request, consent_id):
    hospital, error = get_hospital_from_payload(request)
    if error:
        return error
    log_action('RECORD_ACCESS_ATTEMPT', hospital.hospital_name, consent_id)

    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if consent.request_status != 'APPROVED':
        return Response({"error": "Consent not approved"}, status=403)

    if hospital.hospital_name != consent.requesting_hospital:
        return Response({"error": "Unauthorized hospital"}, status=403)

    dummy_record = {
        "patient_id": consent.patient_id,
        "diagnosis": "Hypertension",
        "treatment": "Lifestyle modification + Medication",
        "owner_hospital": consent.requested_to_hospital
    }
    log_action('RECORD_ACCESS_SUCCESS', hospital.hospital_name, consent.consent_id)
    return Response(dummy_record, status=200)