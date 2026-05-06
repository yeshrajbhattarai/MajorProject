import re

from rest_framework import serializers
from .models import (
    Hospital,
    HospitalUser,
    Patient,
    Lab,
    LabRequest,
    LabRequestRevision,
    MedicalRecordMeta,
)


INDIA_MOBILE_REGEX = r'^[6-9]\d{9}$'


def _validate_indian_mobile(value):
    if not re.match(INDIA_MOBILE_REGEX, value):
        raise serializers.ValidationError('Enter a valid 10-digit Indian mobile number')
    return value


class StaffContactValidationMixin:
    def validate_email(self, value):
        normalized = value.lower()
        if HospitalUser.objects.filter(email=normalized).exists():
            raise serializers.ValidationError('A staff member with this email already exists')
        return normalized

    def validate_phone(self, value):
        _validate_indian_mobile(value)
        if HospitalUser.objects.filter(phone=value).exists():
            raise serializers.ValidationError('This phone number is already registered')
        return value


# ─── Hospital Serializers ─────────────────────────────────────────────────────

# used when returning hospital data to API — never expose password_hash
class HospitalSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Hospital
        fields = [
            'id', 'hospital_name', 'email', 'contact_number',
            'account_status', 'license_number', 'address',
            'city', 'state', 'country', 'created_at',
        ]


# used for hospital registration — accepts all required fields
class HospitalRegisterSerializer(serializers.Serializer):
    hospital_name    = serializers.CharField(max_length=255)
    email            = serializers.EmailField()
    contact_number   = serializers.CharField(max_length=10)
    password         = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    # validate both passwords match
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match'})
        return data

    # validate Indian mobile number format
    def validate_contact_number(self, value):
        _validate_indian_mobile(value)
        if Hospital.objects.filter(contact_number=value).exists():
            raise serializers.ValidationError('This contact number is already registered')
        return value

    # validate email is not already registered
    def validate_email(self, value):
        if Hospital.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError('This email is already registered')
        return value.lower()


# ─── HospitalUser Serializers ─────────────────────────────────────────────────

# used when returning staff data — never expose password_hash
class HospitalUserSerializer(serializers.ModelSerializer):
    hospital_name = serializers.CharField(source='hospital.hospital_name', read_only=True)

    class Meta:
        model  = HospitalUser
        fields = [
            'id', 'full_name', 'email', 'phone', 'employee_id',
            'role', 'specialization', 'status', 'hospital_name',
            'date_of_birth', 'gender', 'home_address', 'years_experience',
            'license_number', 'bio', 'profile_photo', 'created_at',
        ]


# used when hospital admin adds a new doctor
class AddDoctorSerializer(StaffContactValidationMixin, serializers.Serializer):
    full_name      = serializers.CharField(max_length=255)
    email          = serializers.EmailField()
    phone          = serializers.CharField(max_length=10)
    employee_id    = serializers.CharField(max_length=50)
    specialization = serializers.CharField(max_length=255)

# used when hospital admin adds a new nurse
class AddNurseSerializer(StaffContactValidationMixin, serializers.Serializer):
    full_name   = serializers.CharField(max_length=255)
    email       = serializers.EmailField()
    phone       = serializers.CharField(max_length=10)
    employee_id = serializers.CharField(max_length=50)

# used when hospital admin adds a new technician
class AddTechnicianSerializer(StaffContactValidationMixin, serializers.Serializer):
    full_name   = serializers.CharField(max_length=255)
    email       = serializers.EmailField()
    phone       = serializers.CharField(max_length=10)
    employee_id = serializers.CharField(max_length=50)

# ─── Patient Serializers ──────────────────────────────────────────────────────

# used when returning patient data — gov_id_number is never exposed, only masked
class PatientSerializer(serializers.ModelSerializer):
    registered_by_name = serializers.CharField(source='registered_by.hospital_name', read_only=True)
    gov_id_type_display = serializers.CharField(source='get_gov_id_type_display', read_only=True)

    class Meta:
        model  = Patient
        fields = [
            'id', 'gov_id_type', 'gov_id_type_display', 'full_name',
            'gender', 'phone', 'email', 'address', 'date_of_birth',
            'blood_group', 'profile_photo', 'registered_by_name',
            'registered_by_self', 'is_active', 'created_at',
        ]


# used when hospital admin registers a new patient
class AddPatientSerializer(serializers.Serializer):
    gov_id_type   = serializers.ChoiceField(choices=[('aadhar', 'Aadhar Card'), ('voter', 'Voter ID')])
    gov_id_number = serializers.CharField()
    full_name     = serializers.CharField(max_length=255)
    gender        = serializers.ChoiceField(choices=['Male', 'Female', 'Other'], required=False, allow_blank=True)
    phone         = serializers.CharField(max_length=10, required=False, allow_blank=True)
    email         = serializers.EmailField(required=True)
    address       = serializers.CharField(required=False, allow_blank=True)

    def validate_phone(self, value):
        if value:
            _validate_indian_mobile(value)
        return value

    def validate_email(self, value):
        normalized = value.lower()
        if Patient.objects.filter(email=normalized).exists():
            raise serializers.ValidationError('A patient with this email already exists')
        return normalized


# ─── Lab Serializers ──────────────────────────────────────────────────────────

class LabSerializer(serializers.ModelSerializer):
    hospital_name = serializers.CharField(source='hospital.hospital_name', read_only=True)

    class Meta:
        model  = Lab
        fields = ['id', 'hospital_name', 'lab_type', 'name', 'custom_field_schema', 'is_active', 'created_at']


class CreateLabSerializer(serializers.Serializer):
    lab_type = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=255)
    custom_field_schema = serializers.JSONField(required=False)


# ─── Lab Request Serializers ──────────────────────────────────────────────────

class LabRequestSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    doctor_name = serializers.CharField(source='requested_by.full_name', read_only=True)
    lab_name = serializers.CharField(source='lab.name', read_only=True)

    lab = LabSerializer(read_only=True)

    class Meta:
        model = LabRequest
        fields = [
            'id',
            'patient_name',
            'doctor_name',
            'lab_name',
            'lab',

            'status',
            'chest_pain_type',
            'diagnosis',
            'treatment_plan',
            'notes',
            'custom_field_values',
            'created_at',
            'completed_at',
        ]


class SendToLabSerializer(serializers.Serializer):
    lab_id = serializers.CharField()
    chest_pain_type = serializers.CharField()
    diagnosis = serializers.CharField()
    treatment_plan = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True)
    custom_field_values = serializers.JSONField(required=False)


class DoctorReassessSerializer(serializers.Serializer):
    chest_pain_type = serializers.CharField()
    diagnosis = serializers.CharField()
    treatment_plan = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()
    custom_field_values = serializers.JSONField(required=False)


# ─── Lab Request Revision Serializer ──────────────────────────────────────────

class LabRequestRevisionSerializer(serializers.ModelSerializer):
    revised_by_name = serializers.CharField(source='revised_by.full_name', read_only=True)

    class Meta:
        model  = LabRequestRevision
        fields = [
            'id', 'lab_request_id', 'revised_by_name', 'changed_fields',
            'reason', 'created_at',
        ]


# ─── Medical Record Serializer –────────────────────────────────────────────────

class MedicalRecordMetaSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    lab_name = serializers.SerializerMethodField()
    record_type_display = serializers.CharField(source='get_record_type_display', read_only=True)
    recorded_by_name = serializers.SerializerMethodField()

    def get_patient_name(self, obj):
        if obj.lab_request and obj.lab_request.patient:
            return obj.lab_request.patient.full_name
        patient = Patient.objects.filter(id=obj.patient_id).only('full_name').first()
        return patient.full_name if patient else None

    def get_lab_name(self, obj):
        if obj.lab_request and obj.lab_request.lab:
            return obj.lab_request.lab.name
        return 'Medical Record' if obj.record_type == MedicalRecordMeta.RECORD_TYPE_MEDICAL else None

    def get_recorded_by_name(self, obj):
        try:
            user = HospitalUser.objects.get(id=obj.recorded_by_id)
            return user.full_name
        except HospitalUser.DoesNotExist:
            return 'Unknown User'

    class Meta:
        model  = MedicalRecordMeta
        fields = [
            'record_id', 'record_type', 'record_type_display', 'patient_name', 'lab_name', 'recorded_by_name',
            'version', 'custom_field_values', 'created_at', 'updated_at',
        ]


class CreateMedicalRecordSerializer(serializers.Serializer):
    age = serializers.IntegerField()
    gender = serializers.CharField()
    technician_change_reason = serializers.CharField(required=False, allow_blank=True)
    custom_field_values = serializers.JSONField(required=False)