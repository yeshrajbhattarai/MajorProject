from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import AuditLog
from hospitals.models import Hospital
from hospitals.authentication import MediChainJWTAuthentication


# Returns filtered audit logs — only accessible by authenticated hospitals.
#! TODO: Restrict logs so each hospital can only see their own actions, not all hospitals

@api_view(['GET'])
@authentication_classes([MediChainJWTAuthentication])
@permission_classes([IsAuthenticated])
def view_logs(request):
    hospital_id = request.user_payload.get('hospital_id')
    if not hospital_id:
        return Response({"error": "Authentication required"}, status=401)

    logs = AuditLog.objects.all()

    severity   = request.GET.get('severity')
    action     = request.GET.get('action')
    consent_id = request.GET.get('consent_id')

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