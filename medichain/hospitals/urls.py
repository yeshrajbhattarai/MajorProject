from django.urls import path
from . import views

urlpatterns = [
    path('', views.hospital_register, name='hospital_register'),
    path('login/', views.hospital_login, name='hospital_login'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('logout/',     views.hospital_logout, name='hospital_logout'),
    path('dashboard/', views.hospital_dashboard,  name='hospital_dashboard'),
    path('profile/',   views.hospital_profile, name='hospital_profile'),
    path('profile/update-name/',     views.hospital_update_name,     name='hospital_update_name'),
    path('profile/update-license/',  views.hospital_update_license,  name='hospital_update_license'),
    path('profile/update-address/',  views.hospital_update_address,  name='hospital_update_address'),
    path('profile/update-password/', views.hospital_update_password, name='hospital_update_password'),


        # Staff — Doctors
    path('staff/doctors/',         views.doctors_list,   name='doctors_list'),
    path('staff/doctors/add/',     views.add_doctor,     name='add_doctor'),
    path('staff/doctors/<uuid:pk>/toggle/', views.toggle_doctor, name='toggle_doctor'),
    
    # Staff — Nurses
    path('staff/nurses/',          views.nurses_list,    name='nurses_list'),
    path('staff/nurses/add/',      views.add_nurse,      name='add_nurse'),
    path('staff/nurses/<uuid:pk>/toggle/',  views.toggle_nurse,  name='toggle_nurse'),
   
 
]   