import re
import random
import hashlib
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from django.utils import timezone
from .models import Hospital, HospitalUser, Patient
from .encryption import encrypt, decrypt
from .decorators import hospital_admin_required, doctor_required, nurse_required
from .utils import generate_temp_password, check_and_activate
from .emails import (
    send_verification_otp,
    send_resend_otp,
    send_doctor_credentials,
    send_nurse_credentials,
)


# ─── Auth ─────────────────────────────────────────────────────────────────────

# render register page / handle hospital registration form
def hospital_register(request):
    if request.method != 'POST':
        return render(request, 'hospitals/register.html')

    hospital_name    = request.POST.get('hospital_name', '').strip()
    email            = request.POST.get('email', '').strip().lower()
    contact_number   = request.POST.get('contact_number', '').strip()
    password         = request.POST.get('password', '')
    confirm_password = request.POST.get('confirm_password', '')

    # clean up stale unverified records before creating a new one
    Hospital.objects.filter(email=email, email_verified=False).delete()
    Hospital.objects.filter(contact_number=contact_number, email_verified=False).delete()

    errors = {}

    if not hospital_name:
        errors['hospital_name'] = 'Hospital name is required'

    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$'
    if not email:
        errors['email'] = 'Email is required'
    elif not re.match(email_regex, email):
        errors['email'] = 'Enter a valid email address'
    elif Hospital.objects.filter(email=email).exists():
        errors['email'] = 'This email is already registered'

    india_mobile_regex = r'^[6-9]\d{9}$'
    if not contact_number:
        errors['contact_number'] = 'Contact number is required'
    elif not re.match(india_mobile_regex, contact_number):
        errors['contact_number'] = 'Enter a valid 10-digit Indian mobile number'
    elif Hospital.objects.filter(contact_number=contact_number).exists():
        errors['contact_number'] = 'This contact number is already registered'

    if not password:
        errors['password'] = 'Password is required'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters'

    if not confirm_password:
        errors['confirm_password'] = 'Please confirm your password'
    elif password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match'

    if errors:
        return JsonResponse({'success': False, 'errors': errors})

    # generate OTP and save hospital record
    otp    = str(random.randint(100000, 999999))
    expiry = timezone.now() + timezone.timedelta(minutes=10)

    hospital = Hospital.objects.create(
        hospital_name           = hospital_name,
        email                   = email,
        contact_number          = contact_number,
        password_hash           = make_password(password),
        email_verify_otp        = otp,
        email_verify_otp_expiry = expiry,
    )

    # send OTP to hospital email
    send_verification_otp(hospital_name, email, otp)

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

    otp_entered = request.POST.get('otp', '').strip()

    # block if OTP has expired
    if timezone.now() > hospital.email_verify_otp_expiry:
        return render(request, 'hospitals/verify_otp.html', {
            'email': hospital.email,
            'error': 'OTP has expired. Please request a new one.',
        })

    # block if OTP is wrong
    if otp_entered != hospital.email_verify_otp:
        return render(request, 'hospitals/verify_otp.html', {
            'email': hospital.email,
            'error': 'Incorrect OTP. Please try again.',
        })

    # mark email as verified and clear OTP fields
    hospital.email_verified          = True
    hospital.email_verify_otp        = None
    hospital.email_verify_otp_expiry = None
    hospital.save()

    del request.session['verify_hospital_id']
    return render(request, 'hospitals/verify_otp.html', {'success': True})


# generate a new OTP and resend it to the hospital email
def resend_otp(request):
    if 'verify_hospital_id' not in request.session:
        return redirect('/')

    hospital = Hospital.objects.get(id=request.session['verify_hospital_id'])

    # generate fresh OTP with new expiry
    otp    = str(random.randint(100000, 999999))
    expiry = timezone.now() + timezone.timedelta(minutes=10)

    hospital.email_verify_otp        = otp
    hospital.email_verify_otp_expiry = expiry
    hospital.save()

    send_resend_otp(hospital.hospital_name, hospital.email, otp)
    return redirect('/verify-otp/')


# handle login for hospital admin, doctor, and nurse from the same page
def hospital_login(request):
    if request.method != 'POST':
        return render(request, 'hospitals/register.html')

    email    = request.POST.get('email', '').strip().lower()
    password = request.POST.get('password', '')

    errors = {}
    if not email:    errors['email']    = 'Email is required'
    if not password: errors['password'] = 'Password is required'
    if errors:
        return JsonResponse({'success': False, 'errors': errors})

    # check Hospital table first — admin login
    try:
        hospital = Hospital.objects.get(email=email)

        # block if email not yet verified
        if not hospital.email_verified:
            return JsonResponse({'success': False, 'errors': {
                'email': 'Please verify your email before logging in. Check your inbox.'
            }})

        # block if password is wrong
        if not check_password(password, hospital.password_hash):
            return JsonResponse({'success': False, 'errors': {
                'password': 'Incorrect password'
            }})

        # block suspended accounts
        if hospital.account_status == 'suspended':
            return JsonResponse({'success': False, 'errors': {
                'email': 'This account has been suspended'
            }})

        # set admin session and redirect to admin dashboard
        request.session['hospital_id']    = str(hospital.id)
        request.session['hospital_name']  = hospital.hospital_name
        request.session['account_status'] = hospital.account_status
        return JsonResponse({'success': True, 'redirect': '/dashboard/'})

    except Hospital.DoesNotExist:
        pass

    # check HospitalUser table — doctor or nurse login
    try:
        staff = HospitalUser.objects.get(email=email)

        # block if password is wrong
        if not check_password(password, staff.password_hash):
            return JsonResponse({'success': False, 'errors': {
                'password': 'Incorrect password'
            }})

        # block deactivated staff accounts
        if staff.status == 'inactive':
            return JsonResponse({'success': False, 'errors': {
                'email': 'Your account has been deactivated. Contact your hospital admin.'
            }})

        # set staff session — hospital_id is needed for data scoping
        request.session['staff_id']       = str(staff.id)
        request.session['staff_name']     = staff.full_name
        request.session['staff_role']     = staff.role
        request.session['staff_hospital'] = staff.hospital.hospital_name
        request.session['hospital_id']    = str(staff.hospital.id)

        # route to role-specific dashboard
        if staff.role == 'doctor':
            return JsonResponse({'success': True, 'redirect': '/staff/doctor/dashboard/'})
        else:
            return JsonResponse({'success': True, 'redirect': '/staff/nurse/dashboard/'})

    except HospitalUser.DoesNotExist:
        pass

    # email not found in either table
    return JsonResponse({'success': False, 'errors': {
        'email': 'No account found with this email'
    }})


# flush session and redirect to login page
def hospital_logout(request):
    request.session.flush()
    return redirect('/')


# ─── Hospital Admin — Dashboard & Profile ─────────────────────────────────────

# render admin dashboard with live counts
@hospital_admin_required
def hospital_dashboard(request):
    hospital       = Hospital.objects.get(id=request.session['hospital_id'])
    total_doctors  = HospitalUser.objects.filter(hospital=hospital, role='doctor').count()
    total_nurses   = HospitalUser.objects.filter(hospital=hospital, role='nurse').count()
    total_patients = Patient.objects.filter(registered_by=hospital).count()

    return render(request, 'hospitals/h_dashboard.html', {
        'hospital_name':    hospital.hospital_name,
        'hospital_email':   hospital.email,
        'hospital_contact': hospital.contact_number,
        'hospital_license': hospital.license_number,
        'hospital_address': hospital.address,
        'account_status':   hospital.account_status,
        'total_patients':   total_patients,
        'total_records':    0,        # will be real count after records model is built
        'total_reports':    0,        # will be real count after reports model is built
        'total_doctors':    total_doctors,
        'total_nurses':     total_nurses,
        'recent_logs':      [],       # will be populated after audit log model is built
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

    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    # reject if name is already locked
    if hospital.name_locked:
        messages.error(request, 'Hospital name is locked and cannot be changed.')
        return redirect('hospital_profile')

    name = request.POST.get('hospital_name', '').strip()
    if not name:
        messages.error(request, 'Hospital name cannot be empty.')
        return redirect('hospital_profile')

    # save, lock, and update session
    hospital.hospital_name = name
    hospital.name_locked   = True
    hospital.save()
    request.session['hospital_name'] = name
    messages.success(request, 'Hospital name saved and locked successfully.')
    return redirect('hospital_profile')


# save and lock license details — can only be set once
@hospital_admin_required
def hospital_update_license(request):
    if request.method != 'POST':
        return redirect('hospital_profile')

    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    # reject if license is already locked
    if hospital.license_locked:
        messages.error(request, 'License details are locked and cannot be changed.')
        return redirect('hospital_profile')

    license_number   = request.POST.get('license_number', '').strip()
    license_document = request.FILES.get('license_document')

    if not license_number:
        messages.error(request, 'License number is required.')
        return redirect('hospital_profile')

    # save document if uploaded, then lock license
    hospital.license_number = license_number
    if license_document:
        hospital.license_document = license_document
    hospital.license_locked = True
    hospital.save()

    # check if hospital can be auto-activated after this update
    check_and_activate(request, hospital)
    messages.success(request, 'License details saved and locked successfully.')
    return redirect('hospital_profile')


# update hospital address — editable anytime
@hospital_admin_required
def hospital_update_address(request):
    if request.method != 'POST':
        return redirect('hospital_profile')

    hospital         = Hospital.objects.get(id=request.session['hospital_id'])
    hospital.address = request.POST.get('address', '').strip()
    hospital.city    = request.POST.get('city', '').strip()
    hospital.state   = request.POST.get('state', '').strip()
    hospital.country = request.POST.get('country', '').strip()
    hospital.save()

    # check if hospital can be auto-activated after address is filled
    check_and_activate(request, hospital)
    messages.success(request, 'Address updated successfully.')
    return redirect('hospital_profile')


# change hospital admin password after verifying current password
@hospital_admin_required
def hospital_update_password(request):
    if request.method != 'POST':
        return redirect('hospital_profile')

    hospital         = Hospital.objects.get(id=request.session['hospital_id'])
    current_password = request.POST.get('current_password', '')
    new_password     = request.POST.get('new_password', '')
    confirm_password = request.POST.get('confirm_new_password', '')

    # verify current password before allowing change
    if not check_password(current_password, hospital.password_hash):
        messages.error(request, 'Current password is incorrect.')
        return redirect('hospital_profile')

    if len(new_password) < 8:
        messages.error(request, 'New password must be at least 8 characters.')
        return redirect('hospital_profile')

    if new_password != confirm_password:
        messages.error(request, 'New passwords do not match.')
        return redirect('hospital_profile')

    hospital.password_hash = make_password(new_password)
    hospital.save()
    messages.success(request, 'Password updated successfully.')
    return redirect('hospital_profile')


# ─── Hospital Admin — Doctors ──────────────────────────────────────────────────

# list all doctors belonging to this hospital
@hospital_admin_required
def doctors_list(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    doctors  = HospitalUser.objects.filter(hospital=hospital, role='doctor').order_by('-created_at')
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

    full_name      = request.POST.get('full_name', '').strip()
    email          = request.POST.get('email', '').strip().lower()
    phone          = request.POST.get('phone', '').strip()
    employee_id    = request.POST.get('employee_id', '').strip()
    specialization = request.POST.get('specialization', '').strip()

    errors = {}
    if not full_name:
        errors['full_name'] = 'Full name is required'
    if not email:
        errors['email'] = 'Email is required'
    elif HospitalUser.objects.filter(email=email).exists():
        errors['email'] = 'A staff member with this email already exists'
    if not phone:
        errors['phone'] = 'Phone number is required'
    elif not re.match(r'^[6-9]\d{9}$', phone):
        errors['phone'] = 'Enter a valid 10-digit Indian mobile number'
    elif HospitalUser.objects.filter(phone=phone).exists():
        errors['phone'] = 'This phone number is already registered'
    if not employee_id:
        errors['employee_id'] = 'Employee ID is required'
    elif HospitalUser.objects.filter(hospital=hospital, employee_id=employee_id).exists():
        errors['employee_id'] = 'This Employee ID already exists in your hospital'
    if not specialization:
        errors['specialization'] = 'Specialization is required'

    if errors:
        return render(request, 'hospitals/add_doctor.html', {
            'hospital_name': hospital.hospital_name,
            'errors':        errors,
            'form_data':     request.POST,
        })

    # generate temp password, create account, send credentials
    temp_password = generate_temp_password()
    HospitalUser.objects.create(
        hospital       = hospital,
        full_name      = full_name,
        email          = email,
        phone          = phone,
        employee_id    = employee_id,
        role           = 'doctor',
        specialization = specialization,
        password_hash  = make_password(temp_password),
        status         = 'active',
    )

    send_doctor_credentials(full_name, email, hospital.hospital_name, temp_password)
    messages.success(request, f'Dr. {full_name} has been registered and credentials sent to {email}.')
    return redirect('doctors_list')


# view individual doctor details
@hospital_admin_required
def doctor_detail(request, pk):
    doctor = HospitalUser.objects.get(id=pk, hospital_id=request.session['hospital_id'], role='doctor')
    return render(request, 'hospitals/doctor_detail.html', {
        'hospital_name': request.session.get('hospital_name'),
        'doctor':        doctor,
    })


# activate / deactivate doctor toggle
@hospital_admin_required
def toggle_doctor(request, pk):
    if request.method != 'POST':
        return redirect('doctors_list')
    doctor        = HospitalUser.objects.get(id=pk, hospital_id=request.session['hospital_id'], role='doctor')
    doctor.status = 'inactive' if doctor.status == 'active' else 'active'
    doctor.save()
    messages.success(request, f'{doctor.full_name} has been {"deactivated" if doctor.status == "inactive" else "activated"}.')
    return redirect('doctors_list')


# ─── Hospital Admin — Nurses ───────────────────────────────────────────────────

# list all nurses belonging to this hospital
@hospital_admin_required
def nurses_list(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    nurses   = HospitalUser.objects.filter(hospital=hospital, role='nurse').order_by('-created_at')
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

    full_name   = request.POST.get('full_name', '').strip()
    email       = request.POST.get('email', '').strip().lower()
    phone       = request.POST.get('phone', '').strip()
    employee_id = request.POST.get('employee_id', '').strip()

    errors = {}
    if not full_name:
        errors['full_name'] = 'Full name is required'
    if not email:
        errors['email'] = 'Email is required'
    elif HospitalUser.objects.filter(email=email).exists():
        errors['email'] = 'A staff member with this email already exists'
    if not phone:
        errors['phone'] = 'Phone number is required'
    elif not re.match(r'^[6-9]\d{9}$', phone):
        errors['phone'] = 'Enter a valid 10-digit Indian mobile number'
    elif HospitalUser.objects.filter(phone=phone).exists():
        errors['phone'] = 'This phone number is already registered'
    if not employee_id:
        errors['employee_id'] = 'Employee ID is required'
    elif HospitalUser.objects.filter(hospital=hospital, employee_id=employee_id).exists():
        errors['employee_id'] = 'This Employee ID already exists in your hospital'

    if errors:
        return render(request, 'hospitals/add_nurse.html', {
            'hospital_name': hospital.hospital_name,
            'errors':        errors,
            'form_data':     request.POST,
        })

    # generate temp password, create account, send credentials
    temp_password = generate_temp_password()
    HospitalUser.objects.create(
        hospital      = hospital,
        full_name     = full_name,
        email         = email,
        phone         = phone,
        employee_id   = employee_id,
        role          = 'nurse',
        password_hash = make_password(temp_password),
        status        = 'active',
    )

    send_nurse_credentials(full_name, email, hospital.hospital_name, temp_password)
    messages.success(request, f'{full_name} has been registered and credentials sent to {email}.')
    return redirect('nurses_list')


# view individual nurse details
@hospital_admin_required
def nurse_detail(request, pk):
    nurse = HospitalUser.objects.get(id=pk, hospital_id=request.session['hospital_id'], role='nurse')
    return render(request, 'hospitals/nurse_detail.html', {
        'hospital_name': request.session.get('hospital_name'),
        'nurse':         nurse,
    })


# activate / deactivate nurse toggle
@hospital_admin_required
def toggle_nurse(request, pk):
    if request.method != 'POST':
        return redirect('nurses_list')
    nurse        = HospitalUser.objects.get(id=pk, hospital_id=request.session['hospital_id'], role='nurse')
    nurse.status = 'inactive' if nurse.status == 'active' else 'active'
    nurse.save()
    messages.success(request, f'{nurse.full_name} has been {"deactivated" if nurse.status == "inactive" else "activated"}.')
    return redirect('nurses_list')


# ─── Hospital Admin — Patients ─────────────────────────────────────────────────

# list all patients registered by this hospital
@hospital_admin_required
def patients_list(request):
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    patients = Patient.objects.filter(registered_by=hospital).order_by('-created_at')
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

    gov_id_type   = request.POST.get('gov_id_type', '').strip()
    gov_id_number = request.POST.get('gov_id_number', '').strip().replace(' ', '')
    full_name     = request.POST.get('full_name', '').strip()
    gender        = request.POST.get('gender', '').strip()
    phone         = request.POST.get('phone', '').strip()
    email         = request.POST.get('email', '').strip().lower()
    address       = request.POST.get('address', '').strip()

    errors = {}
    if not gov_id_number: errors['gov_id']    = 'Government ID is required'
    if not full_name:     errors['full_name'] = 'Full name is required'
    if phone and not re.match(r'^[6-9]\d{9}$', phone):
        errors['phone'] = 'Enter a valid 10-digit Indian mobile number'

    # hash gov_id_type + gov_id_number together to detect cross-type duplicates
    gov_id_hash = None
    if gov_id_number:
        gov_id_hash = hashlib.sha256(f"{gov_id_type}{gov_id_number}".encode()).hexdigest()
        if Patient.objects.filter(gov_id_hash=gov_id_hash).exists():
            errors['gov_id'] = 'This patient is already registered in the system'

    if errors:
        return render(request, 'hospitals/add_patient.html', {
            'hospital_name': hospital.hospital_name,
            'errors':        errors,
            'form_data':     request.POST,
        })

    # encrypt gov ID before storing — hash is kept separately for lookups
    Patient.objects.create(
        gov_id_type   = gov_id_type,
        gov_id_number = encrypt(gov_id_number),
        gov_id_hash   = gov_id_hash,
        full_name     = full_name,
        gender        = gender  or None,
        phone         = phone   or None,
        email         = email   or None,
        address       = address or None,
        registered_by = hospital,
    )

    messages.success(request, f'{full_name} has been registered successfully.')
    return redirect('patients_list')


# view individual patient details with masked gov ID
@hospital_admin_required
def patient_detail(request, pk):
    patient = Patient.objects.get(id=pk)

    # decrypt gov ID and mask all but last 4 digits for display
    try:
        raw_id        = decrypt(patient.gov_id_number)
        gov_id_masked = '•' * (len(raw_id) - 4) + raw_id[-4:]
    except Exception:
        gov_id_masked = '••••••••'

    return render(request, 'hospitals/patient_detail.html', {
        'hospital_name': request.session.get('hospital_name'),
        'patient':       patient,
        'gov_id_masked': gov_id_masked,
    })
