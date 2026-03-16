import re
import random
import hashlib
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone

from .models import Hospital, HospitalUser, Patient
from .utils import generate_temp_password, check_and_activate_without_session
from .emails import (
    send_verification_otp,
    send_resend_otp,
    send_doctor_credentials,
    send_nurse_credentials,
)
from .encryption import encrypt, decrypt


# ─── Auth Services ────────────────────────────────────────────────────────────

# validate and create a new hospital record, send OTP, return hospital object
def service_register_hospital(hospital_name, email, contact_number, password, confirm_password):
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
        return None, errors

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

    return hospital, None


# verify OTP for a hospital — returns (success, error)
def service_verify_otp(hospital_id, otp_entered):
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return False, 'Invalid hospital ID'

    # block if OTP has expired
    if timezone.now() > hospital.email_verify_otp_expiry:
        return False, 'OTP has expired. Please request a new one.'

    # block if OTP is wrong
    if otp_entered != hospital.email_verify_otp:
        return False, 'Incorrect OTP. Please try again.'

    # mark email as verified and clear OTP fields
    hospital.email_verified          = True
    hospital.email_verify_otp        = None
    hospital.email_verify_otp_expiry = None
    hospital.save()

    return True, None


# generate a fresh OTP and resend to hospital email — returns (success, error)
def service_resend_otp(hospital_id):
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return False, 'Invalid hospital ID'

    # generate fresh OTP with new expiry
    otp    = str(random.randint(100000, 999999))
    expiry = timezone.now() + timezone.timedelta(minutes=10)

    hospital.email_verify_otp        = otp
    hospital.email_verify_otp_expiry = expiry
    hospital.save()

    send_resend_otp(hospital.hospital_name, hospital.email, otp)
    return True, None


# unified login — checks Hospital table then HospitalUser table
# returns (user_type, object, errors)
# user_type is 'hospital_admin', 'doctor', 'nurse', or None on failure
def service_login(email, password):
    errors = {}
    if not email:    errors['email']    = 'Email is required'
    if not password: errors['password'] = 'Password is required'
    if errors:
        return None, None, errors

    # check Hospital table first — admin login
    try:
        hospital = Hospital.objects.get(email=email)

        # block if email not yet verified
        if not hospital.email_verified:
            return None, None, {'email': 'Please verify your email before logging in. Check your inbox.'}

        # block if password is wrong
        if not check_password(password, hospital.password_hash):
            return None, None, {'password': 'Incorrect password'}

        # block suspended accounts
        if hospital.account_status == 'suspended':
            return None, None, {'email': 'This account has been suspended'}

        return 'hospital_admin', hospital, None

    except Hospital.DoesNotExist:
        pass

    # check HospitalUser table — doctor or nurse login
    try:
        staff = HospitalUser.objects.get(email=email)

        # block if password is wrong
        if not check_password(password, staff.password_hash):
            return None, None, {'password': 'Incorrect password'}

        # block deactivated staff accounts
        if staff.status == 'inactive':
            return None, None, {'email': 'Your account has been deactivated. Contact your hospital admin.'}

        return staff.role, staff, None

    except HospitalUser.DoesNotExist:
        pass

    # email not found in either table
    return None, None, {'email': 'No account found with this email'}


# ─── Hospital Profile Services ────────────────────────────────────────────────

# get dashboard counts for a hospital
def service_get_dashboard_data(hospital_id):
    hospital       = Hospital.objects.get(id=hospital_id)
    total_doctors  = HospitalUser.objects.filter(hospital=hospital, role='doctor').count()
    total_nurses   = HospitalUser.objects.filter(hospital=hospital, role='nurse').count()
    total_patients = Patient.objects.filter(registered_by=hospital).count()
    return hospital, total_doctors, total_nurses, total_patients


# save and lock hospital name — returns (success, error)
def service_update_name(hospital_id, name):
    hospital = Hospital.objects.get(id=hospital_id)

    # reject if name is already locked
    if hospital.name_locked:
        return None, 'Hospital name is locked and cannot be changed.'

    if not name:
        return None, 'Hospital name cannot be empty.'

    # save and lock
    hospital.hospital_name = name
    hospital.name_locked   = True
    hospital.save()
    return hospital, None


# save and lock license details — returns (success, error)
def service_update_license(hospital_id, license_number, license_document=None):
    hospital = Hospital.objects.get(id=hospital_id)

    # reject if license is already locked
    if hospital.license_locked:
        return None, 'License details are locked and cannot be changed.'

    if not license_number:
        return None, 'License number is required.'

    # save document if uploaded, then lock license
    hospital.license_number = license_number
    if license_document:
        hospital.license_document = license_document
    hospital.license_locked = True
    hospital.save()

    # check if hospital can be auto-activated
    check_and_activate_without_session(hospital)
    return hospital, None


# update address fields — editable anytime
def service_update_address(hospital_id, address, city, state, country):
    hospital         = Hospital.objects.get(id=hospital_id)
    hospital.address = address
    hospital.city    = city
    hospital.state   = state
    hospital.country = country
    hospital.save()

    # check if hospital can be auto-activated after address is filled
    check_and_activate_without_session(hospital)
    return hospital, None


# change password after verifying current password — returns (success, error)
def service_update_password(hospital_id, current_password, new_password, confirm_password):
    hospital = Hospital.objects.get(id=hospital_id)

    # verify current password before allowing change
    if not check_password(current_password, hospital.password_hash):
        return False, 'Current password is incorrect.'

    if len(new_password) < 8:
        return False, 'New password must be at least 8 characters.'

    if new_password != confirm_password:
        return False, 'New passwords do not match.'

    hospital.password_hash = make_password(new_password)
    hospital.save()
    return True, None


# ─── Doctor Services ──────────────────────────────────────────────────────────

# get all doctors for a hospital
def service_get_doctors(hospital_id):
    hospital = Hospital.objects.get(id=hospital_id)
    return HospitalUser.objects.filter(hospital=hospital, role='doctor').order_by('-created_at')


# validate and create a new doctor, send credentials — returns (doctor, errors)
def service_add_doctor(hospital_id, full_name, email, phone, employee_id, specialization):
    hospital = Hospital.objects.get(id=hospital_id)

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
        return None, errors

    # generate temp password, create account, send credentials
    temp_password = generate_temp_password()
    doctor = HospitalUser.objects.create(
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
    return doctor, None


# get a single doctor by pk scoped to hospital — returns (doctor, error)
def service_get_doctor(hospital_id, pk):
    try:
        return HospitalUser.objects.get(id=pk, hospital_id=hospital_id, role='doctor'), None
    except HospitalUser.DoesNotExist:
        return None, 'Doctor not found'


# toggle doctor active/inactive status — returns (doctor, error)
def service_toggle_doctor(hospital_id, pk):
    doctor, error = service_get_doctor(hospital_id, pk)
    if error:
        return None, error
    doctor.status = 'inactive' if doctor.status == 'active' else 'active'
    doctor.save()
    return doctor, None


# ─── Nurse Services ───────────────────────────────────────────────────────────

# get all nurses for a hospital
def service_get_nurses(hospital_id):
    hospital = Hospital.objects.get(id=hospital_id)
    return HospitalUser.objects.filter(hospital=hospital, role='nurse').order_by('-created_at')


# validate and create a new nurse, send credentials — returns (nurse, errors)
def service_add_nurse(hospital_id, full_name, email, phone, employee_id):
    hospital = Hospital.objects.get(id=hospital_id)

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
        return None, errors

    # generate temp password, create account, send credentials
    temp_password = generate_temp_password()
    nurse = HospitalUser.objects.create(
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
    return nurse, None


# get a single nurse by pk scoped to hospital — returns (nurse, error)
def service_get_nurse(hospital_id, pk):
    try:
        return HospitalUser.objects.get(id=pk, hospital_id=hospital_id, role='nurse'), None
    except HospitalUser.DoesNotExist:
        return None, 'Nurse not found'


# toggle nurse active/inactive status — returns (nurse, error)
def service_toggle_nurse(hospital_id, pk):
    nurse, error = service_get_nurse(hospital_id, pk)
    if error:
        return None, error
    nurse.status = 'inactive' if nurse.status == 'active' else 'active'
    nurse.save()
    return nurse, None


# ─── Patient Services ─────────────────────────────────────────────────────────

# get all patients registered by this hospital
def service_get_patients(hospital_id):
    hospital = Hospital.objects.get(id=hospital_id)
    return Patient.objects.filter(registered_by=hospital).order_by('-created_at')


# validate and register a new patient with encrypted gov ID — returns (patient, errors)
def service_add_patient(hospital_id, gov_id_type, gov_id_number, full_name,
                        gender=None, phone=None, email=None, address=None):
    hospital      = Hospital.objects.get(id=hospital_id)
    gov_id_number = gov_id_number.replace(' ', '')

    errors = {}
    if not gov_id_number:
        errors['gov_id'] = 'Government ID is required'
    if not full_name:
        errors['full_name'] = 'Full name is required'
    if phone and not re.match(r'^[6-9]\d{9}$', phone):
        errors['phone'] = 'Enter a valid 10-digit Indian mobile number'

    # hash gov_id_type + gov_id_number together to detect cross-type duplicates
    gov_id_hash = None
    if gov_id_number:
        gov_id_hash = hashlib.sha256(f"{gov_id_type}{gov_id_number}".encode()).hexdigest()
        if Patient.objects.filter(gov_id_hash=gov_id_hash).exists():
            errors['gov_id'] = 'This patient is already registered in the system'

    if errors:
        return None, errors

    # encrypt gov ID before storing — hash kept separately for lookups
    patient = Patient.objects.create(
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

    return patient, None


# get a single patient and return with masked gov ID — returns (patient, gov_id_masked, error)
def service_get_patient(pk):
    try:
        patient = Patient.objects.get(id=pk)
    except Patient.DoesNotExist:
        return None, None, 'Patient not found'

    # decrypt gov ID and mask all but last 4 digits for display
    try:
        raw_id        = decrypt(patient.gov_id_number)
        gov_id_masked = '•' * (len(raw_id) - 4) + raw_id[-4:]
    except Exception:
        gov_id_masked = '••••••••'

    return patient, gov_id_masked, None
