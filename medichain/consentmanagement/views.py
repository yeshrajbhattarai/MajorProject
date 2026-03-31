from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ConsentRequest
from .serializers import (
    ConsentRequestSerializer,
    ConsentCreateSerializer,
    PatientDecisionSerializer,
    HospitalDecisionSerializer
)
from django.shortcuts import get_object_or_404
#! Samarpans Model Testing
from hospitals.models import Hospital
from django.core.exceptions import ValidationError

# ! Auditlog module
from auditlog.utils import log_action

#? ── HELPER ──────────────────────────────────────────────────────────────────
def get_hospital_from_token(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, Response({"error": "Missing or invalid token"}, status=401)
    token = auth_header.split(" ")[1]
    try:
        hospital = Hospital.objects.get(api_key=token)
    except (Hospital.DoesNotExist, ValidationError):
        return None, Response({"error": "Invalid hospital token"}, status=401)
    return hospital, None


@api_view(['GET'])
def hospital_directory(request):
    hospital, error = get_hospital_from_token(request)
    if error:
        return error
    
    hospitals = Hospital.objects.filter(
        account_status='active'
    ).exclude(
        hospital_name=hospital.hospital_name  # hide my own hospital...
    ).values('hospital_name', 'city', 'state')
    
    return Response(list(hospitals), status=200)



#? ── CONSENT MANAGEMENT APIs ──────────────────────────────────────────────────

@api_view(['POST'])
def create_consent(request):
    hospital, error = get_hospital_from_token(request)
    if error:
        return error

    data = request.data.copy()
    data['requesting_hospital'] = hospital.hospital_name  #! override with real hospital name

    serializer = ConsentCreateSerializer(data=data)
    if serializer.is_valid():
        consent = serializer.save()
        log_action('CONSENT_CREATED', hospital.hospital_name, consent.consent_id)
        return Response(ConsentRequestSerializer(consent).data, status=201)  #* full object back
    return Response(serializer.errors, status=400)


@api_view(['GET'])
def view_consent(request):
    #! Dev only - not for production
    consents = ConsentRequest.objects.all().order_by('-created_at')
    serializer = ConsentRequestSerializer(consents, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def sent_requests(request):
    hospital, error = get_hospital_from_token(request)
    if error:
        return error

    consents = ConsentRequest.objects.filter(
        requesting_hospital=hospital.hospital_name
    ).order_by('-created_at')
    serializer = ConsentRequestSerializer(consents, many=True)
    return Response(serializer.data)



@api_view(['GET'])
def received_requests(request):
    hospital, error = get_hospital_from_token(request)
    if error:
        return error

    consents = ConsentRequest.objects.filter(
        requested_to_hospital=hospital.hospital_name
    ).order_by('-created_at')
    serializer = ConsentRequestSerializer(consents, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def consent_detail(request, consent_id):
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)
    serializer = ConsentRequestSerializer(consent)
    return Response(serializer.data)


@api_view(['PATCH'])
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


@api_view(['PATCH'])
def hospital_decision(request, consent_id):
    hospital, error = get_hospital_from_token(request)  # add this
    if error:
        return error

    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if hospital.hospital_name != consent.requested_to_hospital:  # add this security check
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

@api_view(['DELETE'])
def delete_consent(request, consent_id):
    hospital, error = get_hospital_from_token(request)
    if error:
        return error

    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    # only requesting hospital can delete their own consent
    if hospital.hospital_name != consent.requesting_hospital:
        return Response({"error": "Unauthorized - only requesting hospital can delete"}, status=403)

    if consent.request_status != 'PENDING':
        return Response({"error": "Cannot delete approved/rejected consent"}, status=400)

    log_action('CONSENT_DELETED', hospital.hospital_name, consent.consent_id,
        extra_info=f"Consent between {consent.requesting_hospital} and {consent.requested_to_hospital}")
    consent.delete()
    return Response({"message": "Consent deleted successfully"}, status=200)


#? ── HOSPITAL API COMMUNICATION ───────────────────────────────────────────────

@api_view(['GET'])
def fetch_record(request, consent_id):
    #* Step 1 - auth first (don't leak consent info to unauthenticated callers)
    hospital, error = get_hospital_from_token(request)
    if error:
        return error
    log_action('RECORD_ACCESS_ATTEMPT', hospital.hospital_name, consent_id)
    #* Step 2 - get the consent
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    #* Step 3 - check consent is approved
    if consent.request_status != 'APPROVED':
        return Response({"error": "Consent not approved"}, status=403)

    #* Step 4 - ensure requesting hospital matches token identity
    if hospital.hospital_name != consent.requesting_hospital:
        return Response({"error": "Unauthorized hospital"}, status=403)

    #! TODO: replace with real record fetch
    dummy_record = {
        "patient_id": consent.patient_id,
        "diagnosis": "Hypertension",
        "treatment": "Lifestyle modification + Medication",
        "owner_hospital": consent.requested_to_hospital
    }
    log_action('RECORD_ACCESS_SUCCESS', hospital.hospital_name, consent.consent_id)
    return Response(dummy_record, status=200)