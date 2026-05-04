from django.urls import path
from .api_views import (
    # auth
    HospitalRegisterAPI,
    VerifyOTPAPI,
    ResendOTPAPI,
    LoginAPI,
    LogoutAPI,
    # dashboard & profile
    HospitalDashboardAPI,
    HospitalProfileAPI,
    HospitalUpdateNameAPI,
    HospitalUpdateLicenseAPI,
    HospitalUpdateAddressAPI,
    HospitalUpdatePasswordAPI,
    # doctors
    DoctorsListAPI,
    DoctorDetailAPI,
    DoctorDashboardAPI,
    DoctorProfileAPI,
    DoctorUpdatePersonalAPI,
    DoctorUpdatePasswordAPI,
    DoctorPatientsListAPI,
    DoctorAddPatientAPI,
    DoctorPatientDetailAPI,
    DoctorAssignNurseAPI,
    DoctorAssignTechnicianAPI,
    DoctorRemoveAssignmentAPI,
    DoctorSendToLabAPI,
    DoctorReassessRecordAPI,
    DoctorLabsListAPI,
    DoctorLabDetailAPI,
    # nurses
    NursesListAPI,
    NurseDetailAPI,
    # Technician
    TechniciansListAPI,
    TechnicianDetailAPI,

    # patients
    PatientsListAPI,
    PatientDetailAPI,

    # technician portal
    TechnicianDashboardAPI,
    TechnicianProfileAPI,
    TechnicianUpdatePersonalAPI,
    TechnicianUpdatePasswordAPI,
    TechnicianPatientsListAPI,
    TechnicianPatientDetailAPI,
    
    # Labs & Medical Records
    LabListAPI,
    LabDetailAPI,
    LabAssignTechnicianAPI,
    LabRemoveTechnicianAPI,
    TechnicianLabQueueAPI,
    TechnicianLabRequestDetailAPI,
    TechnicianCreateRecordAPI,
    TechnicianRecordsListAPI,
    RecordDetailAPI,
    RecordHistoryAPI,
)


# ─── API v1 Routes ────────────────────────────────────────────────────────────
# all routes are prefixed with /api/v1/ from the project urls.py

urlpatterns = [

    # ── Auth ──────────────────────────────────────────────────────────────────
    path('register/',   HospitalRegisterAPI.as_view(), name='api_register'),
    path('verify-otp/', VerifyOTPAPI.as_view(),         name='api_verify_otp'),
    path('resend-otp/', ResendOTPAPI.as_view(),         name='api_resend_otp'),
    path('login/',      LoginAPI.as_view(),             name='api_login'),
    path('logout/',     LogoutAPI.as_view(),            name='api_logout'),

    # ── Dashboard & Profile ───────────────────────────────────────────────────
    path('dashboard/',                    HospitalDashboardAPI.as_view(),     name='api_dashboard'),
    path('profile/',                      HospitalProfileAPI.as_view(),       name='api_profile'),
    path('profile/update-name/',          HospitalUpdateNameAPI.as_view(),    name='api_update_name'),
    path('profile/update-license/',       HospitalUpdateLicenseAPI.as_view(), name='api_update_license'),
    path('profile/update-address/',       HospitalUpdateAddressAPI.as_view(), name='api_update_address'),
    path('profile/update-password/',      HospitalUpdatePasswordAPI.as_view(),name='api_update_password'),

    # ── Doctors ───────────────────────────────────────────────────────────────
    path('staff/doctors/',          DoctorsListAPI.as_view(),  name='api_doctors_list'),
    path('staff/doctors/<uuid:pk>/', DoctorDetailAPI.as_view(), name='api_doctor_detail'),

    # ── Nurses ────────────────────────────────────────────────────────────────
    path('staff/nurses/',           NursesListAPI.as_view(),   name='api_nurses_list'),
    path('staff/nurses/<uuid:pk>/', NurseDetailAPI.as_view(),  name='api_nurse_detail'),

    # ── Technicians ───────────────────────────────────────────────────────────────
    path('staff/technicians/',            TechniciansListAPI.as_view(),   name='api_technicians_list'),
    path('staff/technicians/<uuid:pk>/',  TechnicianDetailAPI.as_view(),  name='api_technician_detail'),

    # ── Patients ──────────────────────────────────────────────────────────────
    path('staff/patients/',            PatientsListAPI.as_view(),   name='api_patients_list'),
    path('staff/patients/<uuid:pk>/',  PatientDetailAPI.as_view(),  name='api_patient_detail'),

     # ── Doctor portal ─────────────────────────────────────────────────────

    path('staff/doctor/dashboard/',   DoctorDashboardAPI.as_view(),  name='api_doctor_dashboard'),
    path('staff/doctor/profile/',     DoctorProfileAPI.as_view(),    name='api_doctor_profile'),
    path('staff/doctor/profile/update-personal/',   DoctorUpdatePersonalAPI.as_view(),  name='api_doctor_update_personal'),
    path('staff/doctor/profile/update-password/',   DoctorUpdatePasswordAPI.as_view(),  name='api_doctor_update_password'),
    path('staff/doctor/patients/add/', DoctorAddPatientAPI.as_view(), name='api_doctor_add_patient'),
    path('staff/doctor/patients/', DoctorPatientsListAPI.as_view(), name='api_doctor_patients_list'),
    path('staff/doctor/patients/<uuid:pk>/', DoctorPatientDetailAPI.as_view(), name='api_doctor_patient_detail'),
    path('staff/doctor/patients/<uuid:pk>/assign-nurse/', DoctorAssignNurseAPI.as_view(), name='api_doctor_assign_nurse'),
    path('staff/doctor/patients/<uuid:pk>/assign-technician/', DoctorAssignTechnicianAPI.as_view(), name='api_doctor_assign_technician'),
    path('staff/doctor/patients/<uuid:pk>/remove-assignment/<uuid:staff_id>/', DoctorRemoveAssignmentAPI.as_view(), name='api_doctor_remove_assignment'),
    path('staff/doctor/patients/<uuid:pk>/send-to-lab/', DoctorSendToLabAPI.as_view(), name='api_doctor_send_to_lab'),
    path('staff/doctor/records/<uuid:record_id>/reassess/', DoctorReassessRecordAPI.as_view(), name='api_doctor_reassess_record'),
    path('staff/doctor/labs/', DoctorLabsListAPI.as_view(), name='api_doctor_labs_list'),
    path('staff/doctor/labs/<uuid:lab_id>/', DoctorLabDetailAPI.as_view(), name='api_doctor_lab_detail'),

    # ── Technician portal ───────────────────────────────────────────────────
    path('staff/technician/dashboard/', TechnicianDashboardAPI.as_view(), name='api_technician_dashboard'),
    path('staff/technician/profile/', TechnicianProfileAPI.as_view(), name='api_technician_profile'),
    path('staff/technician/profile/update-personal/', TechnicianUpdatePersonalAPI.as_view(), name='api_technician_update_personal'),
    path('staff/technician/profile/update-password/', TechnicianUpdatePasswordAPI.as_view(), name='api_technician_update_password'),
    path('staff/technician/patients/', TechnicianPatientsListAPI.as_view(), name='api_technician_patients_list'),
    path('staff/technician/patients/<uuid:pk>/', TechnicianPatientDetailAPI.as_view(), name='api_technician_patient_detail'),
    
    # ── Labs & Medical Records ──────────────────────────────────────────────
    path('staff/labs/', LabListAPI.as_view(), name='api_labs_list'),
    path('staff/labs/<uuid:lab_id>/', LabDetailAPI.as_view(), name='api_lab_detail'),
    path('staff/labs/<uuid:lab_id>/assign-technician/', LabAssignTechnicianAPI.as_view(), name='api_lab_assign_technician'),
    path('staff/labs/<uuid:lab_id>/remove-technician/<uuid:technician_id>/', LabRemoveTechnicianAPI.as_view(), name='api_lab_remove_technician'),
    
    path('staff/technician/lab-queue/', TechnicianLabQueueAPI.as_view(), name='api_technician_lab_queue'),
    path('staff/technician/lab-requests/<uuid:request_id>/', TechnicianLabRequestDetailAPI.as_view(), name='api_technician_lab_request_detail'),
    
    path('staff/technician/records/create/', TechnicianCreateRecordAPI.as_view(), name='api_technician_create_record'),
    path('staff/technician/records/', TechnicianRecordsListAPI.as_view(), name='api_technician_records_list'),
    path('staff/records/<uuid:record_id>/', RecordDetailAPI.as_view(), name='api_record_detail'),
    path('staff/records/<uuid:record_id>/history/', RecordHistoryAPI.as_view(), name='api_record_history'),
]
