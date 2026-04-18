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


class PatientRecordRequestSerializer(serializers.Serializer):
    id = serializers.CharField()
    record_id = serializers.CharField(allow_null=True, required=False)
    status = serializers.CharField()
    status_display = serializers.CharField()
    lab_name = serializers.CharField()
    lab_type = serializers.CharField()
    requested_by = serializers.CharField()
    created_at = serializers.DateTimeField()


class PatientRecordGroupSerializer(serializers.Serializer):
    hospital_id = serializers.CharField()
    hospital_name = serializers.CharField()
    total_requests = serializers.IntegerField()
    pending_requests = serializers.IntegerField()
    completed_requests = serializers.IntegerField()
    requests = PatientRecordRequestSerializer(many=True)


class PatientDashboardStatsSerializer(serializers.Serializer):
    total_requests = serializers.IntegerField()
    pending_requests = serializers.IntegerField()
    completed_requests = serializers.IntegerField()
    hospitals_count = serializers.IntegerField()


class PatientDashboardResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    profile_complete = serializers.BooleanField()
    stats = PatientDashboardStatsSerializer()
    records_by_hospital = PatientRecordGroupSerializer(many=True)
    recent_requests = PatientRecordRequestSerializer(many=True)


class PatientRecordAuditSerializer(serializers.Serializer):
    created_by_id = serializers.CharField(allow_null=True, required=False)
    created_by_name = serializers.CharField(allow_null=True, required=False)
    created_by_role = serializers.CharField(allow_null=True, required=False)
    created_by_staff_code = serializers.CharField(allow_null=True, required=False)
    created_at = serializers.DateTimeField()
    latest_updated_by_id = serializers.CharField(allow_null=True, required=False)
    latest_updated_by_name = serializers.CharField(allow_null=True, required=False)
    latest_updated_by_role = serializers.CharField(allow_null=True, required=False)
    latest_updated_by_staff_code = serializers.CharField(allow_null=True, required=False)
    latest_updated_at = serializers.DateTimeField()
    latest_update_reason = serializers.CharField(allow_null=True, required=False)
    selected_version = serializers.IntegerField()
    selected_version_event_type = serializers.CharField()
    selected_version_changed_at = serializers.DateTimeField()
    selected_version_changed_by_name = serializers.CharField(allow_null=True, required=False)
    selected_version_changed_by_role = serializers.CharField(allow_null=True, required=False)
    selected_version_changed_by_staff_code = serializers.CharField(allow_null=True, required=False)
    selected_version_reason = serializers.CharField(allow_null=True, required=False)


class PatientRecordTimelineSerializer(serializers.Serializer):
    version_number = serializers.IntegerField()
    changed_at = serializers.DateTimeField()
    changed_by_id = serializers.CharField()
    changed_by_staff_code = serializers.CharField(allow_null=True, required=False)
    changed_by_name = serializers.CharField()
    changed_by_role = serializers.CharField()
    change_reason = serializers.CharField(allow_null=True, required=False)
    data_snapshot = serializers.ListField()
    is_full_snapshot = serializers.BooleanField()
    event_type = serializers.CharField()


class PatientRecordDetailSerializer(serializers.Serializer):
    record_id = serializers.CharField()
    version = serializers.IntegerField()
    is_latest = serializers.BooleanField(required=False)
    age = serializers.CharField(allow_null=True, required=False)
    gender = serializers.CharField(allow_null=True, required=False)
    custom_field_values = serializers.DictField(child=serializers.CharField(), required=False)


class PatientLabRequestSerializer(serializers.Serializer):
    id = serializers.CharField()
    status = serializers.CharField()
    status_display = serializers.CharField()
    lab_name = serializers.CharField()
    hospital_name = serializers.CharField()
    requested_by = serializers.CharField()
    requested_by_staff_code = serializers.CharField(allow_null=True, required=False)
    diagnosis = serializers.CharField(allow_null=True, required=False)
    treatment_plan = serializers.CharField(allow_null=True, required=False)
    notes = serializers.CharField(allow_null=True, required=False)


class PatientRecordDetailResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    patient = serializers.DictField()
    record = PatientRecordDetailSerializer()
    lab_request = PatientLabRequestSerializer()
    audit = PatientRecordAuditSerializer()
    timeline = PatientRecordTimelineSerializer(many=True)
    custom_field_values = serializers.DictField(required=False)
    lab_custom_field_schema = serializers.ListField(required=False)


class PatientRecordHistoryItemSerializer(serializers.Serializer):
    version_number = serializers.IntegerField()
    changed_at = serializers.DateTimeField()
    changed_by_id = serializers.CharField()
    changed_by_staff_code = serializers.CharField(allow_null=True, required=False)
    changed_by_name = serializers.CharField()
    changed_by_role = serializers.CharField()
    change_reason = serializers.CharField(allow_null=True, required=False)
    data_snapshot = serializers.ListField()
    is_full_snapshot = serializers.BooleanField()
    event_type = serializers.CharField()


class PatientRecordHistoryResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    record_id = serializers.CharField()
    history_count = serializers.IntegerField()
    history = PatientRecordHistoryItemSerializer(many=True)
