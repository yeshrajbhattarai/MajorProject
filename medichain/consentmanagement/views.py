from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ConsentRequest
from .serializers import ConsentRequestSerializer

# Create your views here.

@api_view(['POST'])
def create_consent(request):
    serializer = ConsentRequestSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
def view_consent(request):
    consents = ConsentRequest.objects.all()
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
    
    # Filter consents where THIS hospital is the requester
    consents = ConsentRequest.objects.filter(requesting_hospital=hospital_name)
    serializer = ConsentRequestSerializer(consents, many=True)
    return Response(serializer.data)

# __________________________________Request Recieved by a hospital
@api_view(['GET'])
def received_requests(request):
    hospital_name = request.GET.get('hospital_name')
    
    if not hospital_name:
        return Response({"error": "Please provide hospital_name"}, status=400)
    
    # Filter consents where THIS hospital owns the record
    consents = ConsentRequest.objects.filter(requested_to_hospital=hospital_name)
    serializer = ConsentRequestSerializer(consents, many=True)
    return Response(serializer.data)

# __________________________________Single detail of consent
@api_view(['GET'])
def consent_detail(request, consent_id):
    try:
        consent = ConsentRequest.objects.get(consent_id=consent_id)
        serializer = ConsentRequestSerializer(consent)
        return Response(serializer.data)
    except ConsentRequest.DoesNotExist:
        return Response({"error": "Consent not found"}, status=404)
    
    
# __________________________________What patient is choosing?
@api_view(['PATCH'])  # patch is used for updating
def patient_decision(request, consent_id):
    try:
        consent = ConsentRequest.objects.get(consent_id=consent_id)
        
        # Get patientdecision from request
        decision = request.data.get('patient_choice')  # Should be aPPROVED or REJECTED
        
        if decision not in ['APPROVED', 'REJECTED']:
            return Response({"error": "Invalid choice. Use APPROVED or REJECTED"}, status=400)
        
        # Update patient choice
        consent.patient_choice = decision
        consent.save()  # This automatically triggers your status logic!
        
        serializer = ConsentRequestSerializer(consent)
        return Response(serializer.data)
        
    except ConsentRequest.DoesNotExist:
        return Response({"error": "Consent not found"}, status=404)
    
    
# __________________________________What owner hospital is choosing?
@api_view(['PATCH'])
def hospital_decision(request, consent_id):
    try:
        consent = ConsentRequest.objects.get(consent_id=consent_id)
        
        # Get hospital's decision
        decision = request.data.get('hospital_choice')
        
        if decision not in ['APPROVED', 'REJECTED']:
            return Response({"error": "Invalid choice. Use APPROVED or REJECTED"}, status=400)
        
        # Update hospital choice
        consent.hospital_choice = decision
        consent.save()  # Status updates automatically!
        
        serializer = ConsentRequestSerializer(consent)
        return Response(serializer.data)
        
    except ConsentRequest.DoesNotExist:
        return Response({"error": "Consent not found"}, status=404)
    
    
# __________________________________delete - only PENDING request possible
@api_view(['DELETE'])
def delete_consent(request, consent_id):
    try:
        consent = ConsentRequest.objects.get(consent_id=consent_id)
        
        if consent.request_status != 'PENDING':
            return Response({"error": "Cannot delete approved/rejected consent"}, status=400)
        
        consent.delete()
        return Response({"message": "Consent deleted successfully"}, status=200)
        
    except ConsentRequest.DoesNotExist:
        return Response({"error": "Consent not found"}, status=404)