from .models import AuditLog


def log_action(action, performed_by, consent_id=None, extra_info=None):
    severity = AuditLog.ACTION_SEVERITY_MAP.get(action, 'INFO')

    AuditLog.objects.create(
        action       = action,
        severity     = severity,
        performed_by = performed_by,
        consent_id   = consent_id,
        extra_info   = extra_info
    )