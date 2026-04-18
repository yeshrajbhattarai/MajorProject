from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.patient_login, name='patient_login'),
    path('register/', views.patient_register, name='patient_register'),
    path('complete-profile/', views.patient_complete_profile, name='patient_complete_profile'),
    path('profile/', views.patient_profile, name='patient_profile'),
    path('profile/update-password/', views.patient_update_password, name='patient_update_password'),
    path('dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('records/', views.patient_records, name='patient_records'),
    path('records/<uuid:record_id>/', views.patient_record_detail, name='patient_record_detail'),
    path('records/<uuid:record_id>/history/', views.patient_record_history, name='patient_record_history'),
    path('logout/', views.patient_logout, name='patient_logout'),
]
