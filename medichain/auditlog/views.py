import uuid

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import AuditLog
from hospitals.models import Hospital
from hospitals.permissions import IsHospitalAdmin


# Returns filtered audit logs — only accessible by authenticated hospitals.
@api_view(['GET'])
@permission_classes([IsHospitalAdmin])
def view_logs(request):
    payload = getattr(request, 'user_payload', None)
    if not payload:
        return Response({"error": "Authentication required"}, status=401)

    hospital_id = payload.get('hospital_id')
    if not hospital_id:
        return Response({"error": "Authentication required"}, status=401)

    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return Response({"error": "Hospital not found"}, status=404)

    logs = AuditLog.objects.filter(
        Q(performed_by=hospital.hospital_name) |
        Q(scope_hospitals__contains=[hospital.hospital_name])
    )

    severity   = request.GET.get('severity')
    action     = request.GET.get('action')
    consent_id = request.GET.get('consent_id')

    if severity:
        logs = logs.filter(severity=severity)
    if action:
        logs = logs.filter(action=action)
    if consent_id:
        try:
            uuid.UUID(consent_id)
        except ValueError:
            return Response({"error": "consent_id must be a valid UUID"}, status=400)
        logs = logs.filter(consent_id=consent_id)

    data = logs.values(
        'log_id', 'action', 'severity',
        'performed_by', 'consent_id', 'scope_hospitals',
        'extra_info', 'timestamp'
    )
    return Response(list(data), status=200)