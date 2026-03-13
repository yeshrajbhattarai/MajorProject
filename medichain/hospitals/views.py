import re
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password, check_password
from .models import Hospital, HospitalUser
from django.contrib import messages
from django.core.mail import send_mail
import string
import secrets


#render dashboard
def hospital_dashboard(request):
    if 'hospital_id' not in request.session:
        return redirect('/')

    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    return render(request, 'hospitals/h_dashboard.html', {
        'hospital_name':    hospital.hospital_name,
        'hospital_email':   hospital.email,
        'hospital_contact': hospital.contact_number,
        'hospital_license': hospital.license_number,
        'hospital_address': hospital.address,
        'account_status':   hospital.account_status,
        # All zero for now — will be real counts after models are built
        'total_patients':   0,
        'total_records':    0,
        'total_reports':    0,
        'total_doctors':    0,
        'total_nurses':     0,
        'recent_logs':      [],
    })


#render register
def hospital_register(request):
    if request.method != 'POST':
        return render(request, 'hospitals/register.html')

    hospital_name    = request.POST.get('hospital_name', '').strip()
    email            = request.POST.get('email', '').strip().lower()
    contact_number   = request.POST.get('contact_number', '').strip()
    password         = request.POST.get('password', '')
    confirm_password = request.POST.get('confirm_password', '')

    # ── Clean up stale unverified records first ──
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

    # ── Generate 6-digit OTP ──
    import random
    from django.utils import timezone
    otp    = str(random.randint(100000, 999999))
    expiry = timezone.now() + timezone.timedelta(minutes=10)

    # ── Save hospital ──
    hospital = Hospital.objects.create(
        hospital_name           = hospital_name,
        email                   = email,
        contact_number          = contact_number,
        password_hash           = make_password(password),
        email_verify_otp        = otp,
        email_verify_otp_expiry = expiry,
    )

    # ── Send OTP email ──
    send_mail(
        subject       = 'MediChain — Email Verification OTP',
        message       = f"""Hello {hospital_name},

Your MediChain email verification OTP is:

{otp}

This OTP is valid for 10 minutes.
If you did not register, ignore this email.

— MediChain Team""",
        from_email    = None,
        recipient_list = [email],
        fail_silently  = False,
    )

    # ── Store hospital id in session for OTP page ──
    request.session['verify_hospital_id'] = str(hospital.id)

    return JsonResponse({
        'success'  : True,
        'redirect' : '/verify-otp/',
    })


def verify_otp(request):
    # ── Must have a pending verification session ──
    if 'verify_hospital_id' not in request.session:
        return redirect('/')

    hospital = Hospital.objects.get(id=request.session['verify_hospital_id'])

    if request.method == 'GET':
        return render(request, 'hospitals/verify_otp.html', {
            'email': hospital.email,
        })

    # ── POST — check OTP ──
    from django.utils import timezone
    otp_entered = request.POST.get('otp', '').strip()

    # Expired
    if timezone.now() > hospital.email_verify_otp_expiry:
        return render(request, 'hospitals/verify_otp.html', {
            'email': hospital.email,
            'error': 'OTP has expired. Please request a new one.',
        })

    # Wrong OTP
    if otp_entered != hospital.email_verify_otp:
        return render(request, 'hospitals/verify_otp.html', {
            'email': hospital.email,
            'error': 'Incorrect OTP. Please try again.',
        })

    # ── Correct — verify and clean up ──
    hospital.email_verified        = True
    hospital.email_verify_otp        = None
    hospital.email_verify_otp_expiry = None
    hospital.save()

    # ── Clear verification session, keep login session ──
    del request.session['verify_hospital_id']

    return render(request, 'hospitals/verify_otp.html', {
        'success': True,
    })


def resend_otp(request):
    if 'verify_hospital_id' not in request.session:
        return redirect('/')

    import random
    from django.utils import timezone

    hospital = Hospital.objects.get(id=request.session['verify_hospital_id'])

    otp    = str(random.randint(100000, 999999))
    expiry = timezone.now() + timezone.timedelta(minutes=10)

    hospital.email_verify_otp        = otp
    hospital.email_verify_otp_expiry = expiry
    hospital.save()

    send_mail(
        subject       = 'MediChain — New Verification OTP',
        message       = f"""Hello {hospital.hospital_name},

Your new OTP is:

{otp}

Valid for 10 minutes.

— MediChain Team""",
        from_email    = None,
        recipient_list = [hospital.email],
        fail_silently  = False,
    )

    return redirect('/verify-otp/')

#render login 
def hospital_login(request):
    if request.method != 'POST':
        return render(request, 'hospitals/register.html')

    # ── Read POST data ──
    email    = request.POST.get('email', '').strip().lower()
    password = request.POST.get('password', '')

    errors = {}

    # ── Basic empty checks ──
    if not email:
        errors['email'] = 'Email is required'
    if not password:
        errors['password'] = 'Password is required'

    if errors:
        return JsonResponse({'success': False, 'errors': errors})

    # ── Look up hospital by email ──
    try:
        hospital = Hospital.objects.get(email=email)
    except Hospital.DoesNotExist:
        return JsonResponse({'success': False, 'errors': {
            'email': 'No account found with this email'
        }})
    
    # ── Block unverified accounts ──
    if not hospital.email_verified:
        return JsonResponse({'success': False, 'errors': {
        'email': 'Please verify your email before logging in. Check your inbox.'
    }})

    # ── Verify password against stored hash ──
    if not check_password(password, hospital.password_hash):
        return JsonResponse({'success': False, 'errors': {
            'password': 'Incorrect password'
        }})

    # ── Block suspended accounts ──
    if hospital.account_status == 'suspended':
        return JsonResponse({'success': False, 'errors': {
            'email': 'This account has been suspended'
        }})

    # ── Save hospital info to session ──
    request.session['hospital_id']    = str(hospital.id)
    request.session['hospital_name']  = hospital.hospital_name
    request.session['account_status'] = hospital.account_status


    return JsonResponse({'success': True, 'redirect': '/dashboard/'})




def hospital_profile(request):
    # ── Block if not logged in ──
    if 'hospital_id' not in request.session:
        return redirect('/')

    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    return render(request, 'hospitals/h_profile.html', {'hospital': hospital})


def check_and_activate(request, hospital):
    if (
        hospital.license_locked and
        hospital.address and
        hospital.city and
        hospital.state and
        hospital.country and
        hospital.account_status == 'pending'
    ):
        hospital.account_status = 'active'
        hospital.save()
        request.session['account_status'] = 'active'


def hospital_update_name(request):
    # ── Block if not logged in ──
    if 'hospital_id' not in request.session:
        return redirect('/')

    if request.method != 'POST':
        return redirect('hospital_profile')

    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    # ── Reject if already locked ──
    if hospital.name_locked:
        messages.error(request, 'Hospital name is locked and cannot be changed.')
        return redirect('hospital_profile')

    name = request.POST.get('hospital_name', '').strip()

    if not name:
        messages.error(request, 'Hospital name cannot be empty.')
        return redirect('hospital_profile')

    # ── Save and lock ──
    hospital.hospital_name = name
    hospital.name_locked   = True
    hospital.save()

    # ── Update session name too ──
    request.session['hospital_name'] = name

    messages.success(request, 'Hospital name saved and locked successfully.')
    return redirect('hospital_profile')


def hospital_update_license(request):
    # ── Block if not logged in ──
    if 'hospital_id' not in request.session:
        return redirect('/')

    if request.method != 'POST':
        return redirect('hospital_profile')

    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    # ── Reject if already locked ──
    if hospital.license_locked:
        messages.error(request, 'License details are locked and cannot be changed.')
        return redirect('hospital_profile')

    license_number   = request.POST.get('license_number', '').strip()
    license_document = request.FILES.get('license_document')

    if not license_number:
        messages.error(request, 'License number is required.')
        return redirect('hospital_profile')

    # ── Save and lock ──
    hospital.license_number = license_number
    if license_document:
        hospital.license_document = license_document
    hospital.license_locked = True
    hospital.save()

    check_and_activate(request, hospital)
    messages.success(request, 'License details saved and locked successfully.')
    return redirect('hospital_profile')


def hospital_update_address(request):
    # ── Block if not logged in ──
    if 'hospital_id' not in request.session:
        return redirect('/')

    if request.method != 'POST':
        return redirect('hospital_profile')

    hospital = Hospital.objects.get(id=request.session['hospital_id'])

    # ── Save address fields (editable anytime) ──
    hospital.address = request.POST.get('address', '').strip()
    hospital.city    = request.POST.get('city', '').strip()
    hospital.state   = request.POST.get('state', '').strip()
    hospital.country = request.POST.get('country', '').strip()
    hospital.save()

    check_and_activate(request, hospital)
    messages.success(request, 'Address updated successfully.')
    return redirect('hospital_profile')


def hospital_update_password(request):
    # ── Block if not logged in ──
    if 'hospital_id' not in request.session:
        return redirect('/')

    if request.method != 'POST':
        return redirect('hospital_profile')

    hospital         = Hospital.objects.get(id=request.session['hospital_id'])
    current_password = request.POST.get('current_password', '')
    new_password     = request.POST.get('new_password', '')
    confirm_password = request.POST.get('confirm_new_password', '')

    # ── Verify current password ──
    if not check_password(current_password, hospital.password_hash):
        messages.error(request, 'Current password is incorrect.')
        return redirect('hospital_profile')

    # ── Validate new password ──
    if len(new_password) < 8:
        messages.error(request, 'New password must be at least 8 characters.')
        return redirect('hospital_profile')

    if new_password != confirm_password:
        messages.error(request, 'New passwords do not match.')
        return redirect('hospital_profile')

    # ── Save new hashed password ──
    hospital.password_hash = make_password(new_password)
    hospital.save()

    messages.success(request, 'Password updated successfully.')
    return redirect('hospital_profile')

# logout and flush sessions 
def hospital_logout(request):
    request.session.flush()
    return redirect('/')

# helper to generate passwords 
def generate_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def doctors_list(request):
    if 'hospital_id' not in request.session:
        return redirect('/')
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    doctors  = HospitalUser.objects.filter(hospital=hospital, role='doctor').order_by('-created_at')
    return render(request, 'hospitals/doctors_list.html', {
        'hospital_name': hospital.hospital_name,
        'doctors':       doctors,
    })


def add_doctor(request):
    if 'hospital_id' not in request.session:
        return redirect('/')
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

    send_mail(
        subject='MediChain — Your Doctor Account Credentials',
        message=(
            f"Hello Dr. {full_name},\n\n"
            f"Your MediChain doctor account has been created by {hospital.hospital_name}.\n\n"
            f"Login Email   : {email}\n"
            f"Temp Password : {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"— MediChain Team"
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )

    messages.success(request, f'Dr. {full_name} has been registered and credentials sent to {email}.')
    return redirect('doctors_list')


def toggle_doctor(request, pk):
    if 'hospital_id' not in request.session:
        return redirect('/')
    if request.method != 'POST':
        return redirect('doctors_list')
    doctor = HospitalUser.objects.get(id=pk, hospital_id=request.session['hospital_id'], role='doctor')
    doctor.status = 'inactive' if doctor.status == 'active' else 'active'
    doctor.save()
    messages.success(request, f'{doctor.full_name} has been {"deactivated" if doctor.status == "inactive" else "activated"}.')
    return redirect('doctors_list')


def nurses_list(request):
    if 'hospital_id' not in request.session:
        return redirect('/')
    hospital = Hospital.objects.get(id=request.session['hospital_id'])
    nurses   = HospitalUser.objects.filter(hospital=hospital, role='nurse').order_by('-created_at')
    return render(request, 'hospitals/nurses_list.html', {
        'hospital_name': hospital.hospital_name,
        'nurses':        nurses,
    })


def add_nurse(request):
    if 'hospital_id' not in request.session:
        return redirect('/')
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

    temp_password = generate_temp_password()
    HospitalUser.objects.create(
        hospital    = hospital,
        full_name   = full_name,
        email       = email,
        phone       = phone,
        employee_id = employee_id,
        role        = 'nurse',
        password_hash = make_password(temp_password),
        status      = 'active',
    )

    send_mail(
        subject='MediChain — Your Nurse Account Credentials',
        message=(
            f"Hello {full_name},\n\n"
            f"Your MediChain nurse account has been created by {hospital.hospital_name}.\n\n"
            f"Login Email   : {email}\n"
            f"Temp Password : {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"— MediChain Team"
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )

    messages.success(request, f'{full_name} has been registered and credentials sent to {email}.')
    return redirect('nurses_list')


def toggle_nurse(request, pk):
    if 'hospital_id' not in request.session:
        return redirect('/')
    if request.method != 'POST':
        return redirect('nurses_list')
    nurse = HospitalUser.objects.get(id=pk, hospital_id=request.session['hospital_id'], role='nurse')
    nurse.status = 'inactive' if nurse.status == 'active' else 'active'
    nurse.save()
    messages.success(request, f'{nurse.full_name} has been {"deactivated" if nurse.status == "inactive" else "activated"}.')
    return redirect('nurses_list')