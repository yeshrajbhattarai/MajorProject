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
    path('staff/doctors/<uuid:pk>/', views.doctor_detail, name='doctor_detail'),
    path('staff/doctors/<uuid:pk>/toggle/', views.toggle_doctor, name='toggle_doctor'),
    
    # Staff — Nurses
    path('staff/nurses/',          views.nurses_list,    name='nurses_list'),
    path('staff/nurses/add/',      views.add_nurse,      name='add_nurse'),
    path('staff/nurses/<uuid:pk>/toggle/',  views.toggle_nurse,  name='toggle_nurse'),
    path('staff/nurses/<uuid:pk>/',  views.nurse_detail,  name='nurse_detail'),


    # Staff — Technicians
    path('staff/technicians/',                  views.technicians_list,   name='technicians_list'),
    path('staff/technicians/add/',              views.add_technician,     name='add_technician'),
    path('staff/technicians/<uuid:pk>/',        views.technician_detail,  name='technician_detail'),
    path('staff/technicians/<uuid:pk>/toggle/', views.toggle_technician,  name='toggle_technician'),

    #patients 
    path('staff/patients/',          views.patients_list,  name='patients_list'),
    path('staff/patients/add/',      views.add_patient,    name='add_patient'),
    path('staff/patients/<uuid:pk>/', views.patient_detail, name='patient_detail'),

    # Labs - admin
    path('labs/', views.admin_labs_list, name='admin_labs_list'),
    path('labs/<uuid:lab_id>/', views.admin_lab_detail, name='admin_lab_detail'),
    path('labs/<uuid:lab_id>/assign/', views.admin_assign_tech_to_lab, name='admin_assign_tech_to_lab'),
    path('labs/<uuid:lab_id>/remove/<uuid:technician_id>/', views.admin_remove_tech_from_lab, name='admin_remove_tech_from_lab'),
    path('labs/<uuid:lab_id>/delete/', views.admin_delete_lab, name='admin_delete_lab'),

     # ── Doctor portal ─────────────────────────────────────────────────────
   
    path('staff/doctor/dashboard/',                  views.doctor_dashboard,        name='doctor_dashboard'),
    path('staff/doctor/profile/',                    views.doctor_profile,          name='doctor_profile'),
    path('staff/doctor/profile/update-personal/',    views.doctor_update_personal,  name='doctor_update_personal'),
    path('staff/doctor/profile/update-password/',    views.doctor_update_password,  name='doctor_update_password'),
    path('staff/doctor/patients/add/',               views.doctor_add_patient,      name='doctor_add_patient'),
    path('staff/doctor/lab-reports/',                views.doctor_lab_reports_list, name='doctor_lab_reports_list'),
    path('staff/doctor/medical-records/',            views.doctor_medical_records_list, name='doctor_medical_records_list'),
    path('staff/doctor/medical-records/<uuid:record_id>/', views.doctor_medical_record_detail, name='doctor_medical_record_detail'),
    path('staff/doctor/approval-queue/',             views.doctor_approval_queue, name='doctor_approval_queue'),
    path('staff/doctor/approval-queue/<uuid:item_id>/', views.doctor_approval_review, name='doctor_approval_review'),
    path('staff/doctor/records/',                    views.doctor_records_list,     name='doctor_records_list'),

     # ── Doctor portal — patients ───────────────────────────────────────────────
    path('staff/doctor/patients/',views.doctor_patients_list, name='doctor_patients_list'),
    path('staff/doctor/patients/<uuid:pk>/', views.doctor_patient_detail, name='doctor_patient_detail'),
    path('staff/doctor/patients/<uuid:pk>/lab-reports/', views.doctor_patient_lab_reports, name='doctor_patient_lab_reports'),
    path('staff/doctor/patients/<uuid:pk>/medical-records/', views.doctor_patient_medical_records, name='doctor_patient_medical_records'),
    path('staff/doctor/patients/<uuid:pk>/assign-nurse/', views.doctor_assign_nurse, name='doctor_assign_nurse'),
    path('staff/doctor/patients/<uuid:pk>/create-medical-record/', views.doctor_create_medical_record_page, name='doctor_create_medical_record_page'),
    path('staff/doctor/patients/<uuid:pk>/send-to-lab/', views.doctor_send_to_lab, name='doctor_send_to_lab'),
    path('staff/doctor/records/<uuid:record_id>/reassess/', views.doctor_reassess_record, name='doctor_reassess_record'),
    path('staff/doctor/patients/<uuid:pk>/remove-assignment/<uuid:staff_id>/',views.doctor_remove_assignment,name='doctor_remove_assignment'),

    # ── Nurse portal ─────────────────────────────────────────────────────────────
    path('staff/nurse/dashboard/',                      views.nurse_dashboard,          name='nurse_dashboard'),
    path('staff/nurse/queue/',                          views.nurse_queue,              name='nurse_queue'),
    path('staff/nurse/queue/<uuid:item_id>/',           views.nurse_queue_review,       name='nurse_queue_review'),
    path('staff/nurse/records/',                        views.nurse_medical_records_list, name='nurse_medical_records_list'),
    path('staff/nurse/records/<uuid:record_id>/',       views.nurse_medical_record_detail, name='nurse_medical_record_detail'),
    path('staff/nurse/profile/',                        views.nurse_profile,            name='nurse_profile'),
    path('staff/nurse/profile/update-personal/',        views.nurse_update_personal,    name='nurse_update_personal'),
    path('staff/nurse/profile/update-password/',        views.nurse_update_password,    name='nurse_update_password'),

    # ── Technician portal ─────────────────────────────────────────────────────────
    path('staff/technician/dashboard/',                   views.technician_dashboard,        name='technician_dashboard'),
    path('staff/technician/profile/',                     views.technician_profile,          name='technician_profile'),
    path('staff/technician/profile/update-personal/',     views.technician_update_personal,  name='technician_update_personal'),
    path('staff/technician/profile/update-password/',     views.technician_update_password,  name='technician_update_password'),
    path('staff/technician/lab/',                         views.technician_lab_queue,          name='technician_lab_queue'),
    path('staff/technician/lab/<uuid:request_id>/',       views.technician_lab_request_detail, name='technician_lab_request_detail'),
    path('staff/technician/lab/<uuid:request_id>/fill/',  views.technician_fill_record,       name='technician_fill_record'),
    path('staff/technician/records/',                     views.technician_records_list,      name='technician_records_list'),
    path('staff/technician/records/<uuid:record_id>/edit/', views.technician_edit_record,     name='technician_edit_record'),
    path('staff/technician/records/<uuid:record_id>/history/', views.technician_record_history, name='technician_record_history'),
    path('staff/records/<uuid:record_id>/',               views.view_record_detail,            name='view_record_detail'),
    path('staff/records/<uuid:record_id>/history/',       views.view_record_history,           name='view_record_history'),


]

