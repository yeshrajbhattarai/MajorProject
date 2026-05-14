from .models import AuditLog


def log_action(action, performed_by, consent_id=None, extra_info=None, scope_hospitals=None):
    severity = AuditLog.ACTION_SEVERITY_MAP.get(action, 'INFO')

    if scope_hospitals is None:
        scope_hospitals = []
    elif isinstance(scope_hospitals, str):
        scope_hospitals = [scope_hospitals]

    AuditLog.objects.create(
        action       = action,
        severity     = severity,
        performed_by = performed_by,
        consent_id   = consent_id,
        scope_hospitals = scope_hospitals,
        extra_info   = extra_info,
    )