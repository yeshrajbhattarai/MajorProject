from django.db import models
import uuid #gives unique long id
class ConsentRequest(models.Model):
    consent_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    patient_id = models.CharField(max_length=50)# whose record is requested
    requesting_hospital = models.CharField(max_length=50)# Hospital that REQUESTS the record
    requested_to_hospital = models.CharField(max_length=50)# Hospital that OWNS the record
    record_id = models.CharField(max_length=50, blank=True, null=True)# this is optional - if any specific record is being requested or not

    patient_choice = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    hospital_choice = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    request_status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def save(self, *args, **kwargs):

        if self.patient_choice == 'APPROVED' and self.hospital_choice == 'APPROVED':
            self.request_status = 'APPROVED'
        elif self.patient_choice == 'REJECTED' or self.hospital_choice == 'REJECTED':
            self.request_status = 'REJECTED'
        else:
            self.request_status = 'PENDING'

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient_id} | {self.requesting_hospital} → {self.requested_to_hospital} | {self.request_status}"
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['patient_id', 'requesting_hospital', 'requested_to_hospital'],
                name='unique_patient_hospital_request'
            )
        ]
        
        


# !secrets.token_hex(32) find research paper 