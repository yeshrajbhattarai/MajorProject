from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.patient_login, name='patient_login'),
    path('register/', views.patient_register, name='patient_register'),
    path('complete-profile/', views.patient_complete_profile, name='patient_complete_profile'),
    path('dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('lab-reports/', views.patient_lab_reports, name='patient_lab_reports'),
    path('medical-records/', views.patient_medical_records, name='patient_medical_records'),
    path('medical-records/<uuid:record_id>/', views.patient_medical_record_detail, name='patient_medical_record_detail'),
    path('consents/', views.patient_consents, name='patient_portal_consents'),
    path('consents/<uuid:consent_id>/', views.patient_consent_detail, name='patient_portal_consent_detail'),
    path('records/', views.patient_records, name='patient_records'),
    path('records/<uuid:record_id>/', views.patient_record_detail, name='patient_record_detail'),
    path('records/<uuid:record_id>/history/', views.patient_record_history, name='patient_record_history'),
    path('profile/', views.patient_profile, name='patient_profile'),
    path('profile/update-password/', views.patient_update_password, name='patient_update_password'),
    path('logout/', views.patient_logout, name='patient_logout'),
]
