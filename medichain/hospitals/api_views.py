from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .permissions import IsHospitalAdmin, IsDoctor, IsNurse
from .serializers import (
    HospitalSerializer,
    HospitalRegisterSerializer,
    HospitalUserSerializer,
    AddDoctorSerializer,
    AddNurseSerializer,
    PatientSerializer,
    AddPatientSerializer,
)
from .services import (
    service_register_hospital,
    service_verify_otp,
    service_resend_otp,
    service_login,
    service_get_dashboard_data,
    service_update_name,
    service_update_license,
    service_update_address,
    service_update_password,
    service_get_doctors,
    service_add_doctor,
    service_get_doctor,
    service_toggle_doctor,
    service_get_nurses,
    service_add_nurse,
    service_get_nurse,
    service_toggle_nurse,
    service_get_patients,
    service_add_patient,
    service_get_patient,
)


# ─── JWT Token Helper ─────────────────────────────────────────────────────────

# generate access + refresh token pair for a given user payload
def get_tokens_for_user(payload: dict) -> dict:
    refresh = RefreshToken()

    # embed custom claims into the token
    for key, value in payload.items():
        refresh[key] = value

    return {
        'refresh': str(refresh),
        'access':  str(refresh.access_token),
    }


# ─── Auth ─────────────────────────────────────────────────────────────────────

# POST /api/v1/register/ — hospital registration
class HospitalRegisterAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = HospitalRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        hospital, errors = service_register_hospital(
            hospital_name    = d['hospital_name'],
            email            = d['email'],
            contact_number   = d['contact_number'],
            password         = d['password'],
            confirm_password = d['confirm_password'],
        )

        if errors:
            return Response({'success': False, 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success':     True,
            'message':     'Registration successful. OTP sent to your email.',
            'hospital_id': str(hospital.id),
        }, status=status.HTTP_201_CREATED)


# POST /api/v1/verify-otp/ — verify email OTP after registration
class VerifyOTPAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        hospital_id = request.data.get('hospital_id', '').strip()
        otp_entered = request.data.get('otp', '').strip()

        if not hospital_id or not otp_entered:
            return Response({'success': False, 'error': 'hospital_id and otp are required'},
                            status=status.HTTP_400_BAD_REQUEST)

        success, error = service_verify_otp(hospital_id, otp_entered)

        if not success:
            return Response({'success': False, 'error': error},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': 'Email verified successfully.'},
                        status=status.HTTP_200_OK)


# POST /api/v1/resend-otp/ — resend a fresh OTP
class ResendOTPAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        hospital_id = request.data.get('hospital_id', '').strip()

        if not hospital_id:
            return Response({'success': False, 'error': 'hospital_id is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        success, error = service_resend_otp(hospital_id)

        if not success:
            return Response({'success': False, 'error': error},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': 'New OTP sent to your email.'},
                        status=status.HTTP_200_OK)


# POST /api/v1/login/ — unified login for hospital admin, doctor, nurse
class LoginAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user_type, obj, errors = service_login(
            email    = request.data.get('email', '').strip().lower(),
            password = request.data.get('password', ''),
        )

        if errors:
            # use 401 for wrong password, 400 for missing fields, 403 for blocked
            http_status = status.HTTP_400_BAD_REQUEST
            if 'password' in errors:
                http_status = status.HTTP_401_UNAUTHORIZED
            if any(k in str(errors) for k in ['suspended', 'deactivated', 'verify']):
                http_status = status.HTTP_403_FORBIDDEN
            return Response({'success': False, 'errors': errors}, status=http_status)

        if user_type == 'hospital_admin':
            # generate JWT with hospital admin claims
            tokens = get_tokens_for_user({
                'user_type':      'hospital_admin',
                'hospital_id':    str(obj.id),
                'hospital_name':  obj.hospital_name,
                'account_status': obj.account_status,
            })
            return Response({
                'success':  True,
                'role':     'hospital_admin',
                'tokens':   tokens,
                'hospital': HospitalSerializer(obj).data,
            }, status=status.HTTP_200_OK)

        # generate JWT with staff claims
        tokens = get_tokens_for_user({
            'user_type':   'staff',
            'staff_id':    str(obj.id),
            'staff_role':  obj.role,
            'hospital_id': str(obj.hospital.id),
        })
        return Response({
            'success': True,
            'role':    obj.role,
            'tokens':  tokens,
            'staff':   HospitalUserSerializer(obj).data,
        }, status=status.HTTP_200_OK)


# ─── Hospital Admin — Dashboard & Profile ─────────────────────────────────────

# GET /api/v1/dashboard/ — hospital admin dashboard counts
class HospitalDashboardAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def get(self, request):
        hospital, total_doctors, total_nurses, total_patients = service_get_dashboard_data(
            request.user_payload['hospital_id']
        )
        return Response({
            'hospital':       HospitalSerializer(hospital).data,
            'total_doctors':  total_doctors,
            'total_nurses':   total_nurses,
            'total_patients': total_patients,
            'total_records':  0,    # will be real count after records model is built
            'total_reports':  0,    # will be real count after reports model is built
        }, status=status.HTTP_200_OK)


# GET /api/v1/profile/ — get hospital profile
class HospitalProfileAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def get(self, request):
        hospital, _, _, _ = service_get_dashboard_data(request.user_payload['hospital_id'])
        return Response(HospitalSerializer(hospital).data, status=status.HTTP_200_OK)


# PATCH /api/v1/profile/update-name/ — save and lock hospital name
class HospitalUpdateNameAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def patch(self, request):
        hospital, error = service_update_name(
            hospital_id = request.user_payload['hospital_id'],
            name        = request.data.get('hospital_name', '').strip(),
        )

        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'hospital_name': hospital.hospital_name},
                        status=status.HTTP_200_OK)


# PATCH /api/v1/profile/update-license/ — save and lock license details
class HospitalUpdateLicenseAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def patch(self, request):
        hospital, error = service_update_license(
            hospital_id      = request.user_payload['hospital_id'],
            license_number   = request.data.get('license_number', '').strip(),
            license_document = request.FILES.get('license_document'),
        )

        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success':        True,
            'license_number': hospital.license_number,
            'account_status': hospital.account_status,
        }, status=status.HTTP_200_OK)


# PATCH /api/v1/profile/update-address/ — update address (editable anytime)
class HospitalUpdateAddressAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def patch(self, request):
        hospital, error = service_update_address(
            hospital_id = request.user_payload['hospital_id'],
            address     = request.data.get('address', '').strip(),
            city        = request.data.get('city', '').strip(),
            state       = request.data.get('state', '').strip(),
            country     = request.data.get('country', '').strip(),
        )

        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success':        True,
            'message':        'Address updated successfully.',
            'account_status': hospital.account_status,
        }, status=status.HTTP_200_OK)


# PATCH /api/v1/profile/update-password/ — change password after verifying current
class HospitalUpdatePasswordAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def patch(self, request):
        success, error = service_update_password(
            hospital_id      = request.user_payload['hospital_id'],
            current_password = request.data.get('current_password', ''),
            new_password     = request.data.get('new_password', ''),
            confirm_password = request.data.get('confirm_new_password', ''),
        )

        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': 'Password updated successfully.'},
                        status=status.HTTP_200_OK)


# ─── Hospital Admin — Doctors ──────────────────────────────────────────────────

# GET  /api/v1/staff/doctors/ — list all doctors
# POST /api/v1/staff/doctors/ — register a new doctor
class DoctorsListAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    # list all doctors belonging to this hospital
    def get(self, request):
        doctors = service_get_doctors(request.user_payload['hospital_id'])
        return Response(HospitalUserSerializer(doctors, many=True).data,
                        status=status.HTTP_200_OK)

    # register a new doctor and send credentials via email
    def post(self, request):
        serializer = AddDoctorSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        doctor, errors = service_add_doctor(
            hospital_id    = request.user_payload['hospital_id'],
            full_name      = d['full_name'],
            email          = d['email'],
            phone          = d['phone'],
            employee_id    = d['employee_id'],
            specialization = d.get('specialization', ''),
        )

        if errors:
            return Response({'success': False, 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': f"Dr. {doctor.full_name} registered and credentials sent to {doctor.email}.",
            'doctor':  HospitalUserSerializer(doctor).data,
        }, status=status.HTTP_201_CREATED)


# GET  /api/v1/staff/doctors/<id>/ — doctor detail
# POST /api/v1/staff/doctors/<id>/ — activate / deactivate toggle
class DoctorDetailAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    # view individual doctor details
    def get(self, request, pk):
        doctor, error = service_get_doctor(request.user_payload['hospital_id'], pk)
        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
        return Response(HospitalUserSerializer(doctor).data, status=status.HTTP_200_OK)

    # activate / deactivate doctor toggle
    def post(self, request, pk):
        doctor, error = service_toggle_doctor(request.user_payload['hospital_id'], pk)
        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'success': True,
            'message': f"{doctor.full_name} has been {'deactivated' if doctor.status == 'inactive' else 'activated'}.",
            'status':  doctor.status,
        }, status=status.HTTP_200_OK)


# ─── Hospital Admin — Nurses ───────────────────────────────────────────────────

# GET  /api/v1/staff/nurses/ — list all nurses
# POST /api/v1/staff/nurses/ — register a new nurse
class NursesListAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    # list all nurses belonging to this hospital
    def get(self, request):
        nurses = service_get_nurses(request.user_payload['hospital_id'])
        return Response(HospitalUserSerializer(nurses, many=True).data,
                        status=status.HTTP_200_OK)

    # register a new nurse and send credentials via email
    def post(self, request):
        serializer = AddNurseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        nurse, errors = service_add_nurse(
            hospital_id = request.user_payload['hospital_id'],
            full_name   = d['full_name'],
            email       = d['email'],
            phone       = d['phone'],
            employee_id = d['employee_id'],
        )

        if errors:
            return Response({'success': False, 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': f"{nurse.full_name} registered and credentials sent to {nurse.email}.",
            'nurse':   HospitalUserSerializer(nurse).data,
        }, status=status.HTTP_201_CREATED)


# GET  /api/v1/staff/nurses/<id>/ — nurse detail
# POST /api/v1/staff/nurses/<id>/ — activate / deactivate toggle
class NurseDetailAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    # view individual nurse details
    def get(self, request, pk):
        nurse, error = service_get_nurse(request.user_payload['hospital_id'], pk)
        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
        return Response(HospitalUserSerializer(nurse).data, status=status.HTTP_200_OK)

    # activate / deactivate nurse toggle
    def post(self, request, pk):
        nurse, error = service_toggle_nurse(request.user_payload['hospital_id'], pk)
        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'success': True,
            'message': f"{nurse.full_name} has been {'deactivated' if nurse.status == 'inactive' else 'activated'}.",
            'status':  nurse.status,
        }, status=status.HTTP_200_OK)


# ─── Hospital Admin — Patients ─────────────────────────────────────────────────

# GET  /api/v1/staff/patients/ — list all patients registered by this hospital
# POST /api/v1/staff/patients/ — register a new patient
class PatientsListAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    # list all patients registered by this hospital
    def get(self, request):
        patients = service_get_patients(request.user_payload['hospital_id'])
        return Response(PatientSerializer(patients, many=True).data,
                        status=status.HTTP_200_OK)

    # register a new patient with encrypted gov ID and duplicate detection
    def post(self, request):
        serializer = AddPatientSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        patient, errors = service_add_patient(
            hospital_id   = request.user_payload['hospital_id'],
            gov_id_type   = d['gov_id_type'],
            gov_id_number = d['gov_id_number'],
            full_name     = d['full_name'],
            gender        = d.get('gender')  or None,
            phone         = d.get('phone')   or None,
            email         = d.get('email')   or None,
            address       = d.get('address') or None,
        )

        if errors:
            return Response({'success': False, 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': f"{patient.full_name} has been registered successfully.",
            'patient': PatientSerializer(patient).data,
        }, status=status.HTTP_201_CREATED)


# GET /api/v1/staff/patients/<id>/ — patient detail with masked gov ID
class PatientDetailAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def get(self, request, pk):
        patient, gov_id_masked, error = service_get_patient(pk)
        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)

        data                  = PatientSerializer(patient).data
        data['gov_id_masked'] = gov_id_masked
        return Response(data, status=status.HTTP_200_OK)
