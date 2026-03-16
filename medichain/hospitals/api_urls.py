from django.urls import path
from .api_views import (
    # auth
    HospitalRegisterAPI,
    VerifyOTPAPI,
    ResendOTPAPI,
    LoginAPI,
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
    # nurses
    NursesListAPI,
    NurseDetailAPI,
    # patients
    PatientsListAPI,
    PatientDetailAPI,
)


# ─── API v1 Routes ────────────────────────────────────────────────────────────
# all routes are prefixed with /api/v1/ from the project urls.py

urlpatterns = [

    # ── Auth ──────────────────────────────────────────────────────────────────
    path('register/',   HospitalRegisterAPI.as_view(), name='api_register'),
    path('verify-otp/', VerifyOTPAPI.as_view(),         name='api_verify_otp'),
    path('resend-otp/', ResendOTPAPI.as_view(),         name='api_resend_otp'),
    path('login/',      LoginAPI.as_view(),             name='api_login'),

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

    # ── Patients ──────────────────────────────────────────────────────────────
    path('staff/patients/',            PatientsListAPI.as_view(),   name='api_patients_list'),
    path('staff/patients/<uuid:pk>/',  PatientDetailAPI.as_view(),  name='api_patient_detail'),
]
