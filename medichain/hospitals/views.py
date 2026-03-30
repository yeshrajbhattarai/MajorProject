from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from .models import Hospital
from .decorators import hospital_admin_required , doctor_required , technician_required
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
    service_get_available_technicians_for_lab,
    service_get_technician_dashboard_data, 
    service_get_technician_profile,
    service_update_technician_personal, 
    service_update_technician_password,
    service_get_lab_queue,
    service_get_lab_request,
    service_get_latest_lab_request_revision,
    service_get_existing_record_for_lab_request,
    service_get_technician_records,
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
    })


# register a new doctor and send credentials via email
@hospital_admin_required
def add_doctor(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/admin/add_doctor.html', {
            'hospital_name': hospital.hospital_name,
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
    })


# register a new nurse and send credentials via email
@hospital_admin_required
def add_nurse(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/admin/add_nurse.html', {
            'hospital_name': hospital.hospital_name,
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
    })


# register a new technician and send credentials via email
@hospital_admin_required
def add_technician(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/admin/add_technician.html', {
            'hospital_name': hospital.hospital_name,
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
    })


# register a new patient with encrypted gov ID and duplicate detection
@hospital_admin_required
def add_patient(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/admin/add_patient.html', {
            'hospital_name': hospital.hospital_name,
        })

    patient, errors = service_add_patient(
        hospital_id   = request.session['hospital_id'],
        gov_id_type   = request.POST.get('gov_id_type', '').strip(),
        gov_id_number = request.POST.get('gov_id_number', '').strip(),
        full_name     = request.POST.get('full_name', '').strip(),
        gender        = request.POST.get('gender', '').strip() or None,
        phone         = request.POST.get('phone', '').strip() or None,
        email         = request.POST.get('email', '').strip().lower() or None,
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
        _, errors = service_create_lab(
            hospital_id=request.session['hospital_id'],
            lab_type=request.POST.get('lab_type', '').strip(),
            name=request.POST.get('name', '').strip(),
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
        email         = request.POST.get('email', '').strip().lower() or None,
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


# ─── Doctor — Patients list ───────────────────────────────────────────────────

@doctor_required
def doctor_patients_list(request):
    patients = service_get_doctor_patients(
        hospital_id=request.session['hospital_id']
    )
    return render(request, 'hospitals/doctor/doctor_patients_list.html', {
        'patients':       patients,
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

    return render(request, 'hospitals/doctor/doctor_patient_detail.html', {
        'patient':          patient,
        'gov_id_masked':    gov_id_masked,
        'assigned_nurses':  assigned_nurses,
        'available_nurses': available_nurses,
        'available_labs':   available_labs,
        'patient_records':  patient_records,
        'staff_name':       request.session.get('staff_name'),
        'staff_hospital':   request.session.get('staff_hospital'),
    })


# ─── Doctor — Assign nurse ────────────────────────────────────────────────────

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
def doctor_send_to_lab(request, pk):
    if request.method != 'POST':
        return redirect('doctor_patient_detail', pk=pk)

    _, errors = service_send_to_lab(
        patient_id=pk,
        lab_id=request.POST.get('lab_id', '').strip(),
        doctor_id=request.session['staff_id'],
        chest_pain_type=request.POST.get('chest_pain_type', '').strip(),
        diagnosis=request.POST.get('diagnosis', '').strip(),
        treatment_plan=request.POST.get('treatment_plan', '').strip(),
        notes=request.POST.get('notes', '').strip(),
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

    data = {
        'age': request.POST.get('age', '').strip(),
        'gender': request.POST.get('gender', '').strip(),
        'blood_pressure_systolic': request.POST.get('blood_pressure_systolic', '').strip(),
        'blood_pressure_diastolic': request.POST.get('blood_pressure_diastolic', '').strip(),
        'cholesterol': request.POST.get('cholesterol', '').strip(),
        'blood_glucose': request.POST.get('blood_glucose', '').strip(),
        'heart_rate': request.POST.get('heart_rate', '').strip(),
        'ecg_result': request.POST.get('ecg_result', '').strip(),
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

    data = {
        'age': request.POST.get('age', '').strip(),
        'gender': request.POST.get('gender', '').strip(),
        'blood_pressure_systolic': request.POST.get('blood_pressure_systolic', '').strip(),
        'blood_pressure_diastolic': request.POST.get('blood_pressure_diastolic', '').strip(),
        'cholesterol': request.POST.get('cholesterol', '').strip(),
        'blood_glucose': request.POST.get('blood_glucose', '').strip(),
        'heart_rate': request.POST.get('heart_rate', '').strip(),
        'ecg_result': request.POST.get('ecg_result', '').strip(),
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

    _, errors = service_doctor_reassess_record(
        record_id=record_id,
        doctor_id=request.session['staff_id'],
        hospital_id=request.session['hospital_id'],
        chest_pain_type=request.POST.get('chest_pain_type', '').strip(),
        diagnosis=request.POST.get('diagnosis', '').strip(),
        treatment_plan=request.POST.get('treatment_plan', '').strip(),
        notes=request.POST.get('notes', '').strip(),
        reason=request.POST.get('reason', '').strip(),
    )
    if errors:
        messages.error(request, ' '.join(errors.values()))
    else:
        messages.success(request, 'Doctor reassessment submitted. Request moved back to technician queue.')
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

    return render(request, 'hospitals/technician/record_detail.html', {
        'record': record,
        'lab_request': lab_request,
        'audit': detail_bundle['audit'],
        'timeline': detail_bundle['timeline'],
        'can_edit': can_edit,
        'can_doctor_reassess': can_doctor_reassess,
        'auto_open_edit': can_edit and request.GET.get('edit') == '1',
        'staff_name': request.session.get('staff_name'),
        'staff_hospital': request.session.get('staff_hospital'),
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
    })