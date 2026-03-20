import uuid
from django.db import models


class AuditLog(models.Model):

    ACTION_CHOICES = [
        ('CONSENT_CREATED','Consent Created'),
        ('PATIENT_APPROVED','Patient Approved'),
        ('PATIENT_REJECTED','Patient Rejected'),
        ('HOSPITAL_APPROVED','Hospital Approved'),
        ('HOSPITAL_REJECTED','Hospital Rejected'),
        ('CONSENT_DELETED','Consent Deleted'),
        ('RECORD_ACCESS_ATTEMPT','Record Access Attempt'),
        ('RECORD_ACCESS_SUCCESS','Record Access Success'),
        ('HASH_MATCHED','Hash Matched'),
        ('HASH_MISMATCH','Hash Mismatch, Possible Tampering'),
    ]

    SEVERITY_CHOICES = [
        ('INFO','Info'),
        ('WARNING','Warning'),
        ('CRITICAL', 'Critical'),
    ]

    # severity is auto-decided based on action — no manual input needed
    ACTION_SEVERITY_MAP = {
        'CONSENT_CREATED':       'INFO',
        'PATIENT_APPROVED':      'INFO',
        'PATIENT_REJECTED':      'INFO',
        'HOSPITAL_APPROVED':     'INFO',
        'HOSPITAL_REJECTED':     'INFO',
        'CONSENT_DELETED':       'WARNING',
        'RECORD_ACCESS_ATTEMPT': 'WARNING',
        'RECORD_ACCESS_SUCCESS': 'INFO',
        'HASH_MATCHED':          'INFO',
        'HASH_MISMATCH':         'CRITICAL',
    }

    log_id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action       = models.CharField(max_length=50, choices=ACTION_CHOICES)
    severity     = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='INFO')
    performed_by = models.CharField(max_length=255)
    consent_id   = models.UUIDField(null=True, blank=True)
    extra_info   = models.TextField(null=True, blank=True)
    timestamp    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.severity}] {self.action} by {self.performed_by}"