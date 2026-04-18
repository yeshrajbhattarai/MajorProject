from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from hospitals.encryption import decrypt
from hospitals.models import MedicalRecordMeta, Patient
from hospitals.token_utils import get_tokens_for_payload
from hospitals.services import service_get_record_detail, service_get_record_history

from .permissions import IsPatient
from .serializers import (
    PatientLoginSerializer,
    PatientPasswordUpdateSerializer,
    PatientProfileUpdateSerializer,
    PatientRegisterSerializer,
)
from .services import (
    get_missing_profile_fields,
    get_profile_completion_percent,
    group_lab_requests_by_hospital,
    is_profile_complete,
    service_get_patient_dashboard_data,
    service_get_patient_lab_requests,
    service_patient_login,
    service_patient_register,
    service_patient_update_password,
    service_patient_update_profile,
)


def _mask_gov_id(gov_id_number):
    if not gov_id_number:
        return None
    try:
        raw = decrypt(gov_id_number)
    except Exception:
        return None
    if not raw:
        return None
    if len(raw) <= 4:
        return raw
    return ('*' * (len(raw) - 4)) + raw[-4:]


def _get_patient_or_404(patient_id):
    return Patient.objects.filter(id=patient_id).first()


def _profile_gate_response(patient):
    missing_fields = get_missing_profile_fields(patient)
    return Response(
        {
            'success': False,
            'error': 'Complete profile required to access medical records.',
            'profile_complete': False,
            'missing_fields': missing_fields,
            'profile_completion_percent': get_profile_completion_percent(patient),
        },
        status=status.HTTP_403_FORBIDDEN,
    )


class PatientRegisterAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        patient, errors = service_patient_register(
            full_name=d['full_name'].strip(),
            email=d['email'].strip(),
            phone=d['phone'].strip(),
            password=d['password'],
            confirm_password=d['confirm_password'],
        )

        if errors:
            return Response({'success': False, 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                'success': True,
                'message': 'Patient registered successfully. Please login.',
                'patient_id': str(patient.id),
            },
            status=status.HTTP_201_CREATED,
        )


class PatientLoginAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        patient, errors = service_patient_login(
            email=d['email'].strip().lower(),
            password=d['password'],
        )

        if errors:
            http_status = status.HTTP_400_BAD_REQUEST
            if 'password' in errors:
                http_status = status.HTTP_401_UNAUTHORIZED
            if any(k in str(errors).lower() for k in ['inactive']):
                http_status = status.HTTP_403_FORBIDDEN
            return Response({'success': False, 'errors': errors}, status=http_status)

        tokens = get_tokens_for_payload(
            {
                'user_type': 'patient',
                'patient_id': str(patient.id),
                'patient_name': patient.full_name,
            }
        )

        return Response(
            {
                'success': True,
                'role': 'patient',
                'tokens': tokens,
                'patient': {
                    'id': str(patient.id),
                    'full_name': patient.full_name,
                    'email': patient.email,
                    'phone': patient.phone,
                    'registered_by_self': patient.registered_by_self,
                },
            },
            status=status.HTTP_200_OK,
        )


class PatientLogoutAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh', '').strip()
        if not refresh_token:
            return Response({'success': False, 'error': 'refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({'success': False, 'error': 'Invalid refresh token'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)


class PatientDashboardAPI(APIView):
    permission_classes = [IsPatient]

    def get(self, request):
        patient_id = request.user_payload['patient_id']

        patient = _get_patient_or_404(patient_id)
        if not patient:
            return Response({'success': False, 'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        if not is_profile_complete(patient):
            return _profile_gate_response(patient)

        dashboard_data = service_get_patient_dashboard_data(patient_id)
        _, lab_requests = service_get_patient_lab_requests(patient_id)
        grouped_records = group_lab_requests_by_hospital(lab_requests)

        data = {
            'success': True,
            'profile_complete': dashboard_data.get('profile_complete', False),
            'stats': {
                'total_requests': dashboard_data.get('lab_count', 0),
                'pending_requests': dashboard_data.get('pending_labs', 0),
                'completed_requests': dashboard_data.get('completed_labs', 0),
                'hospitals_count': dashboard_data.get('hospitals_count', 0),
            },
            'records_by_hospital': [
                {
                    'hospital_id': group['hospital_id'],
                    'hospital_name': group['hospital_name'],
                    'total_requests': group['total_requests'],
                    'pending_requests': group['pending_requests'],
                    'completed_requests': group['completed_requests'],
                    'requests': [
                        {
                            'id': str(item['request'].id),
                            'record_id': item['record_id'],
                            'status': item['request'].status,
                            'status_display': item['request'].get_status_display(),
                            'lab_name': item['request'].lab.name,
                            'lab_type': item['request'].lab.get_lab_type_display(),
                            'requested_by': item['request'].requested_by.full_name,
                            'created_at': item['request'].created_at,
                        }
                        for item in group['requests']
                    ],
                }
                for group in grouped_records
            ],
            'recent_requests': [
                {
                    'id': str(req.id),
                    'status': req.status,
                    'status_display': req.get_status_display(),
                    'lab_name': req.lab.name,
                    'lab_type': req.lab.get_lab_type_display(),
                    'requested_by': req.requested_by.full_name,
                    'created_at': req.created_at,
                }
                for req in lab_requests[:10]
            ],
        }
        return Response(data, status=status.HTTP_200_OK)


class PatientRecordsAPI(APIView):
    permission_classes = [IsPatient]

    def get(self, request):
        patient_id = request.user_payload['patient_id']
        patient = _get_patient_or_404(patient_id)
        if not patient:
            return Response({'success': False, 'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        if not is_profile_complete(patient):
            return _profile_gate_response(patient)

        dashboard_data = service_get_patient_dashboard_data(patient_id)
        _, lab_requests = service_get_patient_lab_requests(patient_id)
        grouped_records = group_lab_requests_by_hospital(lab_requests)

        return Response(
            {
                'success': True,
                'profile_complete': dashboard_data.get('profile_complete', False),
                'stats': {
                    'total_requests': dashboard_data.get('lab_count', 0),
                    'pending_requests': dashboard_data.get('pending_labs', 0),
                    'completed_requests': dashboard_data.get('completed_labs', 0),
                    'hospitals_count': dashboard_data.get('hospitals_count', 0),
                },
                'records_by_hospital': grouped_records,
            },
            status=status.HTTP_200_OK,
        )


class PatientRecordDetailAPI(APIView):
    permission_classes = [IsPatient]

    def get(self, request, record_id):
        patient_id = request.user_payload['patient_id']
        patient = _get_patient_or_404(patient_id)
        if not patient:
            return Response({'success': False, 'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        if not is_profile_complete(patient):
            return _profile_gate_response(patient)

        meta = MedicalRecordMeta.objects.filter(record_id=record_id, patient_id=patient.id).first()
        if not meta:
            return Response({'success': False, 'error': 'Record not found for your account.'}, status=status.HTTP_404_NOT_FOUND)

        version_number = request.query_params.get('v')
        if version_number:
            try:
                version_number = int(version_number)
            except (TypeError, ValueError):
                return Response({'success': False, 'error': 'Invalid record version requested.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            version_number = None

        record, lab_request, detail_bundle, error = service_get_record_detail(
            record_id=record_id,
            hospital_id=str(meta.hospital_id),
            version_number=version_number,
        )

        if error:
            return Response({'success': False, 'error': error}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                'success': True,
                'patient': {
                    'id': str(patient.id),
                    'full_name': patient.full_name,
                    'email': patient.email,
                    'phone': patient.phone,
                },
                'record': {
                    'record_id': str(record.record_id),
                    'version': record.version,
                    'is_latest': getattr(record, 'is_latest', False),
                    'age': getattr(record, 'age', None),
                    'gender': getattr(record, 'gender', None),
                    'custom_field_values': getattr(record, 'custom_field_values', {}),
                },
                'lab_request': {
                    'id': str(lab_request.id),
                    'status': lab_request.status,
                    'status_display': lab_request.get_status_display(),
                    'lab_name': lab_request.lab.name,
                    'hospital_name': lab_request.lab.hospital.hospital_name,
                    'requested_by': lab_request.requested_by.full_name,
                    'requested_by_staff_code': getattr(lab_request.requested_by, 'employee_id', None),
                    'diagnosis': lab_request.diagnosis,
                    'treatment_plan': lab_request.treatment_plan,
                    'notes': lab_request.notes,
                },
                'audit': detail_bundle['audit'],
                'timeline': detail_bundle['timeline'],
                'custom_field_values': detail_bundle.get('custom_field_values', {}),
                'lab_custom_field_schema': detail_bundle.get('lab_custom_field_schema', []),
            },
            status=status.HTTP_200_OK,
        )


class PatientRecordHistoryAPI(APIView):
    permission_classes = [IsPatient]

    def get(self, request, record_id):
        patient_id = request.user_payload['patient_id']
        patient = _get_patient_or_404(patient_id)
        if not patient:
            return Response({'success': False, 'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        if not is_profile_complete(patient):
            return _profile_gate_response(patient)

        meta = MedicalRecordMeta.objects.filter(record_id=record_id, patient_id=patient.id).first()
        if not meta:
            return Response({'success': False, 'error': 'Record history not found for your account.'}, status=status.HTTP_404_NOT_FOUND)

        history = service_get_record_history(
            record_id=record_id,
            hospital_id=str(meta.hospital_id),
        )

        return Response(
            {
                'success': True,
                'record_id': str(record_id),
                'history_count': len(history),
                'history': history,
            },
            status=status.HTTP_200_OK,
        )


class PatientProfileAPI(APIView):
    permission_classes = [IsPatient]

    def get(self, request):
        patient_id = request.user_payload['patient_id']
        patient = Patient.objects.filter(id=patient_id).first()
        if not patient:
            return Response({'success': False, 'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        missing_fields = get_missing_profile_fields(patient)
        gov_id_locked = bool(patient.gov_id_type and patient.gov_id_number)

        return Response(
            {
                'success': True,
                'profile_complete': len(missing_fields) == 0,
                'missing_fields': missing_fields,
                'profile_completion_percent': get_profile_completion_percent(patient),
                'patient': {
                    'id': str(patient.id),
                    'full_name': patient.full_name,
                    'email': patient.email,
                    'phone': patient.phone,
                    'address': patient.address,
                    'gender': patient.gender,
                    'date_of_birth': patient.date_of_birth,
                    'blood_group': patient.blood_group,
                    'registered_by_self': patient.registered_by_self,
                    'hospital_name': patient.registered_by.hospital_name if patient.registered_by else 'Self Registered',
                },
                'gov_id': {
                    'locked': gov_id_locked,
                    'type': patient.gov_id_type,
                    'number_masked': _mask_gov_id(patient.gov_id_number),
                },
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        patient_id = request.user_payload['patient_id']
        serializer = PatientProfileUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        patient, errors = service_patient_update_profile(
            patient_id=patient_id,
            full_name=d.get('full_name', ''),
            email=d.get('email', ''),
            phone=d.get('phone', ''),
            address=d.get('address', ''),
            gender=d.get('gender') or None,
            date_of_birth=d.get('date_of_birth') or None,
            blood_group=d.get('blood_group') or None,
            gov_id_type=d.get('gov_id_type', ''),
            gov_id_number=d.get('gov_id_number', ''),
        )

        if errors:
            return Response({'success': False, 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        missing_fields = get_missing_profile_fields(patient)
        return Response(
            {
                'success': True,
                'message': 'Profile updated successfully.',
                'profile_complete': len(missing_fields) == 0,
                'missing_fields': missing_fields,
                'profile_completion_percent': get_profile_completion_percent(patient),
            },
            status=status.HTTP_200_OK,
        )


class PatientUpdatePasswordAPI(APIView):
    permission_classes = [IsPatient]

    def patch(self, request):
        serializer = PatientPasswordUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        success, error = service_patient_update_password(
            patient_id=request.user_payload['patient_id'],
            current_password=d.get('current_password', ''),
            new_password=d.get('new_password', ''),
            confirm_password=d.get('confirm_new_password', ''),
        )

        if error:
            return Response({'success': False, 'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': 'Password updated successfully.'}, status=status.HTTP_200_OK)
