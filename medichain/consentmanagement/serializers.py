from rest_framework import serializers
from .models import ConsentRequest
from hospitals.models import Hospital

# validates the consent's -  requested_to_hospital matches the one which is in my db
def validate_requested_to_hospital(self, value):
    if not Hospital.objects.filter(hospital_name=value).exists():
        raise serializers.ValidationError("This hospital is not registered in MediChain")
    return value
class ConsentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentRequest
        fields = '__all__'
        read_only_fields = [
            'consent_id',
            'request_status',
            'created_at',
            'updated_at'
        ]


class ConsentCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = ConsentRequest
        fields = [
            'patient_id',
            'requesting_hospital',
            'requested_to_hospital',
            'record_id'
        ]
        
    
    
    def validate(self, data):
        if data['requesting_hospital'] == data['requested_to_hospital']:
            raise serializers.ValidationError(
                "Cannot request record from same hospital"
            )
        return data


class PatientDecisionSerializer(serializers.ModelSerializer):

    class Meta:
        model = ConsentRequest
        fields = ['patient_choice']

    def validate_patient_choice(self, value):
        if value not in ['APPROVED', 'REJECTED']:
            raise serializers.ValidationError(
                "Invalid choice. Use APPROVED or REJECTED"
            )
        return value


class HospitalDecisionSerializer(serializers.ModelSerializer):

    class Meta:
        model = ConsentRequest
        fields = ['hospital_choice']

    def validate_hospital_choice(self, value):
        if value not in ['APPROVED', 'REJECTED']:
            raise serializers.ValidationError(
                "Invalid choice. Use APPROVED or REJECTED"
            )
        return value