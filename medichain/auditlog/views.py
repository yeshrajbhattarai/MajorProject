from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import AuditLog
from hospitals.models import Hospital
from django.core.exceptions import ValidationError
# Create your views here.

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



# !__________________LOG VIEW_________________________________________
@api_view(['GET'])
def view_logs(request):
    hospital, error = get_hospital_from_token(request)
    if error:
        return error

    logs = AuditLog.objects.all()

    # optional filters via query params
    severity   = request.GET.get('severity')    # ?severity=CRITICAL
    action     = request.GET.get('action')      # ?action=HASH_MISMATCH
    consent_id = request.GET.get('consent_id')  # ?consent_id=uuid-here

    if severity:
        logs = logs.filter(severity=severity)
    if action:
        logs = logs.filter(action=action)
    if consent_id:
        logs = logs.filter(consent_id=consent_id)

    data = logs.values(
        'log_id', 'action', 'severity',
        'performed_by', 'consent_id',
        'extra_info', 'timestamp'
    )
    return Response(list(data), status=200)
# !__________________LOG VIEW_________________________________________
