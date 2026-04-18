import re
import random
import hashlib
import json
import uuid
from decimal import Decimal
from datetime import date, datetime
from types import SimpleNamespace
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Q
from django.utils import timezone

from .models import (
    Hospital,
    HospitalUser,
    Patient,
    PatientAssignment,
    Lab,
    LabAssignment,
    LabRequest,
    LabRequestRevision,
    MedicalRecordMeta,
)
from .db_router import set_hospital_db
from .hospital_db import create_hospital_database, ensure_db_exists
from .lab_table_manager import (
    compile_record_values,
    ensure_lab_tables,
    extract_custom_values_from_row,
    fetch_latest_record,
    fetch_record_history,
    fetch_record_version,
    insert_record,
    insert_version,
    update_record,
    slugify,
)
from .utils import generate_temp_password, check_and_activate_without_session, update_password_with_verification
from .emails import (
    send_verification_otp,
    send_resend_otp,
    send_doctor_credentials,
    send_nurse_credentials,
    send_technician_credentials,
    send_patient_credentials,
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

    # Provision a dedicated hospital-local DB immediately after registration.
    create_hospital_database(str(hospital.id))

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
    total_technicians = HospitalUser.objects.filter(hospital=hospital, role='technician').count()
    total_patients = Patient.objects.filter(registered_by=hospital).count()
    return hospital, total_doctors, total_nurses, total_patients,total_technicians


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
    return update_password_with_verification(
        instance=hospital,
        current_password=current_password,
        new_password=new_password,
        confirm_password=confirm_password,
    )


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


# ─── Technicians Services ───────────────────────────────────────────────────────────

# get all technicians for a hospital
def service_get_technicians(hospital_id):
    hospital = Hospital.objects.get(id=hospital_id)
    return HospitalUser.objects.filter(hospital=hospital, role='technician').order_by('-created_at')

# validate and create a new technician — returns (technician, errors)
def service_add_technician(hospital_id, full_name, email, phone, employee_id):
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
    technician = HospitalUser.objects.create(
        hospital      = hospital,
        full_name     = full_name,
        email         = email,
        phone         = phone,
        employee_id   = employee_id,
        role          = 'technician',
        password_hash = make_password(temp_password),
        status        = 'active',
    )

    send_technician_credentials(full_name, email, hospital.hospital_name, temp_password)
    return technician, None

# get a single technician scoped to hospital — returns (technician, error)
def service_get_technician(hospital_id, pk):
    try:
        return HospitalUser.objects.get(id=pk, hospital_id=hospital_id, role='technician'), None
    except HospitalUser.DoesNotExist:
        return None, 'Technician not found'

# toggle technician active/inactive — returns (technician, error)
def service_toggle_technician(hospital_id, pk):
    technician, error = service_get_technician(hospital_id, pk)
    if error:
        return None, error
    technician.status = 'inactive' if technician.status == 'active' else 'active'
    technician.save()
    return technician, None


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
    normalized_email = (email or '').strip().lower()

    errors = {}
    if not gov_id_number:
        errors['gov_id'] = 'Government ID is required'
    if not full_name:
        errors['full_name'] = 'Full name is required'
    if not normalized_email:
        errors['email'] = 'Email is required'
    else:
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$'
        if not re.match(email_regex, normalized_email):
            errors['email'] = 'Enter a valid email address'
        elif Patient.objects.filter(email=normalized_email).exists():
            errors['email'] = 'A patient with this email already exists'
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

    temp_password = generate_temp_password()

    # encrypt gov ID before storing — hash kept separately for lookups
    patient = Patient.objects.create(
        gov_id_type   = gov_id_type,
        gov_id_number = encrypt(gov_id_number),
        gov_id_hash   = gov_id_hash,
        full_name     = full_name,
        gender        = gender  or None,
        phone         = phone   or None,
        email         = normalized_email,
        address       = address or None,
        password_hash = make_password(temp_password),
        registered_by = hospital,
    )

    send_patient_credentials(patient.full_name, patient.email, hospital.hospital_name, temp_password)

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




# ─── Doctor Portal Services ───────────────────────────────────────────────────

# get all info in dashboard 
def service_get_doctor_dashboard_data(staff_id, hospital_id):
    hospital       = Hospital.objects.get(id=hospital_id)
    total_patients = Patient.objects.filter(is_active=True).count()
    total_records  = MedicalRecordMeta.objects.filter(
        hospital_id=hospital_id,
        lab_request__requested_by_id=staff_id,
    ).count()
    total_reports  = 0   # TODO: FileUpload.objects.filter(uploaded_by_id=staff_id).count()
    return total_patients, total_records, total_reports


 
def service_get_doctor_profile(staff_id):
    try:
        return HospitalUser.objects.get(id=staff_id, role='doctor'), None
    except HospitalUser.DoesNotExist:
        return None, 'Doctor not found'
 
 
def service_update_doctor_personal(staff_id, date_of_birth, gender, years_experience,
                                   license_number, home_address, bio):
    try:
        doctor = HospitalUser.objects.get(id=staff_id, role='doctor')
    except HospitalUser.DoesNotExist:
        return None, 'Doctor not found'
 
    if date_of_birth:
        doctor.date_of_birth = date_of_birth
    if gender:
        doctor.gender = gender
 
    # allow clearing these fields by passing empty string
    doctor.years_experience = int(years_experience) if years_experience else None
    doctor.license_number   = license_number.strip() or None
    doctor.home_address     = home_address.strip() or None
    doctor.bio              = bio.strip() or None
 
    doctor.save()
    return doctor, None
 
 
def service_update_doctor_password(staff_id, current_password, new_password, confirm_password):
    """Change doctor password after verifying the current one."""
    try:
        doctor = HospitalUser.objects.get(id=staff_id, role='doctor')
    except HospitalUser.DoesNotExist:
        return False, 'Doctor not found'
 
    errors = {}
    if not current_password:
        errors['current_password'] = 'Current password is required'
    elif not check_password(current_password, doctor.password_hash):
        errors['current_password'] = 'Current password is incorrect'
 
    if not new_password:
        errors['new_password'] = 'New password is required'
    elif len(new_password) < 8:
        errors['new_password'] = 'Password must be at least 8 characters'
 
    if new_password and confirm_password and new_password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match'
 
    if errors:
        return False, errors
 
    doctor.password_hash = make_password(new_password)
    doctor.save()
    return True, None

# Show patients relevant to the hospital by default.
# If gov_id_type + gov_id_number_query are provided, allow explicit lookup by registered government ID.
def service_get_doctor_patients(hospital_id, gov_id_type=None, gov_id_number_query=None):
    gov_id_type = (gov_id_type or '').strip().lower()
    gov_id_number_query = (gov_id_number_query or '').replace(' ', '').strip()

    # Explicit government-ID lookup mode: doctor can open any active patient only when searched by gov ID.
    if gov_id_type and gov_id_number_query:
        gov_id_hash = hashlib.sha256(f"{gov_id_type}{gov_id_number_query}".encode()).hexdigest()
        patients = Patient.objects.filter(gov_id_hash=gov_id_hash, is_active=True).order_by('-created_at')
    else:
        hospital_record_patient_ids = MedicalRecordMeta.objects.filter(
            hospital_id=hospital_id,
        ).values_list('patient_id', flat=True)

        patients = Patient.objects.filter(
            Q(is_active=True, registered_by_id=hospital_id)
            | Q(is_active=True, id__in=hospital_record_patient_ids)
        ).distinct().order_by('-created_at')

    # attach assignment info to each patient object for easy template access
    for patient in patients:
        patient.assigned_nurses = PatientAssignment.objects.filter(
            patient=patient,
            role='nurse',
            staff__hospital_id=hospital_id,
        ).select_related('staff')

    return patients

# Return a single patient with nurse assignments and active labs.
def service_get_doctor_patient_detail(pk, hospital_id):
    try:
        hospital = Hospital.objects.get(id=hospital_id)
        patient  = Patient.objects.get(id=pk, is_active=True)
    except (Hospital.DoesNotExist, Patient.DoesNotExist):
        return None, None, None, None, None, None, 'Patient not found'

    # decrypt + mask gov ID
    try:
        raw_id        = decrypt(patient.gov_id_number)
        gov_id_masked = '•' * (len(raw_id) - 4) + raw_id[-4:]
    except Exception:
        gov_id_masked = '••••••••'

    # current assignments
    assigned_nurses = PatientAssignment.objects.filter(
        patient=patient,
        role='nurse',
        staff__hospital=hospital,
    ).select_related('staff')

    # IDs already assigned (to exclude from dropdown)
    assigned_nurse_ids = assigned_nurses.values_list('staff_id', flat=True)

    # available nurses not yet assigned to this patient
    available_nurses = HospitalUser.objects.filter(
        hospital=hospital, role='nurse', status='active'
    ).exclude(id__in=assigned_nurse_ids)

    available_labs = Lab.objects.filter(
        hospital=hospital,
        is_active=True,
    ).order_by('name')

    patient_records = MedicalRecordMeta.objects.filter(
        patient_id=patient.id,
        hospital_id=hospital.id,
    ).select_related(
        'lab_request',
        'lab_request__lab',
        'lab_request__requested_by',
    ).order_by('-updated_at')

    return (
        patient,
        gov_id_masked,
        list(assigned_nurses),
        list(available_nurses),
        list(available_labs),
        list(patient_records),
        None
    )

# Assign a nurse to a patient.
def service_assign_staff_to_patient(patient_id, staff_id, role, assigned_by_id):
    if role != 'nurse':
        return None, 'Only nurse assignment is allowed in doctor workflow'
    
    try:
        patient     = Patient.objects.get(id=patient_id)
        staff       = HospitalUser.objects.get(id=staff_id, role=role, status='active')
        assigned_by = HospitalUser.objects.get(id=assigned_by_id)
    except Patient.DoesNotExist:
        return None, 'Patient not found'
    except HospitalUser.DoesNotExist:
        return None, 'Nurse not found or inactive'

    # check they belong to the same hospital
    if staff.hospital_id != patient.registered_by_id:
        return None, 'Staff does not belong to this hospital'

    # check duplicate assignment
    if PatientAssignment.objects.filter(patient=patient, staff=staff).exists():
        return None, f'{staff.full_name} is already assigned to this patient'

    assignment = PatientAssignment.objects.create(
        patient=patient,
        staff=staff,
        role=role,
        assigned_by=assigned_by,
    )
    return assignment, None


def service_remove_staff_from_patient(patient_id, staff_id):
    """
    Remove a nurse or technician assignment from a patient.
    Returns (True, None) on success or (False, error).
    """
    try:
        assignment = PatientAssignment.objects.get(
            patient_id=patient_id, staff_id=staff_id
        )
        assignment.delete()
        return True, None
    except PatientAssignment.DoesNotExist:
        return False, 'Assignment not found'



# ─── Admin Lab Services ───────────────────────────────────────────────────────

def service_create_lab(hospital_id, lab_type, name, custom_field_schema=None):
    if lab_type not in dict(Lab.LAB_TYPE_CHOICES):
        return None, {'lab_type': 'Invalid lab type'}

    hospital = Hospital.objects.get(id=hospital_id)
    if Lab.objects.filter(hospital=hospital, lab_type=lab_type, is_active=True).exists():
        return None, {'lab_type': 'This lab type already exists in your hospital'}

    if not name or not name.strip():
        return None, {'name': 'Lab name is required'}

    normalized_schema, schema_errors = _normalize_custom_field_schema(custom_field_schema or [])
    if schema_errors:
        return None, schema_errors

    archived_lab = Lab.objects.filter(
        hospital=hospital,
        lab_type=lab_type,
        is_active=False,
    ).order_by('-created_at').first()

    if archived_lab:
        archived_lab.name = name.strip()
        archived_lab.custom_field_schema = normalized_schema
        archived_lab.is_active = True
        archived_lab.save(update_fields=['name', 'custom_field_schema', 'is_active'])
        alias = ensure_db_exists(hospital_id)
        ensure_lab_tables(alias, archived_lab)
        return archived_lab, None

    lab = Lab.objects.create(
        hospital=hospital,
        lab_type=lab_type,
        name=name.strip(),
        custom_field_schema=normalized_schema,
    )
    alias = ensure_db_exists(hospital_id)
    ensure_lab_tables(alias, lab)
    return lab, None


def service_delete_lab(hospital_id, lab_id):
    try:
        lab = Lab.objects.get(id=lab_id, hospital_id=hospital_id)
    except Lab.DoesNotExist:
        return False, 'Lab not found'

    if not lab.is_active:
        return True, None

    active_requests_exist = LabRequest.objects.filter(
        lab=lab,
        status__in=[LabRequest.STATUS_PENDING, LabRequest.STATUS_IN_PROGRESS],
    ).exists()
    if active_requests_exist:
        return False, 'Cannot delete while pending/in-progress requests exist for this lab'

    # Archive the lab so historical records remain intact while allowing future recreation.
    lab.is_active = False
    lab.save(update_fields=['is_active'])
    LabAssignment.objects.filter(lab=lab).delete()
    return True, None


def _normalize_custom_field_schema(schema):
    if schema in (None, ''):
        return [], None
    if not isinstance(schema, list):
        return None, {'custom_field_schema': 'Field schema must be a list of field definitions'}

    allowed_types = {'text', 'textarea', 'number', 'integer', 'decimal', 'date', 'choice', 'boolean'}
    allowed_roles = {'doctor', 'technician'}
    reserved_keys = {'diagnosis', 'treatment_plan', 'notes', 'age', 'gender', 'technician_change_reason'}

    normalized = []
    seen_keys = set()

    for index, field_def in enumerate(schema):
        if not isinstance(field_def, dict):
            return None, {'custom_field_schema': f'Field #{index + 1} must be an object'}

        label = str(field_def.get('label') or '').strip()
        key_source = field_def.get('key') or label
        key = slugify(str(key_source or ''))
        field_type = str(field_def.get('type') or 'text').strip().lower()
        required = bool(field_def.get('required', False))
        help_text = str(field_def.get('help_text') or '').strip()
        options = field_def.get('options') or []
        fill_by = str(field_def.get('fill_by') or 'technician').strip().lower()

        if not key:
            return None, {'custom_field_schema': f'Field #{index + 1} requires a key or label'}
        if key in seen_keys:
            return None, {'custom_field_schema': f'Duplicate field key: {key}'}
        if key in reserved_keys:
            return None, {'custom_field_schema': f'Field key {key} is already built into the lab workflow'}
        if field_type not in allowed_types:
            return None, {'custom_field_schema': f'Invalid field type for {key}'}
        if fill_by not in allowed_roles:
            return None, {'custom_field_schema': f'Invalid fill by role for {key}'}
        if field_type == 'choice' and not isinstance(options, list):
            return None, {'custom_field_schema': f'Choice field {key} must include an options list'}

        normalized_options = []
        if field_type == 'choice':
            for opt in options:
                if isinstance(opt, dict):
                    value = str(opt.get('value') or '').strip()
                    option_label = str(opt.get('label') or value).strip()
                    if not value:
                        continue
                    normalized_options.append({'value': value, 'label': option_label})
                else:
                    value = str(opt).strip()
                    if not value:
                        continue
                    normalized_options.append({'value': value, 'label': value})
            if required and not normalized_options:
                return None, {'custom_field_schema': f'Choice field {key} requires at least one option'}

        seen_keys.add(key)
        normalized.append({
            'key': key,
            'label': label or key,
            'type': field_type,
            'fill_by': fill_by,
            'required': required,
            'help_text': help_text,
            'options': normalized_options if field_type == 'choice' else [],
        })

    return normalized, None


def _filter_custom_fields_for_role(schema, role):
    role = (role or '').strip().lower()
    return [field for field in (schema or []) if field.get('fill_by', 'doctor') == role]


def _validate_custom_field_values(schema, values):
    if values in (None, ''):
        values = {}
    if not isinstance(values, dict):
        return None, {'custom_field_values': 'Custom field values must be a JSON object'}

    normalized = {}
    errors = {}
    schema_map = {field['key']: field for field in (schema or [])}

    for key, field in schema_map.items():
        raw_value = values.get(key)
        if raw_value in (None, ''):
            if field['required']:
                errors[key] = 'This field is required'
            continue

        field_type = field['type']
        if field_type in {'text', 'textarea', 'date'}:
            normalized[key] = str(raw_value)
        elif field_type == 'integer':
            try:
                normalized[key] = int(raw_value)
            except (TypeError, ValueError):
                errors[key] = 'Enter a whole number'
        elif field_type == 'number':
            try:
                normalized[key] = float(raw_value)
            except (TypeError, ValueError):
                errors[key] = 'Enter a number'
        elif field_type == 'decimal':
            try:
                normalized[key] = float(raw_value)
            except (TypeError, ValueError):
                errors[key] = 'Enter a decimal number'
        elif field_type == 'boolean':
            if isinstance(raw_value, bool):
                normalized[key] = raw_value
            elif str(raw_value).lower() in {'true', '1', 'yes', 'on'}:
                normalized[key] = True
            elif str(raw_value).lower() in {'false', '0', 'no', 'off'}:
                normalized[key] = False
            else:
                errors[key] = 'Enter true or false'
        elif field_type == 'choice':
            option_values = [option.get('value') if isinstance(option, dict) else option for option in field.get('options', [])]
            if raw_value not in option_values:
                errors[key] = 'Invalid choice'
            else:
                normalized[key] = raw_value
        else:
            normalized[key] = raw_value

    for key in values.keys():
        if key not in schema_map:
            normalized[key] = values[key]

    if errors:
        return None, errors
    return normalized, None


def service_get_labs(hospital_id):
    labs = Lab.objects.filter(hospital_id=hospital_id).order_by('name')
    result = []
    for lab in labs:
        result.append({
            'lab': lab,
            'technicians_count': LabAssignment.objects.filter(lab=lab).count(),
            'pending_count': LabRequest.objects.filter(lab=lab, status=LabRequest.STATUS_PENDING).count(),
            'completed_count': LabRequest.objects.filter(lab=lab, status=LabRequest.STATUS_COMPLETED).count(),
        })
    return result


def service_get_lab_detail(hospital_id, lab_id):
    try:
        lab = Lab.objects.get(id=lab_id, hospital_id=hospital_id)
    except Lab.DoesNotExist:
        return None, None, None, None, 'Lab not found'

    assignments = LabAssignment.objects.filter(lab=lab).select_related('technician')
    pending_requests = LabRequest.objects.filter(lab=lab, status=LabRequest.STATUS_PENDING).select_related('patient', 'requested_by')
    completed_count = LabRequest.objects.filter(lab=lab, status=LabRequest.STATUS_COMPLETED).count()
    return lab, list(assignments), list(pending_requests), completed_count, None


def service_assign_technician_to_lab(hospital_id, lab_id, technician_id):
    try:
        lab = Lab.objects.get(id=lab_id, hospital_id=hospital_id)
        technician = HospitalUser.objects.get(
            id=technician_id,
            hospital_id=hospital_id,
            role='technician',
            status='active',
        )
    except Lab.DoesNotExist:
        return None, 'Lab not found'
    except HospitalUser.DoesNotExist:
        return None, 'Technician not found or inactive'

    assignment, created = LabAssignment.objects.get_or_create(lab=lab, technician=technician)
    if not created:
        return None, 'Technician already assigned to this lab'
    return assignment, None


def service_remove_technician_from_lab(lab_id, technician_id):
    deleted, _ = LabAssignment.objects.filter(lab_id=lab_id, technician_id=technician_id).delete()
    if not deleted:
        return False, 'Assignment not found'
    return True, None


def service_get_available_technicians_for_lab(hospital_id, lab_id):
    assigned_ids = LabAssignment.objects.filter(lab_id=lab_id).values_list('technician_id', flat=True)
    return HospitalUser.objects.filter(
        hospital_id=hospital_id,
        role='technician',
        status='active',
    ).exclude(id__in=assigned_ids).order_by('full_name')


# ─── Doctor Lab Request Services ──────────────────────────────────────────────

def service_get_hospital_labs(hospital_id):
    return Lab.objects.filter(hospital_id=hospital_id, is_active=True).order_by('name')


def service_send_to_lab(patient_id, lab_id, doctor_id, chest_pain_type, diagnosis, treatment_plan, notes, custom_field_values=None):
    try:
        doctor = HospitalUser.objects.get(id=doctor_id, role='doctor', status='active')
        patient = Patient.objects.get(id=patient_id)
        lab = Lab.objects.get(id=lab_id, hospital_id=doctor.hospital_id, is_active=True)
    except HospitalUser.DoesNotExist:
        return None, {'doctor': 'Doctor not found'}
    except Patient.DoesNotExist:
        return None, {'patient': 'Patient not found'}
    except Lab.DoesNotExist:
        return None, {'lab': 'Lab not found or inactive'}

    if LabRequest.objects.filter(
        patient=patient,
        lab=lab,
        status__in=[LabRequest.STATUS_PENDING, LabRequest.STATUS_IN_PROGRESS],
    ).exists():
        return None, {'lab': 'This patient already has an active request for this lab'}

    schema, schema_errors = _normalize_custom_field_schema(lab.custom_field_schema or [])
    if schema_errors:
        return None, schema_errors

    doctor_schema = _filter_custom_fields_for_role(schema, 'doctor')
    normalized_custom_values, custom_errors = _validate_custom_field_values(doctor_schema, custom_field_values or {})
    if custom_errors:
        return None, custom_errors

    normalized_chest_pain_type = _normalize_chest_pain_type(chest_pain_type)

    errors = {}
    if not diagnosis or not diagnosis.strip():
        errors['diagnosis'] = 'Diagnosis is required'
    if not treatment_plan or not treatment_plan.strip():
        errors['treatment_plan'] = 'Treatment plan is required'
    if errors:
        return None, errors

    request_obj = LabRequest.objects.create(
        patient=patient,
        lab=lab,
        requested_by=doctor,
        status=LabRequest.STATUS_PENDING,
        chest_pain_type=normalized_chest_pain_type,
        diagnosis=diagnosis.strip(),
        treatment_plan=treatment_plan.strip(),
        notes=(notes or '').strip() or None,
        custom_field_values=normalized_custom_values or {},
    )
    return request_obj, None


def service_doctor_reassess_record(record_id, doctor_id, hospital_id, chest_pain_type, diagnosis, treatment_plan, notes, reason, send_to_queue=True):
    try:
        doctor = HospitalUser.objects.get(
            id=doctor_id,
            hospital_id=hospital_id,
            role='doctor',
            status='active',
        )
    except HospitalUser.DoesNotExist:
        return None, {'doctor': 'Doctor not found or inactive'}

    meta = MedicalRecordMeta.objects.select_related('lab_request').filter(
        record_id=record_id,
        hospital_id=hospital_id,
    ).first()
    if not meta:
        return None, {'record': 'Medical record not found'}

    request_obj = meta.lab_request

    normalized_chest_pain_type = _normalize_chest_pain_type(
        chest_pain_type,
        fallback=request_obj.chest_pain_type or LabRequest.CHEST_PAIN_CHOICES[0][0],
    )

    errors = {}
    if not diagnosis or not diagnosis.strip():
        errors['diagnosis'] = 'Diagnosis is required'
    if not treatment_plan or not treatment_plan.strip():
        errors['treatment_plan'] = 'Treatment plan is required'
    if not reason or not reason.strip():
        errors['reason'] = 'Please provide a reason for reassessment'
    if errors:
        return None, errors

    old_payload = {
        'chest_pain_type': request_obj.chest_pain_type,
        'diagnosis': request_obj.diagnosis,
        'treatment_plan': request_obj.treatment_plan,
        'notes': request_obj.notes or '',
    }
    new_payload = {
        'chest_pain_type': normalized_chest_pain_type,
        'diagnosis': diagnosis.strip(),
        'treatment_plan': treatment_plan.strip(),
        'notes': (notes or '').strip(),
    }

    changed_fields = [field for field in old_payload if old_payload[field] != new_payload[field]]
    if not changed_fields:
        return None, {'changes': 'No updates detected. Please change at least one field.'}

    request_obj.chest_pain_type = new_payload['chest_pain_type']
    request_obj.diagnosis = new_payload['diagnosis']
    request_obj.treatment_plan = new_payload['treatment_plan']
    request_obj.notes = new_payload['notes'] or None
    update_fields = [
        'chest_pain_type',
        'diagnosis',
        'treatment_plan',
        'notes',
    ]
    if send_to_queue:
        request_obj.status = LabRequest.STATUS_PENDING
        request_obj.completed_at = None
        update_fields.extend(['status', 'completed_at'])

    request_obj.save(update_fields=update_fields)

    LabRequestRevision.objects.create(
        lab_request=request_obj,
        revised_by=doctor,
        changed_fields=changed_fields,
        reason=reason.strip(),
    )

    # Doctor reassessment must also produce a new immutable record version.
    alias = ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)
    ensure_lab_tables(alias, request_obj.lab)

    old_record = fetch_latest_record(alias, request_obj.lab, record_id)
    if not old_record:
        history_rows = list(fetch_record_history(alias, request_obj.lab, record_id))
        if not history_rows:
            return None, {'record': 'Record history not found for reassessment versioning'}
        old_record = history_rows[-1]

    old_version = int(getattr(old_record, 'version', getattr(old_record, 'version_number', 1)))
    next_version = old_version + 1

    existing_custom_values = extract_custom_values_from_row(old_record, request_obj.lab)
    custom_field_values = {
        **(meta.custom_field_values or {}),
        **(existing_custom_values or {}),
    }
    meta_custom_field_values = _to_json_compatible(custom_field_values)

    payload = {
        'age': getattr(old_record, 'age', 0),
        'gender': getattr(old_record, 'gender', 'Male'),
    }

    new_record_row = compile_record_values(
        request_obj,
        {
            'row_id': str(uuid.uuid4()),
            'record_id': str(record_id),
            'recorded_by_id': str(doctor_id),
            'version': next_version,
            'is_latest': True,
            'sha256_hash': '',
            **payload,
        },
        custom_field_values,
    )
    record_hash = _payload_hash({k: v for k, v in new_record_row.items() if k != 'sha256_hash'})
    new_record_row['sha256_hash'] = record_hash

    updated_row_count = update_record(alias, request_obj.lab, record_id, {
        **new_record_row,
        'record_id': str(record_id),
    })
    if not updated_row_count:
        insert_record(alias, request_obj.lab, {
            **new_record_row,
            'record_id': str(record_id),
            'is_latest': 1,
            'version': next_version,
        })

    version_row = {
        **new_record_row,
        'version_row_id': str(uuid.uuid4()),
        'version_number': next_version,
        'changed_by_id': str(doctor_id),
        'change_reason': f"Doctor reassessment: {(reason or '').strip()}",
    }
    insert_version(alias, request_obj.lab, version_row)

    MedicalRecordMeta.objects.filter(record_id=record_id).update(
        sha256_hash=record_hash,
        version=next_version,
        recorded_by_id=doctor_id,
        custom_field_values=meta_custom_field_values,
        updated_at=timezone.now(),
    )

    return request_obj, None


# ─── Technician Portal Services ───────────────────────────────────────────────

def service_get_technician_dashboard_data(staff_id):
    queue = service_get_lab_queue(staff_id)
    total_requests = len(queue)
    total_records = service_get_technician_records(staff_id=staff_id, hospital_id=None).count()
    total_reports = total_records
    return total_requests, total_records, total_reports


def service_get_technician_profile(staff_id):
    try:
        return HospitalUser.objects.get(id=staff_id, role='technician'), None
    except HospitalUser.DoesNotExist:
        return None, 'Technician not found'


def service_update_technician_personal(staff_id, date_of_birth, gender, years_experience,
                                       license_number, home_address, bio):
    try:
        technician = HospitalUser.objects.get(id=staff_id, role='technician')
    except HospitalUser.DoesNotExist:
        return None, 'Technician not found'

    if date_of_birth:
        technician.date_of_birth = date_of_birth
    if gender:
        technician.gender = gender

    technician.years_experience = int(years_experience) if years_experience else None
    technician.license_number = license_number.strip() or None
    technician.home_address = home_address.strip() or None
    technician.bio = bio.strip() or None

    technician.save()
    return technician, None


def service_update_technician_password(staff_id, current_password, new_password, confirm_password):
    try:
        technician = HospitalUser.objects.get(id=staff_id, role='technician')
    except HospitalUser.DoesNotExist:
        return False, 'Technician not found'

    errors = {}
    if not current_password:
        errors['current_password'] = 'Current password is required'
    elif not check_password(current_password, technician.password_hash):
        errors['current_password'] = 'Current password is incorrect'

    if not new_password:
        errors['new_password'] = 'New password is required'
    elif len(new_password) < 8:
        errors['new_password'] = 'Password must be at least 8 characters'

    if new_password and confirm_password and new_password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match'

    if errors:
        return False, errors

    technician.password_hash = make_password(new_password)
    technician.save()
    return True, None


def service_get_lab_queue(staff_id):
    assigned_lab_ids = list(
        LabAssignment.objects.filter(technician_id=staff_id).values_list('lab_id', flat=True)
    )
    if not assigned_lab_ids:
        return []

    requests = LabRequest.objects.filter(
        lab_id__in=assigned_lab_ids,
        status__in=[LabRequest.STATUS_PENDING, LabRequest.STATUS_IN_PROGRESS],
    ).select_related('patient', 'requested_by', 'lab').order_by('-created_at')

    queue = list(requests)
    latest_revisions = {}
    for rev in LabRequestRevision.objects.filter(
        lab_request_id__in=[req.id for req in queue]
    ).select_related('revised_by').order_by('lab_request_id', '-created_at'):
        if rev.lab_request_id not in latest_revisions:
            latest_revisions[rev.lab_request_id] = rev
    for req in queue:
        rev = latest_revisions.get(req.id)
        req.latest_revision = rev
    return queue


def service_get_lab_request(staff_id, request_id):
    try:
        request_obj = LabRequest.objects.select_related('patient', 'requested_by', 'lab').get(id=request_id)
    except LabRequest.DoesNotExist:
        return None, 'Lab request not found'

    if not LabAssignment.objects.filter(lab=request_obj.lab, technician_id=staff_id).exists():
        return None, 'This request is not in your lab queue'
    return request_obj, None


def service_get_latest_lab_request_revision(lab_request_id):
    return LabRequestRevision.objects.filter(
        lab_request_id=lab_request_id
    ).select_related('revised_by').order_by('-created_at').first()


def service_get_existing_record_for_lab_request(lab_request_id, hospital_id):
    meta = MedicalRecordMeta.objects.filter(
        lab_request_id=lab_request_id,
        hospital_id=hospital_id,
    ).select_related('lab_request', 'lab_request__lab').only('record_id', 'lab_request__lab').first()
    if not meta:
        return None

    alias = ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)
    ensure_lab_tables(alias, meta.lab_request.lab)

    existing = fetch_latest_record(alias, meta.lab_request.lab, meta.record_id)
    if existing:
        existing.custom_field_values = extract_custom_values_from_row(existing, meta.lab_request.lab)
        return existing

    history_rows = list(fetch_record_history(alias, meta.lab_request.lab, meta.record_id))
    if history_rows:
        latest_from_history = history_rows[-1]
        latest_from_history.custom_field_values = extract_custom_values_from_row(latest_from_history, meta.lab_request.lab)
        return latest_from_history
    return None


def _record_payload(data):
    def as_int(value, default=None):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    gender = (data.get('gender') or '').strip()
    if gender not in {'Male', 'Female'}:
        gender = 'Male'

    return {
        'age': as_int(data.get('age'), 0),
        'gender': gender,
    }


def _payload_hash(payload):
    def _json_default(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value)

    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=_json_default)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _to_json_compatible(value):
    if isinstance(value, dict):
        return {str(k): _to_json_compatible(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_compatible(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _normalize_chest_pain_type(chest_pain_type, fallback=None):
    valid_chest_choices = dict(LabRequest.CHEST_PAIN_CHOICES)
    chest_choice_map = {k.lower(): k for k in valid_chest_choices.keys()}
    chest_choice_map.update({v.lower(): k for k, v in valid_chest_choices.items()})
    chest_choice_map.update({
        'typical angina': 'typical',
        'atypical angina': 'atypical',
        'non-anginal pain': 'non_anginal',
    })
    normalized = chest_choice_map.get((chest_pain_type or '').strip().lower())
    if normalized:
        return normalized
    return fallback or LabRequest.CHEST_PAIN_CHOICES[0][0]


def service_create_medical_record(lab_request_id, technician_id, hospital_id, data, technician_reason=''):
    request_obj, error = service_get_lab_request(technician_id, lab_request_id)
    if error:
        return None, {'lab_request': error}

    alias = ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)
    ensure_lab_tables(alias, request_obj.lab)

    payload = _record_payload(data)
    schema, schema_errors = _normalize_custom_field_schema(request_obj.lab.custom_field_schema or [])
    if schema_errors:
        return None, schema_errors

    technician_schema = _filter_custom_fields_for_role(schema, 'technician')
    technician_custom_field_values = data.get('custom_field_values') or {}
    normalized_technician_values, custom_errors = _validate_custom_field_values(technician_schema, technician_custom_field_values)
    if custom_errors:
        return None, custom_errors

    custom_field_values = {
        **(request_obj.custom_field_values or {}),
        **(normalized_technician_values or {}),
    }

    existing_meta = MedicalRecordMeta.objects.filter(lab_request_id=request_obj.id).first()
    if existing_meta:
        cleaned_reason = (technician_reason or '').strip()
        if not cleaned_reason:
            return None, {
                'change_reason': 'Please add technician change reason for re-submission.'
            }

        new_record, errors = service_edit_medical_record(
            record_id=existing_meta.record_id,
            technician_id=technician_id,
            hospital_id=hospital_id,
            data=data,
            change_reason=f'Technician resubmission: {cleaned_reason}',
        )
        if errors:
            return None, errors

        request_obj.status = LabRequest.STATUS_COMPLETED
        request_obj.completed_at = timezone.now()
        request_obj.save(update_fields=['status', 'completed_at'])
        return new_record, None

    logical_record_id = uuid.uuid4()

    record_row = compile_record_values(
        request_obj,
        {
            'row_id': str(uuid.uuid4()),
            'record_id': str(logical_record_id),
            'recorded_by_id': str(technician_id),
            'version': 1,
            'is_latest': True,
            'sha256_hash': '',
            **payload,
        },
        custom_field_values,
    )
    record_hash = _payload_hash({k: v for k, v in record_row.items() if k != 'sha256_hash'})
    record_row['sha256_hash'] = record_hash

    insert_record(alias, request_obj.lab, record_row)

    version_row = {
        **record_row,
        'version_row_id': str(uuid.uuid4()),
        'version_number': 1,
        'changed_by_id': str(technician_id),
        'change_reason': 'Initial record submission',
    }
    insert_version(alias, request_obj.lab, version_row)

    MedicalRecordMeta.objects.create(
        record_id=logical_record_id,
        lab_request=request_obj,
        hospital_id=hospital_id,
        patient_id=request_obj.patient_id,
        recorded_by_id=technician_id,
        sha256_hash=record_hash,
        version=1,
        custom_field_values=custom_field_values,
    )

    request_obj.status = LabRequest.STATUS_COMPLETED
    request_obj.completed_at = timezone.now()
    request_obj.save(update_fields=['status', 'completed_at'])
    record = SimpleNamespace(**record_row)
    record.lab_request = request_obj
    record.custom_field_values = custom_field_values
    return record, None


def service_edit_medical_record(record_id, technician_id, hospital_id, data, change_reason):
    ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)

    meta = MedicalRecordMeta.objects.select_related('lab_request', 'lab_request__lab').filter(record_id=record_id).first()
    if not meta:
        return None, {'record': 'Record not found'}

    request_obj = meta.lab_request
    alias = ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)
    ensure_lab_tables(alias, request_obj.lab)

    old_record = fetch_latest_record(alias, request_obj.lab, record_id)
    if not old_record:
        history_rows = list(fetch_record_history(alias, request_obj.lab, record_id))
        if not history_rows:
            return None, {'record': 'Record not found'}
        old_record = history_rows[-1]

    payload = _record_payload(data)
    schema, schema_errors = _normalize_custom_field_schema(request_obj.lab.custom_field_schema or [])
    if schema_errors:
        return None, schema_errors

    technician_schema = _filter_custom_fields_for_role(schema, 'technician')
    technician_custom_field_values = data.get('custom_field_values') or {}
    normalized_technician_values, custom_errors = _validate_custom_field_values(technician_schema, technician_custom_field_values)
    if custom_errors:
        return None, custom_errors

    custom_field_values = {
        **(meta.custom_field_values or {}),
        **(normalized_technician_values or {}),
    }

    old_version = int(getattr(old_record, 'version', getattr(old_record, 'version_number', 1)))
    next_version = old_version + 1

    new_record_row = compile_record_values(
        request_obj,
        {
            'row_id': str(uuid.uuid4()),
            'record_id': str(record_id),
            'recorded_by_id': str(technician_id),
            'version': next_version,
            'is_latest': True,
            'sha256_hash': '',
            **payload,
        },
        custom_field_values,
    )
    record_hash = _payload_hash({k: v for k, v in new_record_row.items() if k != 'sha256_hash'})
    new_record_row['sha256_hash'] = record_hash

    updated_row_count = update_record(alias, request_obj.lab, record_id, {
        **new_record_row,
        'record_id': str(record_id),
    })

    if not updated_row_count:
        insert_record(alias, request_obj.lab, {
            **new_record_row,
            'record_id': str(record_id),
            'is_latest': 1,
            'version': next_version,
        })

    version_row = {
        **new_record_row,
        'version_row_id': str(uuid.uuid4()),
        'version_number': next_version,
        'changed_by_id': str(technician_id),
        'change_reason': (change_reason or '').strip() or 'Record updated',
    }
    insert_version(alias, request_obj.lab, version_row)

    MedicalRecordMeta.objects.filter(record_id=record_id).update(
        sha256_hash=record_hash,
        version=next_version,
        recorded_by_id=technician_id,
        custom_field_values=custom_field_values,
        updated_at=timezone.now(),
    )

    new_record = SimpleNamespace(**new_record_row)
    new_record.lab_request = request_obj
    new_record.custom_field_values = custom_field_values
    return new_record, None


def service_get_record_history(record_id, hospital_id):
    alias = ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)
    meta = MedicalRecordMeta.objects.select_related('lab_request', 'lab_request__lab').filter(record_id=record_id).first()
    if not meta:
        return []

    history = list(fetch_record_history(alias, meta.lab_request.lab, record_id))

    changed_by_ids = [str(h.changed_by_id) for h in history if getattr(h, 'changed_by_id', None)]
    users = {
        str(user.id): user
        for user in HospitalUser.objects.filter(id__in=changed_by_ids).only('id', 'full_name', 'role', 'employee_id')
    }

    def resolve_actor(changed_by_id):
        actor_key = str(changed_by_id)
        actor = users.get(actor_key)
        if actor:
            return actor
        if actor_key == str(meta.recorded_by_id):
            return HospitalUser.objects.filter(id=meta.recorded_by_id).only('id', 'full_name', 'role', 'employee_id').first()
        return None

    schema_label_map = {
        (field.get('key') or ''): (field.get('label') or field.get('key') or '')
        for field in (meta.lab_request.lab.custom_field_schema or [])
        if isinstance(field, dict)
    }
    schema_role_map = {
        (field.get('key') or ''): (
            'technician'
            if str(field.get('fill_by') or 'doctor').strip().lower() == 'technician'
            else 'doctor'
        )
        for field in (meta.lab_request.lab.custom_field_schema or [])
        if isinstance(field, dict)
    }
    default_label_map = {
        'diagnosis': 'Diagnosis',
        'treatment_plan': 'Treatment Plan',
        'notes': 'Notes',
        'chest_pain_type': 'Chest Pain Type',
        'age': 'Age',
        'gender': 'Gender',
    }
    doctor_default_keys = {'diagnosis', 'treatment_plan', 'notes', 'chest_pain_type'}
    technician_default_keys = {'age', 'gender'}

    def field_label(key):
        if key in schema_label_map and schema_label_map[key]:
            return schema_label_map[key]
        if key in default_label_map:
            return default_label_map[key]
        return key.replace('_', ' ').strip().title()

    def field_role(key):
        if key in schema_role_map:
            return schema_role_map[key]
        if key in doctor_default_keys:
            return 'doctor'
        if key in technician_default_keys:
            return 'technician'
        return 'technician'

    def build_public_state(item):
        state = {
            'diagnosis': getattr(item, 'diagnosis', None),
            'treatment_plan': getattr(item, 'treatment_plan', None),
            'notes': getattr(item, 'notes', None),
            'chest_pain_type': getattr(item, 'chest_pain_type', None),
            'age': getattr(item, 'age', None),
            'gender': getattr(item, 'gender', None),
        }
        state.update(extract_custom_values_from_row(item, meta.lab_request.lab))
        return state

    def as_text(value):
        if value is None:
            return '-'
        return str(value)

    timeline = []
    previous_state = None
    for item in history:
        actor = resolve_actor(item.changed_by_id)
        current_state = build_public_state(item)
        snapshot_rows = []

        if previous_state is None:
            for key, value in current_state.items():
                snapshot_rows.append({
                    'label': field_label(key),
                    'value': as_text(value),
                    'source_role': field_role(key),
                })
        else:
            for key, value in current_state.items():
                previous_value = previous_state.get(key)
                if value != previous_value:
                    snapshot_rows.append({
                        'label': field_label(key),
                        'previous': as_text(previous_value),
                        'current': as_text(value),
                        'source_role': field_role(key),
                    })

        previous_state = current_state
        timeline.append({
            'version_number': item.version_number,
            'changed_at': item.changed_at,
            'changed_by_id': str(item.changed_by_id),
            'changed_by_staff_code': (actor.employee_id if actor and getattr(actor, 'employee_id', None) else None),
            'changed_by_name': actor.full_name if actor else 'Unknown User',
            'changed_by_role': actor.role if actor else 'unknown',
            'change_reason': item.change_reason,
            'data_snapshot': snapshot_rows,
            'is_full_snapshot': item.version_number == 1,
            'event_type': 'created' if item.version_number == 1 else 'updated',
        })

    return list(reversed(timeline))


def service_get_record_detail(record_id, hospital_id, version_number=None):
    alias = ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)
    meta = MedicalRecordMeta.objects.select_related('lab_request', 'lab_request__requested_by', 'lab_request__lab').filter(record_id=record_id).first()
    if not meta:
        return None, None, None, 'Record metadata not found'

    if version_number:
        record = fetch_record_version(alias, meta.lab_request.lab, record_id, version_number)
    else:
        record = fetch_latest_record(alias, meta.lab_request.lab, record_id)

    if not record:
        history_rows = list(fetch_record_history(alias, meta.lab_request.lab, record_id))
        if not history_rows:
            return None, None, None, 'Record not found'
        if version_number:
            record = next((row for row in history_rows if int(getattr(row, 'version_number', 0)) == int(version_number)), history_rows[-1])
        else:
            record = history_rows[-1]

    history = service_get_record_history(record_id=record_id, hospital_id=hospital_id)
    history_asc = list(reversed(history))

    created_event = history_asc[0] if history_asc else None
    latest_event = history_asc[-1] if history_asc else None
    selected_event = next((h for h in history_asc if h['version_number'] == record.version), None)

    created_actor = None
    latest_actor = None
    if created_event and created_event['changed_by_id']:
        created_actor = HospitalUser.objects.filter(id=created_event['changed_by_id']).only('id', 'full_name', 'role').first()
    if latest_event and latest_event['changed_by_id']:
        latest_actor = HospitalUser.objects.filter(id=latest_event['changed_by_id']).only('id', 'full_name', 'role').first()
    if not created_actor and meta.recorded_by_id:
        created_actor = HospitalUser.objects.filter(id=meta.recorded_by_id).only('id', 'full_name', 'role').first()
    if not latest_actor and meta.recorded_by_id:
        latest_actor = HospitalUser.objects.filter(id=meta.recorded_by_id).only('id', 'full_name', 'role').first()

    audit = {
        'created_by_id': created_event['changed_by_id'] if created_event else None,
        'created_by_name': created_event['changed_by_name'] if created_event and created_event['changed_by_name'] != 'Unknown User' else (created_actor.full_name if created_actor else None),
        'created_by_role': created_event['changed_by_role'] if created_event and created_event['changed_by_role'] != 'unknown' else (created_actor.role if created_actor else None),
        'created_by_staff_code': created_event.get('changed_by_staff_code') if created_event else (created_actor.employee_id if created_actor and getattr(created_actor, 'employee_id', None) else None),
        'created_at': created_event['changed_at'] if created_event else record.created_at,
        'latest_updated_by_id': selected_event['changed_by_id'] if selected_event else (latest_event['changed_by_id'] if latest_event else None),
        'latest_updated_by_name': selected_event['changed_by_name'] if selected_event and selected_event['changed_by_name'] != 'Unknown User' else (
            latest_event['changed_by_name'] if latest_event and latest_event['changed_by_name'] != 'Unknown User' else (latest_actor.full_name if latest_actor else None)
        ),
        'latest_updated_by_role': selected_event['changed_by_role'] if selected_event and selected_event['changed_by_role'] != 'unknown' else (
            latest_event['changed_by_role'] if latest_event and latest_event['changed_by_role'] != 'unknown' else (latest_actor.role if latest_actor else None)
        ),
        'latest_updated_by_staff_code': selected_event.get('changed_by_staff_code') if selected_event else (
            latest_event.get('changed_by_staff_code') if latest_event else (latest_actor.employee_id if latest_actor and getattr(latest_actor, 'employee_id', None) else None)
        ),
        'latest_updated_at': selected_event['changed_at'] if selected_event else (latest_event['changed_at'] if latest_event else record.updated_at),
        'latest_update_reason': selected_event['change_reason'] if selected_event else (latest_event['change_reason'] if latest_event else 'Initial record submission'),
        'selected_version': record.version,
        'selected_version_event_type': selected_event['event_type'] if selected_event else 'updated',
        'selected_version_changed_at': selected_event['changed_at'] if selected_event else record.updated_at,
        'selected_version_changed_by_name': selected_event['changed_by_name'] if selected_event else None,
        'selected_version_changed_by_role': selected_event['changed_by_role'] if selected_event else None,
        'selected_version_changed_by_staff_code': selected_event.get('changed_by_staff_code') if selected_event else None,
        'selected_version_reason': selected_event['change_reason'] if selected_event else None,
    }

    record.lab_request = meta.lab_request
    record.custom_field_values = extract_custom_values_from_row(record, meta.lab_request.lab)

    return record, meta.lab_request, {
        'audit': audit,
        'timeline': history,
        'custom_field_values': extract_custom_values_from_row(record, meta.lab_request.lab),
        'lab_custom_field_schema': meta.lab_request.lab.custom_field_schema or [],
    }, None


def service_get_technician_records(staff_id, hospital_id):
    assigned_lab_ids = list(
        LabAssignment.objects.filter(technician_id=staff_id).values_list('lab_id', flat=True)
    )
    if not assigned_lab_ids:
        return MedicalRecordMeta.objects.none()

    filters = {
        'lab_request__lab_id__in': assigned_lab_ids,
    }
    if hospital_id:
        filters['hospital_id'] = hospital_id

    return MedicalRecordMeta.objects.filter(
        **filters,
    ).select_related(
        'lab_request',
        'lab_request__patient',
        'lab_request__lab',
        'lab_request__requested_by',
    ).order_by('-updated_at')


def service_get_doctor_records(hospital_id, gov_id_type=None, gov_id_number=None, lab_id=None, scope='all'):
    gov_id_type = (gov_id_type or '').strip().lower()
    gov_id_number = (gov_id_number or '').replace(' ', '').strip()
    lab_id = (lab_id or '').strip()
    scope = (scope or 'all').strip().lower()

    records = MedicalRecordMeta.objects.filter(
        hospital_id=hospital_id,
    ).select_related(
        'lab_request',
        'lab_request__patient',
        'lab_request__lab',
        'lab_request__requested_by',
    ).order_by('-updated_at')

    if scope == 'lab':
        records = records
    elif scope == 'medical':
        records = MedicalRecordMeta.objects.none()

    if lab_id:
        records = records.filter(lab_request__lab_id=lab_id)

    if gov_id_type and gov_id_number:
        gov_id_hash = hashlib.sha256(f"{gov_id_type}{gov_id_number}".encode()).hexdigest()
        records = records.filter(lab_request__patient__gov_id_hash=gov_id_hash)

    labs = Lab.objects.filter(hospital_id=hospital_id, is_active=True).order_by('name')

    grouped = []
    for lab in labs:
        lab_records = [record for record in records if record.lab_request.lab_id == lab.id]
        if lab_records:
            grouped.append({
                'lab': lab,
                'records': lab_records,
                'count': len(lab_records),
            })

    return records, list(labs), grouped


# Backward compatibility for existing API modules that still import legacy names.
def service_get_technician_patients(staff_id):
    return service_get_lab_queue(staff_id)


def service_get_technician_patient_detail(staff_id, patient_id):
    return None, None, None, None, 'Legacy patient-based technician flow removed. Use lab request detail.'