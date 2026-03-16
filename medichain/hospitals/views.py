from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from .models import Hospital
from .decorators import hospital_admin_required
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
    service_get_patients,
    service_add_patient,
    service_get_patient,
)


# ─── Auth ─────────────────────────────────────────────────────────────────────

# render register page / handle hospital registration form
def hospital_register(request):
    if request.method != 'POST':
        return render(request, 'hospitals/register.html')

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
        return render(request, 'hospitals/verify_otp.html', {'email': hospital.email})

    success, error = service_verify_otp(
        hospital_id = request.session['verify_hospital_id'],
        otp_entered = request.POST.get('otp', '').strip(),
    )

    if not success:
        return render(request, 'hospitals/verify_otp.html', {
            'email': hospital.email,
            'error': error,
        })

    del request.session['verify_hospital_id']
    return render(request, 'hospitals/verify_otp.html', {'success': True})


# generate a new OTP and resend to the hospital email
def resend_otp(request):
    if 'verify_hospital_id' not in request.session:
        return redirect('/')

    service_resend_otp(request.session['verify_hospital_id'])
    return redirect('/verify-otp/')


# handle login for hospital admin, doctor, and nurse from the same page
def hospital_login(request):
    if request.method != 'POST':
        return render(request, 'hospitals/register.html')

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
    return JsonResponse({'success': True, 'redirect': '/staff/nurse/dashboard/'})


# flush session and redirect to login page
def hospital_logout(request):
    request.session.flush()
    return redirect('/')


# ─── Hospital Admin — Dashboard & Profile ─────────────────────────────────────

# render admin dashboard with live counts
@hospital_admin_required
def hospital_dashboard(request):
    hospital, total_doctors, total_nurses, total_patients = service_get_dashboard_data(
        request.session['hospital_id']
    )
    return render(request, 'hospitals/h_dashboard.html', {
        'hospital_name':    hospital.hospital_name,
        'hospital_email':   hospital.email,
        'hospital_contact': hospital.contact_number,
        'hospital_license': hospital.license_number,
        'hospital_address': hospital.address,
        'account_status':   hospital.account_status,
        'total_patients':   total_patients,
        'total_records':    0,      # will be real count after records model is built
        'total_reports':    0,      # will be real count after reports model is built
        'total_doctors':    total_doctors,
        'total_nurses':     total_nurses,
        'recent_logs':      [],     # will be populated after audit log model is built
    })


# render hospital profile page
@hospital_admin_required
def hospital_profile(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    return render(request, 'hospitals/h_profile.html', {'hospital': hospital})


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
    return render(request, 'hospitals/doctors_list.html', {
        'hospital_name': hospital.hospital_name,
        'doctors':       doctors,
    })


# register a new doctor and send credentials via email
@hospital_admin_required
def add_doctor(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/add_doctor.html', {
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
        return render(request, 'hospitals/add_doctor.html', {
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

    return render(request, 'hospitals/doctor_detail.html', {
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
    return render(request, 'hospitals/nurses_list.html', {
        'hospital_name': hospital.hospital_name,
        'nurses':        nurses,
    })


# register a new nurse and send credentials via email
@hospital_admin_required
def add_nurse(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/add_nurse.html', {
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
        return render(request, 'hospitals/add_nurse.html', {
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

    return render(request, 'hospitals/nurse_detail.html', {
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


# ─── Hospital Admin — Patients ─────────────────────────────────────────────────

# list all patients registered by this hospital
@hospital_admin_required
def patients_list(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    patients = service_get_patients(request.session['hospital_id'])
    return render(request, 'hospitals/patients_list.html', {
        'hospital_name': hospital.hospital_name,
        'patients':      patients,
    })


# register a new patient with encrypted gov ID and duplicate detection
@hospital_admin_required
def add_patient(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    if request.method != 'POST':
        return render(request, 'hospitals/add_patient.html', {
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
        return render(request, 'hospitals/add_patient.html', {
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

    return render(request, 'hospitals/patient_detail.html', {
        'hospital_name': request.session.get('hospital_name'),
        'patient':       patient,
        'gov_id_masked': gov_id_masked,
    })
