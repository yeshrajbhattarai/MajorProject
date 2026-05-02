from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .permissions import IsHospitalAdmin, IsHospitalAdminActive, IsHospitalUserActive, IsDoctor, IsNurse, IsTechnician
from .serializers import (
    HospitalSerializer,
    HospitalRegisterSerializer,
    HospitalUserSerializer,
    AddDoctorSerializer,
    AddNurseSerializer,
    AddTechnicianSerializer,
    PatientSerializer,
    AddPatientSerializer,
    LabSerializer,
    CreateLabSerializer,
    LabRequestSerializer,
    SendToLabSerializer,
    DoctorReassessSerializer,
    LabRequestRevisionSerializer,
    MedicalRecordMetaSerializer,
    CreateMedicalRecordSerializer,
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
    service_get_technicians,
    service_add_technician,
    service_get_technician,
    service_toggle_technician,
    service_get_patients,
    service_add_patient,
    service_get_patient,
    service_get_doctor_dashboard_data,
    service_get_doctor_profile,
    service_update_doctor_personal,
    service_update_doctor_password,
    service_get_doctor_patients,
    service_get_doctor_patient_detail,
    service_assign_staff_to_patient,
    service_remove_staff_from_patient,
    service_get_technician_dashboard_data,
    service_get_technician_profile,
    service_update_technician_personal,
    service_update_technician_password,
    service_get_technician_patients,
    service_get_technician_patient_detail,
    service_create_lab,
    service_get_labs,
    service_get_lab_detail,
    service_assign_technician_to_lab,
    service_remove_technician_from_lab,
    service_send_to_lab,
    service_get_lab_queue,
    service_get_lab_request,
    service_get_latest_lab_request_revision,
    service_create_medical_record,
    service_edit_medical_record,
    service_get_record_detail,
    service_get_record_history,
    service_get_technician_records,
    service_doctor_reassess_record,
)
from .token_utils import get_tokens_for_payload


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
            tokens = get_tokens_for_payload({
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
        tokens = get_tokens_for_payload({
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


# POST /api/v1/logout/ — blacklist refresh token
class LogoutAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh', '').strip()
        if not refresh_token:
            return Response({'success': False, 'error': 'refresh token is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({'success': False, 'error': 'Invalid refresh token'},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': 'Logged out successfully.'},
                        status=status.HTTP_200_OK)


# ─── Hospital Admin — Dashboard & Profile ─────────────────────────────────────

# GET /api/v1/dashboard/ — hospital admin dashboard counts
class HospitalDashboardAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def get(self, request):
        hospital, total_doctors, total_nurses, total_patients, total_technicians = service_get_dashboard_data(
            request.user_payload['hospital_id']
        )
        return Response({
            'hospital':           HospitalSerializer(hospital).data,
            'total_doctors':      total_doctors,
            'total_nurses':       total_nurses,
            'total_technicians':  total_technicians,
            'total_patients':     total_patients,
            'total_records':      0,    # will be real count after records model is built
            'total_reports':      0,    # will be real count after reports model is built
        }, status=status.HTTP_200_OK)


# GET /api/v1/profile/ — get hospital profile
class HospitalProfileAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def get(self, request):
        hospital, _, _, _, _ = service_get_dashboard_data(request.user_payload['hospital_id'])
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
    permission_classes = [IsHospitalAdminActive]

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
    permission_classes = [IsHospitalAdminActive]

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
    permission_classes = [IsHospitalAdminActive]

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
    permission_classes = [IsHospitalAdminActive]

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


# ─── Hospital Admin — Technicians ─────────────────────────────────────────────

# GET  /api/v1/staff/technicians/ — list all technicians
# POST /api/v1/staff/technicians/ — register a new technician
class TechniciansListAPI(APIView):
    permission_classes = [IsHospitalAdminActive]

    # list all technicians belonging to this hospital
    def get(self, request):
        technicians = service_get_technicians(request.user_payload['hospital_id'])
        return Response(HospitalUserSerializer(technicians, many=True).data,
                        status=status.HTTP_200_OK)

    # register a new technician and send credentials via email
    def post(self, request):
        serializer = AddTechnicianSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        technician, errors = service_add_technician(
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
            'success':    True,
            'message':    f"{technician.full_name} registered and credentials sent to {technician.email}.",
            'technician': HospitalUserSerializer(technician).data,
        }, status=status.HTTP_201_CREATED)


# GET  /api/v1/staff/technicians/<id>/ — technician detail
# POST /api/v1/staff/technicians/<id>/ — activate / deactivate toggle
class TechnicianDetailAPI(APIView):
    permission_classes = [IsHospitalAdminActive]

    # view individual technician details
    def get(self, request, pk):
        technician, error = service_get_technician(request.user_payload['hospital_id'], pk)
        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
        return Response(HospitalUserSerializer(technician).data, status=status.HTTP_200_OK)

    # activate / deactivate technician toggle
    def post(self, request, pk):
        technician, error = service_toggle_technician(request.user_payload['hospital_id'], pk)
        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'success': True,
            'message': f"{technician.full_name} has been {'deactivated' if technician.status == 'inactive' else 'activated'}.",
            'status':  technician.status,
        }, status=status.HTTP_200_OK)


# ─── Hospital Admin — Patients ─────────────────────────────────────────────────

# GET  /api/v1/staff/patients/ — list all patients registered by this hospital
# POST /api/v1/staff/patients/ — register a new patient
class PatientsListAPI(APIView):
    permission_classes = [IsHospitalAdminActive]

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
    permission_classes = [IsHospitalAdminActive]

    def get(self, request, pk):
        patient, gov_id_masked, error = service_get_patient(pk)
        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)

        data                  = PatientSerializer(patient).data
        data['gov_id_masked'] = gov_id_masked
        return Response(data, status=status.HTTP_200_OK)


# GET /api/v1/staff/doctor/dashboard/ — doctor's own dashboard stats
class DoctorDashboardAPI(APIView):
    permission_classes = [IsDoctor]
 
    def get(self, request):
        total_patients, total_records, total_reports = service_get_doctor_dashboard_data(
            staff_id    = request.user_payload['staff_id'],
            hospital_id = request.user_payload['hospital_id'],
        )
        return Response({
            'staff_id':       request.user_payload['staff_id'],
            'staff_role':     request.user_payload['staff_role'],
            'hospital_id':    request.user_payload['hospital_id'],
            'total_patients': total_patients,
            'total_records':  total_records,
            'total_reports':  total_reports,
        }, status=status.HTTP_200_OK)
    

    
# GET /api/v1/staff/doctor/profile/ — get doctor's own profile
class DoctorProfileAPI(APIView):
    permission_classes = [IsDoctor]
 
    def get(self, request):
        doctor, error = service_get_doctor_profile(request.user_payload['staff_id'])
        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
        return Response(HospitalUserSerializer(doctor).data, status=status.HTTP_200_OK)
 
 
# PATCH /api/v1/staff/doctor/profile/update-personal/ — update personal details
class DoctorUpdatePersonalAPI(APIView):
    permission_classes = [IsDoctor]
 
    def patch(self, request):
        doctor, error = service_update_doctor_personal(
            staff_id         = request.user_payload['staff_id'],
            date_of_birth    = request.data.get('date_of_birth', '').strip() or None,
            gender           = request.data.get('gender', '').strip() or None,
            years_experience = request.data.get('years_experience', '').strip() or None,
            license_number   = request.data.get('license_number', '').strip(),
            home_address     = request.data.get('home_address', '').strip(),
            bio              = request.data.get('bio', '').strip(),
        )
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'success': True,
            'message': 'Personal details updated successfully.',
            'doctor':  HospitalUserSerializer(doctor).data,
        }, status=status.HTTP_200_OK)
 
 
# PATCH /api/v1/staff/doctor/profile/update-password/ — change doctor password
class DoctorUpdatePasswordAPI(APIView):
    permission_classes = [IsDoctor]
 
    def patch(self, request):
        success, error = service_update_doctor_password(
            staff_id         = request.user_payload['staff_id'],
            current_password = request.data.get('current_password', ''),
            new_password     = request.data.get('new_password', ''),
            confirm_password = request.data.get('confirm_new_password', ''),
        )
        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'success': True, 'message': 'Password updated successfully.'},
                        status=status.HTTP_200_OK)


# GET /api/v1/staff/doctor/patients/ — doctor-scoped patient list
class DoctorPatientsListAPI(APIView):
    permission_classes = [IsDoctor]

    def get(self, request):
        patients = service_get_doctor_patients(
            hospital_id=request.user_payload['hospital_id']
        )
        return Response(PatientSerializer(patients, many=True).data,
                        status=status.HTTP_200_OK)


# POST /api/v1/staff/doctor/patients/add/ — add patient by doctor
class DoctorAddPatientAPI(APIView):
    permission_classes = [IsDoctor]

    def post(self, request):
        serializer = AddPatientSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        patient, errors = service_add_patient(
            hospital_id=request.user_payload['hospital_id'],
            gov_id_type=d['gov_id_type'],
            gov_id_number=d['gov_id_number'],
            full_name=d['full_name'],
            gender=d.get('gender') or None,
            phone=d.get('phone') or None,
            email=d.get('email') or None,
            address=d.get('address') or None,
        )

        if errors:
            return Response({'success': False, 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': f'{patient.full_name} has been registered successfully.',
            'patient': PatientSerializer(patient).data,
        }, status=status.HTTP_201_CREATED)


# GET /api/v1/staff/doctor/patients/<id>/ — patient detail + assignments
class DoctorPatientDetailAPI(APIView):
    permission_classes = [IsDoctor]

    def get(self, request, pk):
        patient, gov_id_masked, assigned_nurses, available_nurses, available_labs, patient_records, error = (
            service_get_doctor_patient_detail(
                pk=pk,
                hospital_id=request.user_payload['hospital_id']
            )
        )

        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'patient': PatientSerializer(patient).data,
            'gov_id_masked': gov_id_masked,
            'assigned_nurses': HospitalUserSerializer([a.staff for a in assigned_nurses], many=True).data,
            'available_nurses': HospitalUserSerializer(available_nurses, many=True).data,
            'available_labs': LabSerializer(available_labs, many=True).data,
            'records': MedicalRecordMetaSerializer(patient_records, many=True).data,
        }, status=status.HTTP_200_OK)


# POST /api/v1/staff/doctor/patients/<id>/assign-nurse/
class DoctorAssignNurseAPI(APIView):
    permission_classes = [IsDoctor]

    def post(self, request, pk):
        nurse_id = request.data.get('nurse_id', '').strip()
        if not nurse_id:
            return Response({'success': False, 'error': 'nurse_id is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        assignment, error = service_assign_staff_to_patient(
            patient_id=pk,
            staff_id=nurse_id,
            role='nurse',
            assigned_by_id=request.user_payload['staff_id'],
        )

        if error:
            return Response({'success': False, 'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': f'{assignment.staff.full_name} assigned as nurse.',
        }, status=status.HTTP_200_OK)


# POST /api/v1/staff/doctor/patients/<id>/assign-technician/
class DoctorAssignTechnicianAPI(APIView):
    permission_classes = [IsDoctor]

    def post(self, request, pk):
        tech_id = request.data.get('tech_id', '').strip()
        if not tech_id:
            return Response({'success': False, 'error': 'tech_id is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        assignment, error = service_assign_staff_to_patient(
            patient_id=pk,
            staff_id=tech_id,
            role='technician',
            assigned_by_id=request.user_payload['staff_id'],
        )

        if error:
            return Response({'success': False, 'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': f'{assignment.staff.full_name} assigned as technician.',
        }, status=status.HTTP_200_OK)


# POST /api/v1/staff/doctor/patients/<id>/remove-assignment/<staff_id>/
class DoctorRemoveAssignmentAPI(APIView):
    permission_classes = [IsDoctor]

    def post(self, request, pk, staff_id):
        success, error = service_remove_staff_from_patient(
            patient_id=pk,
            staff_id=staff_id,
        )

        if error:
            return Response({'success': False, 'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': success, 'message': 'Assignment removed.'},
                        status=status.HTTP_200_OK)


# GET /api/v1/staff/technician/dashboard/
class TechnicianDashboardAPI(APIView):
    permission_classes = [IsTechnician]

    def get(self, request):
        total_patients, total_records, total_reports = service_get_technician_dashboard_data(
            staff_id=request.user_payload['staff_id'],
        )
        return Response({
            'staff_id': request.user_payload['staff_id'],
            'staff_role': request.user_payload['staff_role'],
            'hospital_id': request.user_payload['hospital_id'],
            'total_patients': total_patients,
            'total_records': total_records,
            'total_reports': total_reports,
        }, status=status.HTTP_200_OK)


# GET /api/v1/staff/technician/profile/
class TechnicianProfileAPI(APIView):
    permission_classes = [IsTechnician]

    def get(self, request):
        technician, error = service_get_technician_profile(request.user_payload['staff_id'])
        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)
        return Response(HospitalUserSerializer(technician).data, status=status.HTTP_200_OK)


# PATCH /api/v1/staff/technician/profile/update-personal/
class TechnicianUpdatePersonalAPI(APIView):
    permission_classes = [IsTechnician]

    def patch(self, request):
        technician, error = service_update_technician_personal(
            staff_id=request.user_payload['staff_id'],
            date_of_birth=request.data.get('date_of_birth', '').strip() or None,
            gender=request.data.get('gender', '').strip() or None,
            years_experience=request.data.get('years_experience', '').strip() or None,
            license_number=request.data.get('license_number', '').strip(),
            home_address=request.data.get('home_address', '').strip(),
            bio=request.data.get('bio', '').strip(),
        )

        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': 'Personal details updated successfully.',
            'technician': HospitalUserSerializer(technician).data,
        }, status=status.HTTP_200_OK)


# PATCH /api/v1/staff/technician/profile/update-password/
class TechnicianUpdatePasswordAPI(APIView):
    permission_classes = [IsTechnician]

    def patch(self, request):
        success, error = service_update_technician_password(
            staff_id=request.user_payload['staff_id'],
            current_password=request.data.get('current_password', ''),
            new_password=request.data.get('new_password', ''),
            confirm_password=request.data.get('confirm_new_password', ''),
        )

        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': success, 'message': 'Password updated successfully.'},
                        status=status.HTTP_200_OK)


# GET /api/v1/staff/technician/patients/
class TechnicianPatientsListAPI(APIView):
    permission_classes = [IsTechnician]

    def get(self, request):
        patients = service_get_technician_patients(staff_id=request.user_payload['staff_id'])
        data = []
        for row in patients:
            data.append({
                'patient': PatientSerializer(row['patient']).data,
                'assigned_by': HospitalUserSerializer(row['assigned_by']).data if row.get('assigned_by') else None,
                'assigned_at': row.get('assigned_at'),
            })
        return Response(data, status=status.HTTP_200_OK)


# GET /api/v1/staff/technician/patients/<id>/
class TechnicianPatientDetailAPI(APIView):
    permission_classes = [IsTechnician]

    def get(self, request, pk):
        patient, assigned_nurses, assigned_technicians, assigned_by, error = (
            service_get_technician_patient_detail(
                staff_id=request.user_payload['staff_id'],
                patient_id=pk,
            )
        )

        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'patient': PatientSerializer(patient).data,
            'assigned_nurses': [
                HospitalUserSerializer(a.staff).data for a in assigned_nurses
            ],
            'assigned_technicians': [
                HospitalUserSerializer(a.staff).data for a in assigned_technicians
            ],
            'assigned_by': HospitalUserSerializer(assigned_by).data if assigned_by else None,
        }, status=status.HTTP_200_OK)


# ─── Lab APIs ─────────────────────────────────────────────────────────────────

# GET/POST /api/v1/staff/labs/
class LabListAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def get(self, request):
        labs = service_get_labs(request.user_payload['hospital_id'])
        data = []
        for row in labs:
            data.append({
                'lab': LabSerializer(row['lab']).data,
                'technicians_count': row['technicians_count'],
                'pending_count': row['pending_count'],
                'completed_count': row['completed_count'],
            })
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CreateLabSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        lab, errors = service_create_lab(
            hospital_id=request.user_payload['hospital_id'],
            lab_type=d['lab_type'],
            name=d['name'],
            custom_field_schema=d.get('custom_field_schema', []),
        )

        if errors:
            return Response({'success': False, 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(LabSerializer(lab).data, status=status.HTTP_201_CREATED)


# GET /api/v1/staff/labs/<lab_id>/
class LabDetailAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def get(self, request, lab_id):
        lab, assignments, pending_requests, completed_count, error = service_get_lab_detail(
            hospital_id=request.user_payload['hospital_id'],
            lab_id=lab_id,
        )

        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'lab': LabSerializer(lab).data,
            'assignments': HospitalUserSerializer([a.technician for a in assignments], many=True).data,
            'pending_requests': len(pending_requests),
            'completed_count': completed_count,
        }, status=status.HTTP_200_OK)


# POST /api/v1/staff/labs/<lab_id>/assign/
class LabAssignTechnicianAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def post(self, request, lab_id):
        technician_id = request.data.get('technician_id', '').strip()
        if not technician_id:
            return Response({'error': 'technician_id is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        _, error = service_assign_technician_to_lab(
            hospital_id=request.user_payload['hospital_id'],
            lab_id=lab_id,
            technician_id=technician_id,
        )

        if error:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': 'Technician assigned to lab'},
                        status=status.HTTP_200_OK)


# POST /api/v1/staff/labs/<lab_id>/remove/<technician_id>/
class LabRemoveTechnicianAPI(APIView):
    permission_classes = [IsHospitalAdmin]

    def post(self, request, lab_id, technician_id):
        success, error = service_remove_technician_from_lab(lab_id, technician_id)

        if not success:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': 'Technician removed from lab'},
                        status=status.HTTP_200_OK)


# ─── Lab Request APIs ─────────────────────────────────────────────────────────

# POST /api/v1/staff/doctor/send-to-lab/
class DoctorSendToLabAPI(APIView):
    permission_classes = [IsDoctor]

    def post(self, request, pk=None):
        serializer = SendToLabSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        patient_id = request.data.get('patient_id', '').strip() or str(pk or '').strip()

        if not patient_id:
            return Response({'error': 'patient_id is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        _, errors = service_send_to_lab(
            patient_id=patient_id,
            lab_id=d['lab_id'],
            doctor_id=request.user_payload['staff_id'],
            chest_pain_type=d['chest_pain_type'],
            diagnosis=d['diagnosis'],
            treatment_plan=d['treatment_plan'],
            notes=d.get('notes', ''),
            custom_field_values=d.get('custom_field_values', {}),
        )

        if errors:
            return Response({'success': False, 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': 'Lab request created'},
                        status=status.HTTP_201_CREATED)


# GET /api/v1/staff/technician/lab/
class TechnicianLabQueueAPI(APIView):
    permission_classes = [IsTechnician]

    def get(self, request):
        queue = service_get_lab_queue(staff_id=request.user_payload['staff_id'])
        return Response(LabRequestSerializer(queue, many=True).data,
                        status=status.HTTP_200_OK)


# GET /api/v1/staff/technician/lab/<request_id>/
class TechnicianLabRequestDetailAPI(APIView):
    permission_classes = [IsTechnician]

    def get(self, request, request_id):
        lab_request, error = service_get_lab_request(
            staff_id=request.user_payload['staff_id'],
            request_id=request_id,
        )

        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)

        latest_revision = service_get_latest_lab_request_revision(request_id)

        return Response({
            'lab_request': LabRequestSerializer(lab_request).data,
            'latest_revision': LabRequestRevisionSerializer(latest_revision).data if latest_revision else None,
        }, status=status.HTTP_200_OK)


# ─── Medical Record APIs ───────────────────────────────────────────────────────

# POST /api/v1/staff/technician/records/
class TechnicianCreateRecordAPI(APIView):
    permission_classes = [IsTechnician]

    def post(self, request):
        serializer = CreateMedicalRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        lab_request_id = request.data.get('lab_request_id', '').strip()
        if not lab_request_id:
            return Response({'error': 'lab_request_id is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        record, errors = service_create_medical_record(
            lab_request_id=lab_request_id,
            technician_id=request.user_payload['staff_id'],
            hospital_id=request.user_payload['hospital_id'],
            data=d,
            technician_reason=d.get('technician_change_reason', ''),
        )

        if errors:
            return Response({'success': False, 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'record_id': str(record.record_id),
            'message': 'Medical record created',
        }, status=status.HTTP_201_CREATED)


# GET /api/v1/staff/technician/records/
class TechnicianRecordsListAPI(APIView):
    permission_classes = [IsTechnician]

    def get(self, request):
        records = service_get_technician_records(
            staff_id=request.user_payload['staff_id'],
            hospital_id=request.user_payload['hospital_id'],
        )
        return Response(MedicalRecordMetaSerializer(records, many=True).data,
                        status=status.HTTP_200_OK)


# GET /api/v1/staff/records/<record_id>/
class RecordDetailAPI(APIView):
    def get(self, request, record_id):
        version_number = request.query_params.get('v')
        if version_number:
            try:
                version_number = int(version_number)
            except ValueError:
                return Response({'error': 'Invalid version number'},
                                status=status.HTTP_400_BAD_REQUEST)

        record, lab_request, detail_bundle, error = service_get_record_detail(
            record_id=record_id,
            hospital_id=request.user_payload.get('hospital_id'),
            version_number=version_number,
        )

        if error:
            return Response({'error': error}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'record_id': str(record.record_id),
            'version': record.version,
            'lab_request': LabRequestSerializer(lab_request).data if lab_request else None,
            'audit': detail_bundle['audit'] if detail_bundle else None,
            'timeline': detail_bundle['timeline'] if detail_bundle else None,
        }, status=status.HTTP_200_OK)


# GET /api/v1/staff/records/<record_id>/history/
class RecordHistoryAPI(APIView):
    def get(self, request, record_id):
        history = service_get_record_history(
            record_id=record_id,
            hospital_id=request.user_payload.get('hospital_id'),
        )

        return Response(history, status=status.HTTP_200_OK)


# POST /api/v1/staff/doctor/records/<record_id>/reassess/
class DoctorReassessRecordAPI(APIView):
    permission_classes = [IsDoctor]

    def post(self, request, record_id):
        serializer = DoctorReassessSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        d = serializer.validated_data
        _, errors = service_doctor_reassess_record(
            record_id=record_id,
            doctor_id=request.user_payload['staff_id'],
            hospital_id=request.user_payload['hospital_id'],
            chest_pain_type=d['chest_pain_type'],
            diagnosis=d['diagnosis'],
            treatment_plan=d['treatment_plan'],
            notes=d.get('notes', ''),
            reason=d['reason'],
        )

        if errors:
            return Response({'success': False, 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': 'Record reassessment submitted. Request moved back to technician queue.',
        }, status=status.HTTP_200_OK)