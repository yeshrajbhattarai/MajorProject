from django.urls import path

from .api_views import (
    PatientDashboardAPI,
    PatientCompleteProfileAPI,
    PatientLoginAPI,
    PatientLogoutAPI,
    PatientRecordDetailAPI,
    PatientRecordHistoryAPI,
    PatientRecordsAPI,
    PatientProfileAPI,
    PatientRegisterAPI,
    PatientVerifyOTPAPI,
    PatientUpdatePasswordAPI,
)

urlpatterns = [
    path('register/', PatientRegisterAPI.as_view(), name='api_patient_register'),
    path('verify-otp/', PatientVerifyOTPAPI.as_view(), name='api_patient_verify_otp'),
    path('login/', PatientLoginAPI.as_view(), name='api_patient_login'),
    path('logout/', PatientLogoutAPI.as_view(), name='api_patient_logout'),

    path('dashboard/', PatientDashboardAPI.as_view(), name='api_patient_dashboard'),
    path('complete-profile/', PatientCompleteProfileAPI.as_view(), name='api_patient_complete_profile'),
    path('records/', PatientRecordsAPI.as_view(), name='api_patient_records'),
    path('lab-records/<uuid:record_id>/', PatientRecordDetailAPI.as_view(), name='api_patient_lab_record_detail'),
    path('lab-records/<uuid:record_id>/history/', PatientRecordHistoryAPI.as_view(), name='api_patient_lab_record_history'),
    path('medical-records/<uuid:record_id>/', PatientRecordDetailAPI.as_view(), name='api_patient_medical_record_detail'),
    path('medical-records/<uuid:record_id>/history/', PatientRecordHistoryAPI.as_view(), name='api_patient_medical_record_history'),
    path('records/<uuid:record_id>/', PatientRecordDetailAPI.as_view(), name='api_patient_record_detail'),
    path('records/<uuid:record_id>/history/', PatientRecordHistoryAPI.as_view(), name='api_patient_record_history'),
    path('profile/', PatientProfileAPI.as_view(), name='api_patient_profile'),
    path('profile/update-password/', PatientUpdatePasswordAPI.as_view(), name='api_patient_update_password'),
]
