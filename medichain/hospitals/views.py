import json
import hashlib

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from .models import Hospital, Lab, HospitalUser, PatientAssignment, MedicalRecordMeta
from .decorators import hospital_admin_required , doctor_required , nurse_required, technician_required
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
    service_send_to_lab,
    service_create_lab,
    service_get_labs,
    service_get_lab_detail,
    service_assign_technician_to_lab,
    service_remove_technician_from_lab,
    service_delete_lab,
    service_get_available_technicians_for_lab,
    service_get_technician_dashboard_data, 
    service_get_technician_profile,
    service_update_technician_personal, 
    service_update_technician_password,
    service_get_nurse_profile,
    service_update_nurse_personal,
    service_update_nurse_password,
    service_create_nurse_queue_item,
    service_get_nurse_queue_items,
    service_get_nurse_queue_item_for_nurse,
    service_complete_nurse_queue_item,
    service_get_doctor_approval_queue_items,
    service_get_doctor_approval_item,
    service_finalize_doctor_approval_item,
    service_get_doctor_medical_records,
    service_get_nurse_medical_records,
    service_get_finalized_medical_record_detail,
    service_update_finalized_medical_record,
    service_get_lab_queue,
    service_get_lab_request,
    service_get_latest_lab_request_revision,
    service_get_existing_record_for_lab_request,
    service_get_technician_records,
    service_get_doctor_records,
    service_create_medical_record,
    service_edit_medical_record,
    service_get_record_history,
    service_get_record_detail,
    service_doctor_reassess_record,
   
)


# ─── Auth ─────────────────────────────────────────────────────────────────────

# render register page / handle hospital registration form
def hospital_register(request):
    if request.method != 'POST':
        return render(request, 'hospitals/auth/register.html')

    hospital, errors = service_register_hospital(
        hospital_name    = request.POST.get('hospital_name', '').strip(),
        email            = request.POST.get('email', '').strip().lower(),
        contact_number   = request.POST.get('contact_number', '').strip(),
        password         = request.POST.get('password', ''),
        confirm_password = request.POST.get('confirm_password', ''),
    )

    if errors:
        return JsonResponse({'success': False, 'errors': errors})

    # store hospital id in session so OTP page knows who to verify
    request.session['verify_hospital_id'] = str(hospital.id)
    return JsonResponse({'success': True, 'redirect': '/verify-otp/'})


# render OTP page / verify the entered OTP
def verify_otp(request):
    if 'verify_hospital_id' not in request.session:
        return redirect('/')

    hospital = Hospital.objects.get(id=request.session['verify_hospital_id'])

    if request.method == 'GET':
        return render(request, 'hospitals/auth/verify_otp.html', {'email': hospital.email})

    success, error = service_verify_otp(
        hospital_id = request.session['verify_hospital_id'],
        otp_entered = request.POST.get('otp', '').strip(),
    )

    if not success:
        return render(request, 'hospitals/auth/verify_otp.html', {
            'email': hospital.email,
            'error': error,
        })

    del request.session['verify_hospital_id']
    return render(request, 'hospitals/auth/verify_otp.html', {'success': True})


# generate a new OTP and resend to the hospital email
def resend_otp(request):
    if 'verify_hospital_id' not in request.session:
        return redirect('/')

    service_resend_otp(request.session['verify_hospital_id'])
    return redirect('/verify-otp/')


# handle login for hospital admin, doctor, and nurse from the same page
def hospital_login(request):
    if request.method != 'POST':
        return render(request, 'hospitals/auth/register.html')

    user_type, obj, errors = service_login(
        email    = request.POST.get('email', '').strip().lower(),
        password = request.POST.get('password', ''),
    )

    if errors:
        return JsonResponse({'success': False, 'errors': errors})

    if user_type == 'hospital_admin':
        # set admin session and redirect to admin dashboard
        request.session['hospital_id']    = str(obj.id)
        request.session['hospital_name']  = obj.hospital_name
        request.session['account_status'] = obj.account_status
        return JsonResponse({'success': True, 'redirect': '/dashboard/'})

    # set staff session — hospital_id needed for data scoping
    request.session['staff_id']       = str(obj.id)
    request.session['staff_name']     = obj.full_name
    request.session['staff_role']     = obj.role
    request.session['staff_hospital'] = obj.hospital.hospital_name
    request.session['hospital_id']    = str(obj.hospital.id)

    # route to role-specific dashboard
    if user_type == 'doctor':
        return JsonResponse({'success': True, 'redirect': '/staff/doctor/dashboard/'})
    if user_type == 'technician':
        return JsonResponse({'success': True, 'redirect': '/staff/technician/dashboard/'})
    return JsonResponse({'success': True, 'redirect': '/staff/nurse/dashboard/'})


# flush session and redirect to login page
def hospital_logout(request):
    request.session.flush()
    return redirect('/')


# ─── Hospital Admin — Dashboard & Profile ─────────────────────────────────────

# render admin dashboard with live counts
@hospital_admin_required
def hospital_dashboard(request):
    hospital, total_doctors, total_nurses, total_patients, total_technicians = service_get_dashboard_data(
        request.session['hospital_id']
    )
    return render(request, 'hospitals/admin/h_dashboard.html', {
        'hospital_name':       hospital.hospital_name,
        'hospital_email':      hospital.email,
        'hospital_contact':    hospital.contact_number,
        'hospital_license':    hospital.license_number,
        'hospital_address':    hospital.address,
        'account_status':      hospital.account_status,
        'total_patients':      total_patients,
        'total_records':       0,      # will be real count after records model is built
        'total_reports':       0,      # will be real count after reports model is built
        'total_doctors':       total_doctors,
        'total_nurses':        total_nurses,
        'total_technicians':   total_technicians,
        'recent_logs':         [],     # will be populated after audit log model is built
        'profile_incomplete':  getattr(request, 'profile_incomplete', False),
    })


# render hospital profile page
@hospital_admin_required
def hospital_profile(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    return render(request, 'hospitals/admin/h_profile.html', {'hospital': hospital})


# save and lock hospital name — can only be changed once
@hospital_admin_required
def hospital_update_name(request):
    if request.method != 'POST':
        return redirect('hospital_profile')

    hospital, error = service_update_name(
        hospital_id = request.session['hospital_id'],
        name        = request.POST.get('hospital_name', '').strip(),
    )

    if error:
        messages.error(request, error)
        return redirect('hospital_profile')

    # update session name to reflect the change immediately
    request.session['hospital_name'] = hospital.hospital_name
    messages.success(request, 'Hospital name saved and locked successfully.')
    return redirect('hospital_profile')


# save and lock license details — can only be set once
@hospital_admin_required
def hospital_update_license(request):
    if request.method != 'POST':
        return redirect('hospital_profile')

    hospital, error = service_update_license(
        hospital_id      = request.session['hospital_id'],
        license_number   = request.POST.get('license_number', '').strip(),
        license_document = request.FILES.get('license_document'),
    )

    if error:
        messages.error(request, error)
        return redirect('hospital_profile')

    # update session status if hospital got auto-activated
    request.session['account_status'] = hospital.account_status
    messages.success(request, 'License details saved and locked successfully.')
    return redirect('hospital_profile')


# update hospital address — editable anytime
@hospital_admin_required
def hospital_update_address(request):
    if request.method != 'POST':
        return redirect('hospital_profile')

    hospital, error = service_update_address(
        hospital_id = request.session['hospital_id'],
        address     = request.POST.get('address', '').strip(),
        city        = request.POST.get('city', '').strip(),
        state       = request.POST.get('state', '').strip(),
        country     = request.POST.get('country', '').strip(),
    )

    if error:
        messages.error(request, error)
        return redirect('hospital_profile')

    # update session status if hospital got auto-activated
    request.session['account_status'] = hospital.account_status
    messages.success(request, 'Address updated successfully.')
    return redirect('hospital_profile')


# change hospital admin password after verifying current password
@hospital_admin_required
def hospital_update_password(request):
    if request.method != 'POST':
        return redirect('hospital_profile')

    success, error = service_update_password(
        hospital_id      = request.session['hospital_id'],
        current_password = request.POST.get('current_password', ''),
        new_password     = request.POST.get('new_password', ''),
        confirm_password = request.POST.get('confirm_new_password', ''),
    )

    if error:
        messages.error(request, error)
        return redirect('hospital_profile')

    messages.success(request, 'Password updated successfully.')
    return redirect('hospital_profile')


# ─── Hospital Admin — Doctors ──────────────────────────────────────────────────

# list all doctors belonging to this hospital
@hospital_admin_required
def doctors_list(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    doctors  = service_get_doctors(request.session['hospital_id'])
    return render(request, 'hospitals/admin/doctors_list.html', {
        'hospital_name': hospital.hospital_name,
        'doctors':       doctors,
        'profile_incomplete': getattr(request, 'profile_incomplete', False),
    })


# register a new doctor and send credentials via email
@hospital_admin_required
def add_doctor(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/admin/add_doctor.html', {
            'hospital_name': hospital.hospital_name,
            'profile_incomplete': getattr(request, 'profile_incomplete', False),
        })

    # Block POST when profile incomplete
    if getattr(request, 'profile_incomplete', False):
        messages.error(request, 'Complete your hospital profile before registering staff.')
        return render(request, 'hospitals/admin/add_doctor.html', {
            'hospital_name': hospital.hospital_name,
            'form_data': request.POST,
        })

    doctor, errors = service_add_doctor(
        hospital_id    = request.session['hospital_id'],
        full_name      = request.POST.get('full_name', '').strip(),
        email          = request.POST.get('email', '').strip().lower(),
        phone          = request.POST.get('phone', '').strip(),
        employee_id    = request.POST.get('employee_id', '').strip(),
        specialization = request.POST.get('specialization', '').strip(),
    )

    if errors:
        return render(request, 'hospitals/admin/add_doctor.html', {
            'hospital_name': hospital.hospital_name,
            'errors':        errors,
            'form_data':     request.POST,
        })

    messages.success(request, f'Dr. {doctor.full_name} has been registered and credentials sent to {doctor.email}.')
    return redirect('doctors_list')


# view individual doctor details
@hospital_admin_required
def doctor_detail(request, pk):
    doctor, error = service_get_doctor(request.session['hospital_id'], pk)
    if error:
        messages.error(request, error)
        return redirect('doctors_list')

    return render(request, 'hospitals/admin/doctor_detail.html', {
        'hospital_name': request.session.get('hospital_name'),
        'doctor':        doctor,
    })


# activate / deactivate doctor toggle
@hospital_admin_required
def toggle_doctor(request, pk):
    if request.method != 'POST':
        return redirect('doctors_list')

    # Block POST when profile incomplete
    if getattr(request, 'profile_incomplete', False):
        messages.error(request, 'Complete your hospital profile before modifying staff status.')
        return redirect('doctors_list')

    doctor, error = service_toggle_doctor(request.session['hospital_id'], pk)
    if error:
        messages.error(request, error)
        return redirect('doctors_list')

    messages.success(request, f'{doctor.full_name} has been {"deactivated" if doctor.status == "inactive" else "activated"}.')
    return redirect('doctors_list')


# ─── Hospital Admin — Nurses ───────────────────────────────────────────────────

# list all nurses belonging to this hospital
@hospital_admin_required
def nurses_list(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    nurses   = service_get_nurses(request.session['hospital_id'])
    return render(request, 'hospitals/admin/nurses_list.html', {
        'hospital_name': hospital.hospital_name,
        'nurses':        nurses,
        'profile_incomplete': getattr(request, 'profile_incomplete', False),
    })


# register a new nurse and send credentials via email
@hospital_admin_required
def add_nurse(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/admin/add_nurse.html', {
            'hospital_name': hospital.hospital_name,
            'profile_incomplete': getattr(request, 'profile_incomplete', False),
        })

    # Block POST when profile incomplete
    if getattr(request, 'profile_incomplete', False):
        messages.error(request, 'Complete your hospital profile before registering staff.')
        return render(request, 'hospitals/admin/add_nurse.html', {
            'hospital_name': hospital.hospital_name,
            'form_data': request.POST,
        })

    nurse, errors = service_add_nurse(
        hospital_id = request.session['hospital_id'],
        full_name   = request.POST.get('full_name', '').strip(),
        email       = request.POST.get('email', '').strip().lower(),
        phone       = request.POST.get('phone', '').strip(),
        employee_id = request.POST.get('employee_id', '').strip(),
    )

    if errors:
        return render(request, 'hospitals/admin/add_nurse.html', {
            'hospital_name': hospital.hospital_name,
            'errors':        errors,
            'form_data':     request.POST,
        })

    messages.success(request, f'{nurse.full_name} has been registered and credentials sent to {nurse.email}.')
    return redirect('nurses_list')


# view individual nurse details
@hospital_admin_required
def nurse_detail(request, pk):
    nurse, error = service_get_nurse(request.session['hospital_id'], pk)
    if error:
        messages.error(request, error)
        return redirect('nurses_list')

    return render(request, 'hospitals/admin/nurse_detail.html', {
        'hospital_name': request.session.get('hospital_name'),
        'nurse':         nurse,
    })


# activate / deactivate nurse toggle
@hospital_admin_required
def toggle_nurse(request, pk):
    if request.method != 'POST':
        return redirect('nurses_list')

    # Block POST when profile incomplete
    if getattr(request, 'profile_incomplete', False):
        messages.error(request, 'Complete your hospital profile before modifying staff status.')
        return redirect('nurses_list')

    nurse, error = service_toggle_nurse(request.session['hospital_id'], pk)
    if error:
        messages.error(request, error)
        return redirect('nurses_list')

    messages.success(request, f'{nurse.full_name} has been {"deactivated" if nurse.status == "inactive" else "activated"}.')
    return redirect('nurses_list')


# ─── Hospital Admin — Technicians ─────────────────────────────────────────────

# list all technicians belonging to this hospital
@hospital_admin_required
def technicians_list(request):
    hospital     = Hospital.objects.get(id=request.session['hospital_id'])
    technicians  = service_get_technicians(request.session['hospital_id'])
    return render(request, 'hospitals/admin/technicians_list.html', {
        'hospital_name': hospital.hospital_name,
        'technicians':   technicians,
        'profile_incomplete': getattr(request, 'profile_incomplete', False),
    })


# register a new technician and send credentials via email
@hospital_admin_required
def add_technician(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/admin/add_technician.html', {
            'hospital_name': hospital.hospital_name,
            'profile_incomplete': getattr(request, 'profile_incomplete', False),
        })

    # Block POST when profile incomplete
    if getattr(request, 'profile_incomplete', False):
        messages.error(request, 'Complete your hospital profile before registering staff.')
        return render(request, 'hospitals/admin/add_technician.html', {
            'hospital_name': hospital.hospital_name,
            'form_data': request.POST,
        })

    technician, errors = service_add_technician(
        hospital_id = request.session['hospital_id'],
        full_name   = request.POST.get('full_name', '').strip(),
        email       = request.POST.get('email', '').strip().lower(),
        phone       = request.POST.get('phone', '').strip(),
        employee_id = request.POST.get('employee_id', '').strip(),
    )

    if errors:
        return render(request, 'hospitals/admin/add_technician.html', {
            'hospital_name': hospital.hospital_name,
            'errors':        errors,
            'form_data':     request.POST,
        })

    messages.success(request, f'{technician.full_name} has been registered and credentials sent to {technician.email}.')
    return redirect('technicians_list')


# view individual technician details
@hospital_admin_required
def technician_detail(request, pk):
    technician, error = service_get_technician(request.session['hospital_id'], pk)
    if error:
        messages.error(request, error)
        return redirect('technicians_list')

    return render(request, 'hospitals/admin/technician_detail.html', {
        'hospital_name': request.session.get('hospital_name'),
        'technician':    technician,
    })


# activate / deactivate technician toggle
@hospital_admin_required
def toggle_technician(request, pk):
    if request.method != 'POST':
        return redirect('technicians_list')

    # Block POST when profile incomplete
    if getattr(request, 'profile_incomplete', False):
        messages.error(request, 'Complete your hospital profile before modifying staff status.')
        return redirect('technicians_list')

    technician, error = service_toggle_technician(request.session['hospital_id'], pk)
    if error:
        messages.error(request, error)
        return redirect('technicians_list')

    messages.success(request, f'{technician.full_name} has been {"deactivated" if technician.status == "inactive" else "activated"}.')
    return redirect('technicians_list')


# ─── Hospital Admin — Patients ─────────────────────────────────────────────────

# list all patients registered by this hospital
@hospital_admin_required
def patients_list(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    patients = service_get_patients(request.session['hospital_id'])
    return render(request, 'hospitals/admin/patients_list.html', {
        'hospital_name': hospital.hospital_name,
        'patients':      patients,
        'profile_incomplete': getattr(request, 'profile_incomplete', False),
    })


# register a new patient with encrypted gov ID and duplicate detection
@hospital_admin_required
def add_patient(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/admin/add_patient.html', {
            'hospital_name': hospital.hospital_name,
            'profile_incomplete': getattr(request, 'profile_incomplete', False),
        })

    # Block POST when profile incomplete
    if getattr(request, 'profile_incomplete', False):
        messages.error(request, 'Complete your hospital profile before registering patients.')
        return render(request, 'hospitals/admin/add_patient.html', {
            'hospital_name': hospital.hospital_name,
            'form_data': request.POST,
        })

    patient, errors = service_add_patient(
        hospital_id   = request.session['hospital_id'],
        gov_id_type   = request.POST.get('gov_id_type', '').strip(),
        gov_id_number = request.POST.get('gov_id_number', '').strip(),
        full_name     = request.POST.get('full_name', '').strip(),
        gender        = request.POST.get('gender', '').strip() or None,
        phone         = request.POST.get('phone', '').strip() or None,
        email         = request.POST.get('email', '').strip().lower(),
        address       = request.POST.get('address', '').strip() or None,
    )

    if errors:
        return render(request, 'hospitals/admin/add_patient.html', {
            'hospital_name': hospital.hospital_name,
            'errors':        errors,
            'form_data':     request.POST,
        })

    messages.success(request, f'{patient.full_name} has been registered successfully.')
    return redirect('patients_list')


# view individual patient details with masked gov ID
@hospital_admin_required
def patient_detail(request, pk):
    patient, gov_id_masked, error = service_get_patient(pk)
    if error:
        messages.error(request, error)
        return redirect('patients_list')

    return render(request, 'hospitals/admin/patient_detail.html', {
        'hospital_name': request.session.get('hospital_name'),
        'patient':       patient,
        'gov_id_masked': gov_id_masked,
    })


# ─── Hospital Admin — Labs ───────────────────────────────────────────────────

@hospital_admin_required
def admin_labs_list(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    if request.method == 'POST':
        schema_raw = request.POST.get('custom_field_schema', '').strip()
        custom_field_schema = []
        if schema_raw:
            try:
                custom_field_schema = json.loads(schema_raw)
            except json.JSONDecodeError:
                messages.error(request, 'Custom field schema must be valid JSON.')
                return redirect('admin_labs_list')

        _, errors = service_create_lab(
            hospital_id=request.session['hospital_id'],
            lab_type=request.POST.get('lab_type', '').strip(),
            name=request.POST.get('name', '').strip(),
            custom_field_schema=custom_field_schema,
        )
        if errors:
            messages.error(request, ' '.join(errors.values()))
        else:
            messages.success(request, 'Lab created successfully.')
        return redirect('admin_labs_list')

    labs = service_get_labs(request.session['hospital_id'])
    return render(request, 'hospitals/admin/labs_list.html', {
        'hospital_name': hospital.hospital_name,
        'labs': labs,
        'lab_types': Lab.LAB_TYPE_CHOICES,
    })


@hospital_admin_required
def admin_lab_detail(request, lab_id):
    lab, assignments, pending_requests, completed_count, error = service_get_lab_detail(
        hospital_id=request.session['hospital_id'],
        lab_id=lab_id,
    )
    if error:
        messages.error(request, error)
        return redirect('admin_labs_list')

    available_technicians = service_get_available_technicians_for_lab(
        hospital_id=request.session['hospital_id'],
        lab_id=lab_id,
    )
    return render(request, 'hospitals/admin/lab_detail.html', {
        'hospital_name': request.session.get('hospital_name'),
        'lab': lab,
        'assignments': assignments,
        'pending_requests': pending_requests,
        'completed_count': completed_count,
        'available_technicians': available_technicians,
    })


@hospital_admin_required
def admin_assign_tech_to_lab(request, lab_id):
    if request.method != 'POST':
        return redirect('admin_lab_detail', lab_id=lab_id)

    _, error = service_assign_technician_to_lab(
        hospital_id=request.session['hospital_id'],
        lab_id=lab_id,
        technician_id=request.POST.get('technician_id', '').strip(),
    )
    if error:
        messages.error(request, error)
    else:
        messages.success(request, 'Technician assigned to lab.')
    return redirect('admin_lab_detail', lab_id=lab_id)


@hospital_admin_required
def admin_remove_tech_from_lab(request, lab_id, technician_id):
    if request.method != 'POST':
        return redirect('admin_lab_detail', lab_id=lab_id)

    success, error = service_remove_technician_from_lab(lab_id, technician_id)
    if not success:
        messages.error(request, error)
    else:
        messages.success(request, 'Technician removed from lab.')
    return redirect('admin_lab_detail', lab_id=lab_id)


@hospital_admin_required
def admin_delete_lab(request, lab_id):
    if request.method != 'POST':
        return redirect('admin_lab_detail', lab_id=lab_id)

    success, error = service_delete_lab(
        hospital_id=request.session['hospital_id'],
        lab_id=lab_id,
    )
    if not success:
        messages.error(request, error)
        return redirect('admin_lab_detail', lab_id=lab_id)

    messages.success(request, 'Lab archived successfully. You can create this lab type again later.')
    return redirect('admin_labs_list')

#list info in doctor's dashboard 
@doctor_required
def doctor_dashboard(request):
    total_patients, total_records, total_reports = service_get_doctor_dashboard_data(
        staff_id    = request.session['staff_id'],
        hospital_id = request.session['hospital_id'],
    )
    return render(request, 'hospitals/doctor/doctor_dashboard.html', {
        'staff_name':     request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
        'total_patients': total_patients,
        'total_records':  total_records,
        'total_reports':  total_reports,
        'recent_logs':    [],   # populate after audit log model is built
    })


@doctor_required
def doctor_profile(request):
    doctor, error = service_get_doctor_profile(request.session['staff_id'])
    if error:
        return redirect('doctor_dashboard')
    return render(request, 'hospitals/doctor/doctor_profile.html', {
        'doctor':         doctor,
        'staff_hospital': request.session.get('staff_hospital'),
        'staff_name':     request.session.get('staff_name'),
    })
 
 
@doctor_required
def doctor_update_personal(request):
    if request.method != 'POST':
        return redirect('doctor_profile')
 
    doctor, error = service_update_doctor_personal(
        staff_id         = request.session['staff_id'],
        date_of_birth    = request.POST.get('date_of_birth', '').strip() or None,
        gender           = request.POST.get('gender', '').strip() or None,
        years_experience = request.POST.get('years_experience', '').strip() or None,
        license_number   = request.POST.get('license_number', '').strip(),
        home_address     = request.POST.get('home_address', '').strip(),
        bio              = request.POST.get('bio', '').strip(),
    )
 
    if error:
        messages.error(request, error)
        return redirect('doctor_profile')
 
    messages.success(request, 'Personal details updated successfully.')
    return redirect('doctor_profile')
 
 
@doctor_required
def doctor_update_password(request):
    if request.method != 'POST':
        return redirect('doctor_profile')
 
    success, error = service_update_doctor_password(
        staff_id         = request.session['staff_id'],
        current_password = request.POST.get('current_password', ''),
        new_password     = request.POST.get('new_password', ''),
        confirm_password = request.POST.get('confirm_new_password', ''),
    )
 
    if error:
        # error can be a dict or a plain string
        msg = error if isinstance(error, str) else ' '.join(error.values())
        messages.error(request, msg)
        return redirect('doctor_profile')
 
    messages.success(request, 'Password updated successfully.')
    return redirect('doctor_profile')
 
 
@doctor_required
def doctor_add_patient(request):
    if request.method != 'POST':
        return render(request, 'hospitals/doctor/doctor_add_patient.html', {
            'staff_name':     request.session.get('staff_name'),
            'staff_hospital': request.session.get('staff_hospital'),
        })
 
    patient, errors = service_add_patient(
        hospital_id   = request.session['hospital_id'],
        gov_id_type   = request.POST.get('gov_id_type', '').strip(),
        gov_id_number = request.POST.get('gov_id_number', '').strip(),
        full_name     = request.POST.get('full_name', '').strip(),
        gender        = request.POST.get('gender', '').strip() or None,
        phone         = request.POST.get('phone', '').strip() or None,
        email         = request.POST.get('email', '').strip().lower(),
        address       = request.POST.get('address', '').strip() or None,
    )
 
    if errors:
        return render(request, 'hospitals/doctor/doctor_add_patient.html', {
            'staff_name':     request.session.get('staff_name'),
            'staff_hospital': request.session.get('staff_hospital'),
            'errors':         errors,
            'form_data':      request.POST,
        })
 
    messages.success(request, f'{patient.full_name} has been registered successfully.')
    return redirect('doctor_patients_list')  


@doctor_required
def doctor_records_list(request):
    return redirect('doctor_lab_reports_list')


@doctor_required
def doctor_lab_reports_list(request):
    gov_id_type = request.GET.get('gov_id_type', '').strip().lower()
    gov_id_number = request.GET.get('gov_id_number', '').strip()
    lab_id = request.GET.get('lab_id', '').strip()
    patient_id = request.GET.get('patient_id', '').strip()

    records, labs, grouped_records = service_get_doctor_records(
        hospital_id=request.session['hospital_id'],
        gov_id_type=gov_id_type,
        gov_id_number=gov_id_number,
        lab_id=lab_id,
        patient_id=patient_id,
        scope='lab',
    )

    return render(request, 'hospitals/doctor/doctor_records_list.html', {
        'records': records,
        'labs': labs,
        'grouped_records': grouped_records,
        'lab_id': lab_id,
        'patient_id': patient_id,
        'gov_id_type': gov_id_type,
        'gov_id_number': gov_id_number,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@doctor_required
def doctor_labs_list(request):
    labs = [
        row for row in service_get_labs(request.session['hospital_id'])
        if row['lab'].is_active
    ]
    return render(request, 'hospitals/doctor/doctor_labs_list.html', {
        'labs': labs,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@doctor_required
def doctor_lab_detail(request, lab_id):
    lab, assignments, pending_requests, completed_count, error = service_get_lab_detail(
        hospital_id=request.session['hospital_id'],
        lab_id=lab_id,
    )
    if error:
        messages.error(request, error)
        return redirect('doctor_labs_list')

    custom_field_schema = lab.custom_field_schema or []
    default_fields = [
        {'label': 'Diagnosis', 'key': 'diagnosis', 'fill_by': 'doctor'},
        {'label': 'Treatment Plan', 'key': 'treatment_plan', 'fill_by': 'doctor'},
        {'label': 'Notes', 'key': 'notes', 'fill_by': 'doctor'},
        {'label': 'Age', 'key': 'age', 'fill_by': 'technician'},
        {'label': 'Gender', 'key': 'gender', 'fill_by': 'technician'},
        {'label': 'Technician Change Reason', 'key': 'technician_change_reason', 'fill_by': 'technician'},
    ]

    doctor_fields = [field for field in default_fields if field['fill_by'] == 'doctor'] + [
        field for field in custom_field_schema if field.get('fill_by') == 'doctor'
    ]
    technician_fields = [field for field in default_fields if field['fill_by'] == 'technician'] + [
        field for field in custom_field_schema if field.get('fill_by') == 'technician'
    ]

    return render(request, 'hospitals/doctor/doctor_lab_detail.html', {
        'lab': lab,
        'assignments': assignments,
        'pending_requests': pending_requests,
        'completed_count': completed_count,
        'assigned_technicians_count': len(assignments),
        'doctor_fields': doctor_fields,
        'technician_fields': technician_fields,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@doctor_required
def doctor_medical_records_list(request):
    gov_id_type = request.GET.get('gov_id_type', '').strip().lower()
    gov_id_number = request.GET.get('gov_id_number', '').replace(' ', '').strip()

    records = service_get_doctor_medical_records(hospital_id=request.session['hospital_id'])

    if gov_id_type and gov_id_number:
        gov_id_hash = hashlib.sha256(f"{gov_id_type}{gov_id_number}".encode()).hexdigest()
        records = records.filter(patient__gov_id_hash=gov_id_hash)

    return render(request, 'hospitals/doctor/doctor_medical_records_list.html', {
        'records': records,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
        'gov_id_type': gov_id_type,
        'gov_id_number': gov_id_number,
    })


@doctor_required
def doctor_medical_record_detail(request, record_id):
    version_number = None
    version_query = request.GET.get('v', '').strip()
    if version_query:
        try:
            version_number = int(version_query)
        except ValueError:
            messages.error(request, 'Invalid medical record version requested.')
            return redirect('doctor_medical_record_detail', record_id=record_id)

    if request.method == 'POST':
        _, errors = service_update_finalized_medical_record(
            record_id=record_id,
            hospital_id=request.session.get('hospital_id'),
            doctor_id=request.session.get('staff_id'),
            data=request.POST,
            change_reason=request.POST.get('change_reason', ''),
        )
        if errors:
            messages.error(request, ' '.join(errors.values()))
            return redirect(f'{request.path}?edit=1')

        messages.success(request, 'Medical record updated successfully. A new version was created.')
        return redirect('doctor_medical_record_detail', record_id=record_id)

    record, detail_bundle, error = service_get_finalized_medical_record_detail(
        record_id=record_id,
        role='doctor',
        hospital_id=request.session.get('hospital_id'),
        staff_id=request.session.get('staff_id'),
        version_number=version_number,
    )
    if error:
        messages.error(request, error)
        return redirect('doctor_medical_records_list')

    return render(request, 'hospitals/medical_record_detail.html', {
        'record_item': record,
        'detail_bundle': detail_bundle,
        'viewer_role': 'doctor',
        'back_url_name': 'doctor_medical_records_list',
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
        'can_edit': bool(detail_bundle and detail_bundle.get('record', {}).get('is_latest')),
        'auto_open_edit': request.GET.get('edit') == '1',
    })


@doctor_required
def doctor_approval_queue(request):
    queue_items = service_get_doctor_approval_queue_items(
        hospital_id=request.session['hospital_id'],
    )
    return render(request, 'hospitals/doctor/doctor_approval_queue.html', {
        'queue_items': queue_items,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@doctor_required
def doctor_approval_review(request, item_id):
    item, error = service_get_doctor_approval_item(
        item_id=item_id,
        hospital_id=request.session['hospital_id'],
    )
    if error:
        messages.error(request, error)
        return redirect('doctor_approval_queue')

    if request.method == 'POST':
        if item.doctor_finalized:
            messages.info(request, 'This case is already finalized.')
            return redirect('doctor_approval_queue')

        next_appointment_date = request.POST.get('next_appointment_date', '').strip()
        doctor_final_notes = request.POST.get('doctor_final_notes', '').strip()

        if not doctor_final_notes:
            messages.error(request, 'Please add doctor final notes.')
            return redirect('doctor_approval_review', item_id=item_id)

        _, finalize_error = service_finalize_doctor_approval_item(
            item_id=item_id,
            hospital_id=request.session['hospital_id'],
            doctor_id=request.session['staff_id'],
            next_appointment_date=next_appointment_date or None,
            doctor_final_notes=doctor_final_notes,
        )
        if finalize_error:
            messages.error(request, finalize_error)
        else:
            messages.success(request, 'Case finalized successfully.')
            return redirect('doctor_approval_queue')

        item, _ = service_get_doctor_approval_item(
            item_id=item_id,
            hospital_id=request.session['hospital_id'],
        )

    return render(request, 'hospitals/doctor/doctor_approval_review.html', {
        'item': item,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


# ─── Doctor — Patients list ───────────────────────────────────────────────────

@doctor_required
def doctor_patients_list(request):
    gov_id_type = request.GET.get('gov_id_type', '').strip().lower()
    gov_id_number_query = request.GET.get('gov_id_number', '').strip()

    if (gov_id_type and not gov_id_number_query) or (gov_id_number_query and not gov_id_type):
        messages.error(request, 'Select ID type and enter ID number to search.')
    if gov_id_type and gov_id_type not in {'aadhar', 'voter'}:
        messages.error(request, 'Invalid government ID type selected.')

    patients = service_get_doctor_patients(
        hospital_id=request.session['hospital_id'],
        gov_id_type=gov_id_type if gov_id_type in {'aadhar', 'voter'} else '',
        gov_id_number_query=gov_id_number_query,
    )
    return render(request, 'hospitals/doctor/doctor_patients_list.html', {
        'patients':       patients,
        'gov_id_type': gov_id_type,
        'gov_id_number_query': gov_id_number_query,
        'staff_name':     request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


# ─── Doctor — Patient detail + assign ────────────────────────────────────────

@doctor_required
def doctor_patient_detail(request, pk):
    (
        patient,
        gov_id_masked,
        assigned_nurses,
        available_nurses,
        available_labs,
        patient_records,
        error
    ) = service_get_doctor_patient_detail(
        pk=pk,
        hospital_id=request.session['hospital_id']
    )

    if error:
        messages.error(request, error)
        return redirect('doctor_patients_list')

    lab_schema_map = {}
    for lab in available_labs:
        lab.custom_field_schema_json = json.dumps(lab.custom_field_schema or [])
        lab_schema_map[str(lab.id)] = lab.custom_field_schema or []

    current_hospital_id = str(request.session.get('hospital_id', ''))
    patient_registered_hospital = (
        patient.registered_by.hospital_name if patient.registered_by else 'Self Registered'
    )
    is_external_patient = (
        str(patient.registered_by_id) != current_hospital_id if patient.registered_by_id else True
    )

    return render(request, 'hospitals/doctor/doctor_patient_detail.html', {
        'patient':          patient,
        'gov_id_masked':    gov_id_masked,
        'assigned_nurses':  assigned_nurses,
        'available_nurses': available_nurses,
        'available_labs':   available_labs,
        'lab_schema_map':   lab_schema_map,
        'patient_records':  patient_records,
        'staff_name':       request.session.get('staff_name'),
        'staff_hospital':   request.session.get('staff_hospital'),
        'patient_registered_hospital': patient_registered_hospital,
        'is_external_patient': is_external_patient,
    })
@doctor_required
def doctor_assign_nurse(request, pk):
    if request.method != 'POST':
        return redirect('doctor_patient_detail', pk=pk)

    nurse_id = request.POST.get('nurse_id', '').strip()
    if not nurse_id:
        messages.error(request, 'Please select a nurse.')
        return redirect('doctor_patient_detail', pk=pk)

    assignment, error = service_assign_staff_to_patient(
        patient_id=pk,
        staff_id=nurse_id,
        role='nurse',
        assigned_by_id=request.session['staff_id'],
    )

    if error:
        messages.error(request, error)
    else:
        messages.success(request, f'{assignment.staff.full_name} assigned as nurse.')

    return redirect('doctor_patient_detail', pk=pk)


@doctor_required
def doctor_create_medical_record_page(request, pk):
    patient, gov_id_masked, assigned_nurses, _, _, _, error = service_get_doctor_patient_detail(
        pk=pk,
        hospital_id=request.session['hospital_id']
    )

    if error:
        messages.error(request, error)
        return redirect('doctor_patients_list')

    form_values = {
        'record_topic': '',
        'primary_diagnosis': '',
        'key_instruction': '',
        'doctor_note': '',
    }

    if request.method == 'POST':
        for key in form_values:
            form_values[key] = request.POST.get(key, '').strip()

        required_doctor_fields = {
            'record_topic': 'Record topic',
            'primary_diagnosis': 'Primary diagnosis',
            'key_instruction': 'Key clinical instruction',
        }
        missing = [label for key, label in required_doctor_fields.items() if not form_values[key]]

        if missing:
            messages.error(request, f"Please complete doctor-required fields: {', '.join(missing)}")
        else:
            handwritten = request.FILES.get('file_handwritten')
            if not handwritten:
                messages.error(request, 'Please upload the handwritten prescription/note before forwarding to nurse queue.')
            else:
                item, error = service_create_nurse_queue_item(
                    hospital_id=request.session['hospital_id'],
                    patient_id=pk,
                    doctor_id=request.session['staff_id'],
                    title=form_values['record_topic'],
                    primary_diagnosis=form_values['primary_diagnosis'],
                    key_instruction=form_values['key_instruction'],
                    doctor_note=form_values['doctor_note'],
                    handwritten_file=handwritten,
                )

                if error:
                    messages.error(request, error)
                else:
                    messages.success(request, 'Record forwarded to hospital nursing queue. Any available nurse can pick it up.')
                    return redirect('doctor_patient_detail', pk=pk)

    return render(request, 'hospitals/doctor/doctor_create_medical_record.html', {
        'patient': patient,
        'gov_id_masked': gov_id_masked,
        'assigned_nurses': assigned_nurses,
        'form_values': form_values,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@doctor_required
def doctor_send_to_lab(request, pk):
    if request.method != 'POST':
        return redirect('doctor_patient_detail', pk=pk)

    lab_id = request.POST.get('lab_id', '').strip()
    custom_field_values = {}
    custom_field_values_raw = request.POST.get('custom_field_values', '').strip()
    if custom_field_values_raw:
        try:
            custom_field_values = json.loads(custom_field_values_raw)
        except json.JSONDecodeError:
            custom_field_values = {}
    if lab_id:
        try:
            lab = Lab.objects.get(id=lab_id, hospital_id=request.session['hospital_id'], is_active=True)
            for field in lab.custom_field_schema or []:
                key = field.get('key')
                if not key:
                    continue
                if key not in custom_field_values:
                    value = request.POST.get(f'custom_{key}', '').strip()
                    if value:
                        custom_field_values[key] = value
        except Lab.DoesNotExist:
            messages.error(request, 'Selected lab was not found.')
            return redirect('doctor_patient_detail', pk=pk)

    _, errors = service_send_to_lab(
        patient_id=pk,
        lab_id=lab_id,
        doctor_id=request.session['staff_id'],
        chest_pain_type=request.POST.get('chest_pain_type', '').strip(),
        diagnosis=request.POST.get('diagnosis', '').strip(),
        treatment_plan=request.POST.get('treatment_plan', '').strip(),
        notes=request.POST.get('notes', '').strip(),
        custom_field_values=custom_field_values,
    )

    if errors:
        messages.error(request, ' '.join(errors.values()))
    else:
        messages.success(request, 'Lab request created successfully.')
    return redirect('doctor_patient_detail', pk=pk)


# ─── Doctor — Remove assignment ───────────────────────────────────────────────

@doctor_required
def doctor_remove_assignment(request, pk, staff_id):
    """pk = patient UUID, staff_id = HospitalUser UUID"""
    if request.method != 'POST':
        return redirect('doctor_patient_detail', pk=pk)

    success, error = service_remove_staff_from_patient(
        patient_id=pk,
        staff_id=staff_id,
    )

    if error:
        messages.error(request, error)
    else:
        messages.success(request, 'Assignment removed.')

    return redirect('doctor_patient_detail', pk=pk)



# ─── Technician Portal ────────────────────────────────────────────────────────

@nurse_required
def nurse_dashboard(request):
    staff_id = request.session.get('staff_id')
    hospital_id = request.session.get('hospital_id')

    assigned_patients = PatientAssignment.objects.filter(
        staff_id=staff_id,
        role='nurse',
        patient__registered_by_id=hospital_id,
    ).count()

    completed_updates = MedicalRecordMeta.objects.filter(
        hospital_id=hospital_id,
        recorded_by_id=staff_id,
    ).count()

    pending_queue = service_get_nurse_queue_items(hospital_id=hospital_id, status='pending').count()

    return render(request, 'hospitals/nurse/nurse_dashboard.html', {
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
        'total_assigned_patients': assigned_patients,
        'total_pending_queue': pending_queue,
        'total_completed_updates': completed_updates,
    })


@nurse_required
def nurse_queue(request):
    queue_items = service_get_nurse_queue_items(
        hospital_id=request.session['hospital_id'],
        status=['pending', 'in_progress'],
    )
    return render(request, 'hospitals/nurse/nurse_queue.html', {
        'queue_items': queue_items,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@nurse_required
def nurse_queue_review(request, item_id):
    item, error = service_get_nurse_queue_item_for_nurse(
        item_id=item_id,
        hospital_id=request.session['hospital_id'],
    )
    if error:
        messages.error(request, error)
        return redirect('nurse_queue')

    nurse_id = request.session['staff_id']
    is_picked_by_other = item.picked_by_id and str(item.picked_by_id) != str(nurse_id)

    if request.method == 'GET' and item.status == 'pending' and not item.picked_by_id:
        item.picked_by_id = nurse_id
        item.status = 'in_progress'
        item.save(update_fields=['picked_by', 'status', 'updated_at'])

    if request.method == 'POST':
        if item.status == 'completed':
            messages.info(request, 'This case is already completed.')
            return redirect('nurse_queue_review', item_id=item_id)

        if is_picked_by_other:
            messages.error(request, f'This case is currently being handled by {item.picked_by.full_name}.')
            return redirect('nurse_queue')

        blood_pressure = request.POST.get('blood_pressure', '').strip()
        pulse_rate = request.POST.get('pulse_rate', '').strip()
        temperature_c = request.POST.get('temperature_c', '').strip()
        spo2_percent = request.POST.get('spo2_percent', '').strip()
        random_blood_sugar = request.POST.get('random_blood_sugar', '').strip()
        nurse_tests_performed = request.POST.get('nurse_tests_performed', '').strip()
        nurse_observation = request.POST.get('nurse_observation', '').strip()
        treatment_given = request.POST.get('treatment_given', '').strip()
        medications_administered = request.POST.get('medications_administered', '').strip()
        follow_up_notes = request.POST.get('follow_up_notes', '').strip()

        missing = []
        if not blood_pressure:
            missing.append('Blood pressure')
        if not pulse_rate:
            missing.append('Pulse rate')
        if not temperature_c:
            missing.append('Temperature')
        if not spo2_percent:
            missing.append('SpO2')
        if not random_blood_sugar:
            missing.append('Random blood sugar')
        if not nurse_tests_performed:
            missing.append('Nurse tests performed')
        if not nurse_observation:
            missing.append('Nurse observation')
        if not treatment_given:
            missing.append('Treatment given')
        if not medications_administered:
            missing.append('Medications administered')

        if missing:
            messages.error(request, f"Please complete required fields: {', '.join(missing)}")
        else:
            _, complete_error = service_complete_nurse_queue_item(
                item_id=item_id,
                hospital_id=request.session['hospital_id'],
                nurse_id=nurse_id,
                blood_pressure=blood_pressure,
                pulse_rate=pulse_rate,
                temperature_c=temperature_c,
                spo2_percent=spo2_percent,
                random_blood_sugar=random_blood_sugar,
                nurse_tests_performed=nurse_tests_performed,
                nurse_observation=nurse_observation,
                treatment_given=treatment_given,
                medications_administered=medications_administered,
                follow_up_notes=follow_up_notes,
            )
            if complete_error:
                messages.error(request, complete_error)
            else:
                messages.success(request, 'Nurse treatment details saved successfully.')
                return redirect('nurse_queue')

        item, _ = service_get_nurse_queue_item_for_nurse(
            item_id=item_id,
            hospital_id=request.session['hospital_id'],
        )

    return render(request, 'hospitals/nurse/nurse_queue_review.html', {
        'item': item,
        'is_picked_by_other': is_picked_by_other,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@nurse_required
def nurse_medical_records_list(request):
    gov_id_type = request.GET.get('gov_id_type', '').strip().lower()
    gov_id_number = request.GET.get('gov_id_number', '').replace(' ', '').strip()

    records = service_get_nurse_medical_records(
        hospital_id=request.session['hospital_id'],
        nurse_id=request.session['staff_id'],
    )

    if gov_id_type and gov_id_number:
        gov_id_hash = hashlib.sha256(f"{gov_id_type}{gov_id_number}".encode()).hexdigest()
        records = records.filter(patient__gov_id_hash=gov_id_hash)

    return render(request, 'hospitals/nurse/nurse_records_list.html', {
        'records': records,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
        'gov_id_type': gov_id_type,
        'gov_id_number': gov_id_number,
    })


@nurse_required
def nurse_medical_record_detail(request, record_id):
    version_number = None
    version_query = request.GET.get('v', '').strip()
    if version_query:
        try:
            version_number = int(version_query)
        except ValueError:
            messages.error(request, 'Invalid medical record version requested.')
            return redirect('nurse_medical_record_detail', record_id=record_id)

    record, detail_bundle, error = service_get_finalized_medical_record_detail(
        record_id=record_id,
        role='nurse',
        hospital_id=request.session.get('hospital_id'),
        staff_id=request.session.get('staff_id'),
        version_number=version_number,
    )
    if error:
        messages.error(request, error)
        return redirect('nurse_medical_records_list')

    return render(request, 'hospitals/medical_record_detail.html', {
        'record_item': record,
        'detail_bundle': detail_bundle,
        'viewer_role': 'nurse',
        'back_url_name': 'nurse_medical_records_list',
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@nurse_required
def nurse_profile(request):
    nurse, error = service_get_nurse_profile(request.session['staff_id'])
    if error:
        messages.error(request, error)
        return redirect('nurse_dashboard')

    return render(request, 'hospitals/nurse/nurse_profile.html', {
        'nurse': nurse,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@nurse_required
def nurse_update_personal(request):
    if request.method != 'POST':
        return redirect('nurse_profile')

    nurse, error = service_update_nurse_personal(
        staff_id         = request.session['staff_id'],
        date_of_birth    = request.POST.get('date_of_birth', '').strip() or None,
        gender           = request.POST.get('gender', '').strip() or None,
        years_experience = request.POST.get('years_experience', '').strip() or None,
        license_number   = request.POST.get('license_number', '').strip(),
        home_address     = request.POST.get('home_address', '').strip(),
        bio              = request.POST.get('bio', '').strip(),
    )

    if error:
        messages.error(request, error)
    else:
        messages.success(request, 'Personal details updated successfully.')

    return redirect('nurse_profile')


@nurse_required
def nurse_update_password(request):
    if request.method != 'POST':
        return redirect('nurse_profile')

    success, error = service_update_nurse_password(
        staff_id         = request.session['staff_id'],
        current_password = request.POST.get('current_password', ''),
        new_password     = request.POST.get('new_password', ''),
        confirm_password = request.POST.get('confirm_new_password', ''),
    )

    if error:
        messages.error(request, str(error))
    else:
        messages.success(request, 'Password updated successfully.')

    return redirect('nurse_profile')

@technician_required
def technician_dashboard(request):
    total_patients, total_records, total_reports = service_get_technician_dashboard_data(
        staff_id=request.session['staff_id'],
    )
    return render(request, 'hospitals/technician/technician_dashboard.html', {
        'staff_name':     request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
        'total_patients': total_patients,
        'total_records':  total_records,
        'total_reports':  total_reports,
    })


@technician_required
def technician_profile(request):
    technician, error = service_get_technician_profile(request.session['staff_id'])
    if error:
        messages.error(request, error)
        return redirect('technician_dashboard')
    return render(request, 'hospitals/technician/technician_profile.html', {
        'technician':     technician,
        'staff_name':     request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@technician_required
def technician_update_personal(request):
    if request.method != 'POST':
        return redirect('technician_profile')

    technician, error = service_update_technician_personal(
        staff_id         = request.session['staff_id'],
        date_of_birth    = request.POST.get('date_of_birth', '').strip() or None,
        gender           = request.POST.get('gender', '').strip() or None,
        years_experience = request.POST.get('years_experience', '').strip() or None,
        license_number   = request.POST.get('license_number', '').strip(),
        home_address     = request.POST.get('home_address', '').strip(),
        bio              = request.POST.get('bio', '').strip(),
    )

    if error:
        messages.error(request, error)
    else:
        messages.success(request, 'Personal details updated successfully.')

    return redirect('technician_profile')


@technician_required
def technician_update_password(request):
    if request.method != 'POST':
        return redirect('technician_profile')

    success, error = service_update_technician_password(
        staff_id         = request.session['staff_id'],
        current_password = request.POST.get('current_password', ''),
        new_password     = request.POST.get('new_password', ''),
        confirm_password = request.POST.get('confirm_new_password', ''),
    )

    if error:
        messages.error(request, str(error))
    else:
        messages.success(request, 'Password updated successfully.')

    return redirect('technician_profile')


@technician_required
def technician_lab_queue(request):
    queue = service_get_lab_queue(staff_id=request.session['staff_id'])
    return render(request, 'hospitals/technician/lab_queue.html', {
        'queue':          queue,
        'staff_name':     request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@technician_required
def technician_lab_request_detail(request, request_id):
    lab_request, error = service_get_lab_request(
        staff_id=request.session['staff_id'],
        request_id=request_id,
    )
    if error:
        messages.error(request, error)
        return redirect('technician_lab_queue')

    latest_revision = service_get_latest_lab_request_revision(request_id)
    existing_record = service_get_existing_record_for_lab_request(
        lab_request_id=request_id,
        hospital_id=request.session['hospital_id'],
    )

    return render(request, 'hospitals/technician/fill_record.html', {
        'lab_request':     lab_request,
        'latest_revision': latest_revision,
        'existing_record': existing_record,
        'lab_custom_field_schema': lab_request.lab.custom_field_schema or [],
        'existing_custom_field_values': getattr(existing_record, 'custom_field_values', {}) if existing_record else {},
        'requires_change_reason': bool(existing_record),
        'staff_name':      request.session.get('staff_name'),
        'staff_hospital':  request.session.get('staff_hospital'),
        'ecg_choices': [
            ('normal', 'Normal'),
            ('st_t_abnormality', 'ST-T abnormality'),
            ('lvh', 'LVH'),
        ],
    })


@technician_required
def technician_fill_record(request, request_id):
    if request.method != 'POST':
        return redirect('technician_lab_request_detail', request_id=request_id)

    custom_field_values = {}
    custom_field_values_raw = request.POST.get('custom_field_values', '').strip()
    if custom_field_values_raw:
        try:
            custom_field_values = json.loads(custom_field_values_raw)
        except json.JSONDecodeError:
            custom_field_values = {}

    data = {
        'age': request.POST.get('age', '').strip(),
        'gender': request.POST.get('gender', '').strip(),
        'custom_field_values': custom_field_values,
    }
    record, errors = service_create_medical_record(
        lab_request_id=request_id,
        technician_id=request.session['staff_id'],
        hospital_id=request.session['hospital_id'],
        data=data,
        technician_reason=request.POST.get('technician_change_reason', '').strip(),
    )
    if errors:
        messages.error(request, ' '.join(errors.values()))
        return redirect('technician_lab_request_detail', request_id=request_id)

    messages.success(request, 'Medical record created successfully.')
    return redirect('view_record_detail', record_id=record.record_id)


@technician_required
def technician_edit_record(request, record_id):
    if request.method != 'POST':
        return redirect('view_record_detail', record_id=record_id)

    custom_field_values = {}
    custom_field_values_raw = request.POST.get('custom_field_values', '').strip()
    if custom_field_values_raw:
        try:
            custom_field_values = json.loads(custom_field_values_raw)
        except json.JSONDecodeError:
            custom_field_values = {}

    data = {
        'age': request.POST.get('age', '').strip(),
        'gender': request.POST.get('gender', '').strip(),
        'custom_field_values': custom_field_values,
    }
    _, errors = service_edit_medical_record(
        record_id=record_id,
        technician_id=request.session['staff_id'],
        hospital_id=request.session['hospital_id'],
        data=data,
        change_reason=request.POST.get('change_reason', '').strip(),
    )
    if errors:
        messages.error(request, ' '.join(errors.values()))
    else:
        messages.success(request, 'Record updated successfully.')
    return redirect('view_record_detail', record_id=record_id)


@technician_required
def technician_record_history(request, record_id):
    return view_record_history(request, record_id)


@technician_required
def technician_records_list(request):
    records = service_get_technician_records(
        staff_id=request.session['staff_id'],
        hospital_id=request.session['hospital_id'],
    )
    return render(request, 'hospitals/technician/records_list.html', {
        'records': records,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@doctor_required
def doctor_reassess_record(request, record_id):
    if request.method != 'POST':
        return redirect('view_record_detail', record_id=record_id)

    reassess_action = (request.POST.get('reassess_action') or 'send_to_queue').strip().lower()
    send_to_queue = reassess_action != 'update_only'

    _, errors = service_doctor_reassess_record(
        record_id=record_id,
        doctor_id=request.session['staff_id'],
        hospital_id=request.session['hospital_id'],
        chest_pain_type=request.POST.get('chest_pain_type', '').strip(),
        diagnosis=request.POST.get('diagnosis', '').strip(),
        treatment_plan=request.POST.get('treatment_plan', '').strip(),
        notes=request.POST.get('notes', '').strip(),
        reason=request.POST.get('reason', '').strip(),
        send_to_queue=send_to_queue,
    )
    if errors:
        messages.error(request, ' '.join(errors.values()))
    else:
        if send_to_queue:
            messages.success(request, 'Doctor reassessment submitted. Request moved back to technician queue.')
        else:
            messages.success(request, 'Doctor update saved. Request status was not changed.')
    return redirect('view_record_detail', record_id=record_id)


def view_record_detail(request, record_id):
    if not request.session.get('staff_id'):
        return redirect('hospital_login')

    version_number = None
    version_query = request.GET.get('v', '').strip()
    if version_query:
        try:
            version_number = int(version_query)
        except ValueError:
            messages.error(request, 'Invalid record version requested.')
            return redirect('view_record_detail', record_id=record_id)

    record, lab_request, detail_bundle, error = service_get_record_detail(
        record_id=record_id,
        hospital_id=request.session.get('hospital_id'),
        version_number=version_number,
    )
    if error:
        messages.error(request, error)
        role = request.session.get('staff_role')
        if role == 'technician':
            return redirect('technician_lab_queue')
        return redirect('doctor_patients_list')

    staff_role = request.session.get('staff_role')
    can_edit = staff_role == 'technician' and record.is_latest
    can_doctor_reassess = staff_role == 'doctor' and record.is_latest

    active_page = 'lab_reports' if staff_role == 'doctor' else 'lab_queue'

    return render(request, 'hospitals/technician/record_detail.html', {
        'record': record,
        'lab_request': lab_request,
        'audit': detail_bundle['audit'],
        'timeline': detail_bundle['timeline'],
        'custom_field_values': detail_bundle.get('custom_field_values', {}),
        'can_edit': can_edit,
        'can_doctor_reassess': can_doctor_reassess,
        'auto_open_edit': can_edit and request.GET.get('edit') == '1',
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
        'active_page': active_page,
    })


def view_record_history(request, record_id):
    if not request.session.get('staff_id'):
        return redirect('hospital_login')

    history = service_get_record_history(
        record_id=record_id,
        hospital_id=request.session.get('hospital_id'),
    )
    return render(request, 'hospitals/technician/record_history.html', {
        'history': history,
        'record_id': record_id,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
        'staff_role': request.session.get('staff_role'),
        'active_page': 'lab_reports' if request.session.get('staff_role') == 'doctor' else 'lab_queue',
    })


# --- Doctor Patient-Specific Records Pages -----------------------------------

@doctor_required
def doctor_patient_lab_reports(request, pk):
    """
    View lab reports for a specific patient.
    Shows only that patient's lab reports and buttons to access reports from other hospitals.
    """
    from consentmanagement.models import ConsentRequest
    from .models import Hospital
    
    # Get patient details
    patient, gov_id_masked, _, _, _, patient_records, error = service_get_doctor_patient_detail(
        pk=pk,
        hospital_id=request.session['hospital_id']
    )
    
    if error:
        messages.error(request, error)
        return redirect('doctor_patients_list')
    
    # Filter only lab records (records with lab_request)
    lab_records = [r for r in patient_records if r.lab_request is not None]
    
    # Get all hospitals for consent button display
    all_hospitals = Hospital.objects.exclude(id=request.session['hospital_id'])
    
    # Get existing consent requests for this patient and hospital
    current_hospital_id = request.session['hospital_id']
    consent_requests = ConsentRequest.objects.filter(
        patient_id=str(pk),
        requesting_hospital=str(current_hospital_id)
    )
    
    return render(request, 'hospitals/doctor/doctor_patient_lab_reports.html', {
        'patient': patient,
        'gov_id_masked': gov_id_masked,
        'lab_records': lab_records,
        'all_hospitals': all_hospitals,
        'consent_requests': consent_requests,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })


@doctor_required
def doctor_patient_medical_records(request, pk):
    """
    View medical records for a specific patient.
    Shows only that patient's medical records and buttons to access records from other hospitals.
    """
    from consentmanagement.models import ConsentRequest
    from .models import Hospital
    
    # Get patient details
    patient, gov_id_masked, _, _, _, patient_records, error = service_get_doctor_patient_detail(
        pk=pk,
        hospital_id=request.session['hospital_id']
    )
    
    if error:
        messages.error(request, error)
        return redirect('doctor_patients_list')
    
    # Filter only medical records (records without lab_request)
    medical_records = [r for r in patient_records if r.lab_request is None]
    
    # Get all hospitals for consent button display
    all_hospitals = Hospital.objects.exclude(id=request.session['hospital_id'])
    
    # Get existing consent requests for this patient and hospital
    current_hospital_id = request.session['hospital_id']
    consent_requests = ConsentRequest.objects.filter(
        patient_id=str(pk),
        requesting_hospital=str(current_hospital_id)
    )
    
    return render(request, 'hospitals/doctor/doctor_patient_medical_records.html', {
        'patient': patient,
        'gov_id_masked': gov_id_masked,
        'medical_records': medical_records,
        'all_hospitals': all_hospitals,
        'consent_requests': consent_requests,
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
    })
