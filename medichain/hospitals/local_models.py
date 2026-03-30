import uuid

from django.db import models


class MedicalRecord(models.Model):
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]

    ECG_CHOICES = [
        ('normal', 'Normal'),
        ('st_t_abnormality', 'ST-T abnormality'),
        ('lvh', 'LVH'),
    ]

    row_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record_id = models.UUIDField(db_index=True)
    lab_request_id = models.UUIDField(db_index=True)
    patient_id = models.UUIDField(db_index=True)
    hospital_id = models.UUIDField(db_index=True)
    recorded_by_id = models.UUIDField(db_index=True)
    version = models.IntegerField(default=1)
    is_latest = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    age = models.IntegerField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    blood_pressure_systolic = models.IntegerField()
    blood_pressure_diastolic = models.IntegerField()
    cholesterol = models.IntegerField()
    blood_glucose = models.FloatField()
    heart_rate = models.IntegerField()
    ecg_result = models.CharField(max_length=32, choices=ECG_CHOICES)
    sha256_hash = models.CharField(max_length=64)

    class Meta:
        app_label = 'hospital_local'
        db_table = 'medical_records'
        ordering = ['-created_at']


class MedicalRecordVersion(models.Model):
    version_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record_id = models.UUIDField(db_index=True)
    version_number = models.IntegerField()
    data_snapshot = models.JSONField()
    changed_by_id = models.UUIDField(db_index=True)
    change_reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'hospital_local'
        db_table = 'medical_record_versions'
        ordering = ['-changed_at']
