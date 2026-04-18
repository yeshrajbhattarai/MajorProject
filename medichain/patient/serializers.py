import re

from rest_framework import serializers


EMAIL_REGEX = r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$'
INDIA_MOBILE_REGEX = r'^[6-9]\d{9}$'


class PatientRegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=10)
    password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match'})
        return attrs

    def validate_phone(self, value):
        cleaned = (value or '').replace(' ', '').strip()
        if not re.match(INDIA_MOBILE_REGEX, cleaned):
            raise serializers.ValidationError('Enter a valid 10-digit Indian mobile number')
        return cleaned


class PatientLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PatientProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=10, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.ChoiceField(choices=['Male', 'Female', 'Other'], required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    blood_group = serializers.ChoiceField(
        choices=['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
        required=False,
        allow_blank=True,
    )
    gov_id_type = serializers.ChoiceField(choices=['aadhar', 'voter'], required=False, allow_blank=True)
    gov_id_number = serializers.CharField(required=False, allow_blank=True)


class PatientPasswordUpdateSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs.get('new_password') != attrs.get('confirm_new_password'):
            raise serializers.ValidationError({'confirm_new_password': 'Passwords do not match'})
        return attrs
