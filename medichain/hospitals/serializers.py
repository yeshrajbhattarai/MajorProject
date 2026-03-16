from rest_framework import serializers
from .models import Hospital, HospitalUser, Patient


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
        import re
        if not re.match(r'^[6-9]\d{9}$', value):
            raise serializers.ValidationError('Enter a valid 10-digit Indian mobile number')
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
class AddDoctorSerializer(serializers.Serializer):
    full_name      = serializers.CharField(max_length=255)
    email          = serializers.EmailField()
    phone          = serializers.CharField(max_length=10)
    employee_id    = serializers.CharField(max_length=50)
    specialization = serializers.CharField(max_length=255)

    def validate_email(self, value):
        if HospitalUser.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError('A staff member with this email already exists')
        return value.lower()

    def validate_phone(self, value):
        import re
        if not re.match(r'^[6-9]\d{9}$', value):
            raise serializers.ValidationError('Enter a valid 10-digit Indian mobile number')
        if HospitalUser.objects.filter(phone=value).exists():
            raise serializers.ValidationError('This phone number is already registered')
        return value


# used when hospital admin adds a new nurse
class AddNurseSerializer(serializers.Serializer):
    full_name   = serializers.CharField(max_length=255)
    email       = serializers.EmailField()
    phone       = serializers.CharField(max_length=10)
    employee_id = serializers.CharField(max_length=50)

    def validate_email(self, value):
        if HospitalUser.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError('A staff member with this email already exists')
        return value.lower()

    def validate_phone(self, value):
        import re
        if not re.match(r'^[6-9]\d{9}$', value):
            raise serializers.ValidationError('Enter a valid 10-digit Indian mobile number')
        if HospitalUser.objects.filter(phone=value).exists():
            raise serializers.ValidationError('This phone number is already registered')
        return value


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
    email         = serializers.EmailField(required=False, allow_blank=True)
    address       = serializers.CharField(required=False, allow_blank=True)

    def validate_phone(self, value):
        import re
        if value and not re.match(r'^[6-9]\d{9}$', value):
            raise serializers.ValidationError('Enter a valid 10-digit Indian mobile number')
        return value

    def validate_email(self, value):
        return value.lower() if value else value