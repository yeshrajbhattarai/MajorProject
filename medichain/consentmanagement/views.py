from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ConsentRequest
from .models import HospitalIdentity
from .serializers import ConsentRequestSerializer, ConsentCreateSerializer, PatientDecisionSerializer, HospitalDecisionSerializer
from django.shortcuts import get_object_or_404
# _______________________________________________________________________________CONSENT_MANAGEMENT_APIs

@api_view(['POST'])
def create_consent(request):
    serializer = ConsentCreateSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)

    return Response(serializer.errors, status=400)

@api_view(['GET'])
def view_consent(request):
    consents = ConsentRequest.objects.all().order_by('-created_at')
    serializer = ConsentRequestSerializer(consents, many = True)
    return Response(serializer.data)
# __________________________________Request sent by a hospital
@api_view(['GET'])
def sent_requests(request):
    # For now, well use hospital name from URL parameter
    # Later we'll get it from logged-in user
    hospital_name = request.GET.get('hospital_name')  # Get from URL like ?hospital_name=Apollo
    
    if not hospital_name:
        return Response({"error": "Please provide hospital_name"}, status=400)
    
    # Filter consents where THIS hospital is the requester in order
    consents = ConsentRequest.objects.filter(
        requesting_hospital=hospital_name
    ).order_by('-created_at')
    serializer = ConsentRequestSerializer(consents, many=True)
    return Response(serializer.data)

# __________________________________Request Recieved by a hospital
@api_view(['GET'])
def received_requests(request):
    hospital_name = request.GET.get('hospital_name')
    
    if not hospital_name:
        return Response({"error": "Please provide hospital_name"}, status=400)
    
    # Filter consents where THIS hospital owns the record
    consents = ConsentRequest.objects.filter(
        requested_to_hospital=hospital_name
    ).order_by('-created_at')
    serializer = ConsentRequestSerializer(consents, many=True)
    return Response(serializer.data)

# __________________________________Single detail of consent
@api_view(['GET'])
def consent_detail(request, consent_id):
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)
    serializer = ConsentRequestSerializer(consent)
    return Response(serializer.data)
    
    
# __________________________________What patient is choosing?
@api_view(['PATCH'])  # patch is used for updating
def patient_decision(request, consent_id):
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if consent.request_status != 'PENDING':
        return Response(
            {"error": "Consent already finalized"},
            status=400
        )

    if consent.patient_choice != 'PENDING':
        return Response(
            {"error": "Patient already responded"},
            status=400
        )

    serializer = PatientDecisionSerializer(
        consent, data=request.data, partial=True
    )

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)

    return Response(serializer.errors, status=400)



# __________________________________What owner hospital is choosing?

@api_view(['PATCH'])
def hospital_decision(request, consent_id):
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if consent.request_status != 'PENDING':
        return Response(
            {"error": "Consent already finalized"},
            status=400
        )

    if consent.hospital_choice != 'PENDING':
        return Response(
            {"error": "Hospital already responded"},
            status=400
        )

    serializer = HospitalDecisionSerializer(
        consent, data=request.data, partial=True
    )

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)

    return Response(serializer.errors, status=400)
    
    
# __________________________________delete - only PENDING request possible
@api_view(['DELETE'])
def delete_consent(request, consent_id):
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if consent.request_status != 'PENDING':
        return Response(
            {"error": "Cannot delete approved/rejected consent"},
            status=400
        )

    consent.delete()
    return Response(
        {"message": "Consent deleted successfully"},
        status=200
    )
# _______________________________________________________________________________HOSPITAL_API_COMMUNICATION
@api_view(['GET'])
def fetch_record(request, consent_id):
    consent = get_object_or_404(ConsentRequest, consent_id=consent_id)

    if consent.request_status != 'APPROVED':
        return Response(
            {"error": "Consent not approved"},
            status=403  
        )
        # ? this line deals with authorization
    auth_header = request.headers.get('Authorization') #* extracts header
    if not auth_header or not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid token"}, status=401)
    
    token = auth_header.split(" ")[1]
    
    hospital = HospitalIdentity.objects.filter(api_token=token).first() #* validate identity of the hospitals
    
    if not hospital: 
        return Response({"error": "Invalid hospital token"}, status=403)
       

    if hospital.name != consent.requesting_hospital: #* ensure the current hospital Matches Requesting Hospital
            return Response({"error": "Unauthorized hospital"}, status=403)
         # ? this line deals with authorization
    # !needs to be updated by real records
    dummy_record = {
        "patient_id": consent.patient_id,
        "diagnosis": "Hypertension",
        "treatment": "Lifestyle modification + Medication",
        "owner_hospital": consent.requested_to_hospital
    } # !needs to be updated by real records

    return Response(dummy_record, status=200)