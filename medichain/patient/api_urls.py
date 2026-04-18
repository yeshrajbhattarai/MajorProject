from django.urls import path

from .api_views import (
    PatientDashboardAPI,
    PatientLoginAPI,
    PatientLogoutAPI,
    PatientRecordDetailAPI,
    PatientRecordHistoryAPI,
    PatientRecordsAPI,
    PatientProfileAPI,
    PatientRegisterAPI,
    PatientUpdatePasswordAPI,
)

urlpatterns = [
    path('register/', PatientRegisterAPI.as_view(), name='api_patient_register'),
    path('login/', PatientLoginAPI.as_view(), name='api_patient_login'),
    path('logout/', PatientLogoutAPI.as_view(), name='api_patient_logout'),

    path('dashboard/', PatientDashboardAPI.as_view(), name='api_patient_dashboard'),
    path('records/', PatientRecordsAPI.as_view(), name='api_patient_records'),
    path('records/<uuid:record_id>/', PatientRecordDetailAPI.as_view(), name='api_patient_record_detail'),
    path('records/<uuid:record_id>/history/', PatientRecordHistoryAPI.as_view(), name='api_patient_record_history'),
    path('profile/', PatientProfileAPI.as_view(), name='api_patient_profile'),
    path('profile/update-password/', PatientUpdatePasswordAPI.as_view(), name='api_patient_update_password'),
]
