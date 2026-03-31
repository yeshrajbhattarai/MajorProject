import re
import random
import hashlib
import json
import uuid
from django.contrib.auth.hashers import make_password, check_password
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
from .local_models import MedicalRecord, MedicalRecordVersion
from .utils import generate_temp_password, check_and_activate_without_session
from .emails import (
    send_verification_otp,
    send_resend_otp,
    send_doctor_credentials,
    send_nurse_credentials,
    send_technician_credentials,
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




# ─── Doctor Portal Services ───────────────────────────────────────────────────

# get all info in dashboard 
def service_get_doctor_dashboard_data(staff_id, hospital_id):
    hospital       = Hospital.objects.get(id=hospital_id)
    total_patients = Patient.objects.filter(registered_by=hospital).count()
    total_records  = 0   # TODO: MedicalRecord.objects.filter(created_by_id=staff_id).count()
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

# Show all patients registered under the hospital.
def service_get_doctor_patients(hospital_id):
   
    hospital = Hospital.objects.get(id=hospital_id)
    patients = Patient.objects.filter(
        registered_by=hospital, is_active=True
    ).order_by('-created_at')

    # attach assignment info to each patient object for easy template access
    for patient in patients:
        patient.assigned_nurses = PatientAssignment.objects.filter(
            patient=patient, role='nurse'
        ).select_related('staff')

    return patients

# Return a single patient with nurse assignments and active labs.
def service_get_doctor_patient_detail(pk, hospital_id):
    
    try:
        hospital = Hospital.objects.get(id=hospital_id)
        patient  = Patient.objects.get(id=pk, registered_by=hospital)
    except (Hospital.DoesNotExist, Patient.DoesNotExist):
        return None, None, None, None, None, 'Patient not found'

    # decrypt + mask gov ID
    try:
        raw_id        = decrypt(patient.gov_id_number)
        gov_id_masked = '•' * (len(raw_id) - 4) + raw_id[-4:]
    except Exception:
        gov_id_masked = '••••••••'

    # current assignments
    assigned_nurses = PatientAssignment.objects.filter(
        patient=patient, role='nurse'
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

def service_create_lab(hospital_id, lab_type, name):
    if lab_type not in dict(Lab.LAB_TYPE_CHOICES):
        return None, {'lab_type': 'Invalid lab type'}

    hospital = Hospital.objects.get(id=hospital_id)
    if Lab.objects.filter(hospital=hospital, lab_type=lab_type).exists():
        return None, {'lab_type': 'This lab type already exists in your hospital'}

    if not name or not name.strip():
        return None, {'name': 'Lab name is required'}

    lab = Lab.objects.create(hospital=hospital, lab_type=lab_type, name=name.strip())
    return lab, None


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


def service_send_to_lab(patient_id, lab_id, doctor_id, chest_pain_type, diagnosis, treatment_plan, notes):
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

    if patient.registered_by_id != doctor.hospital_id:
        return None, {'patient': 'Patient does not belong to your hospital'}

    if LabRequest.objects.filter(
        patient=patient,
        lab=lab,
        status__in=[LabRequest.STATUS_PENDING, LabRequest.STATUS_IN_PROGRESS],
    ).exists():
        return None, {'lab': 'This patient already has an active request for this lab'}

    errors = {}
    if chest_pain_type not in dict(LabRequest.CHEST_PAIN_CHOICES):
        errors['chest_pain_type'] = 'Invalid chest pain type'
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
        chest_pain_type=chest_pain_type,
        diagnosis=diagnosis.strip(),
        treatment_plan=treatment_plan.strip(),
        notes=(notes or '').strip() or None,
    )
    return request_obj, None


def service_doctor_reassess_record(record_id, doctor_id, hospital_id, chest_pain_type, diagnosis, treatment_plan, notes, reason):
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

    valid_chest_choices = dict(LabRequest.CHEST_PAIN_CHOICES)
    errors = {}
    if chest_pain_type not in valid_chest_choices:
        errors['chest_pain_type'] = 'Invalid chest pain type'
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
        'chest_pain_type': chest_pain_type,
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
    request_obj.status = LabRequest.STATUS_PENDING
    request_obj.completed_at = None
    request_obj.save(update_fields=[
        'chest_pain_type',
        'diagnosis',
        'treatment_plan',
        'notes',
        'status',
        'completed_at',
    ])

    LabRequestRevision.objects.create(
        lab_request=request_obj,
        revised_by=doctor,
        changed_fields=changed_fields,
        reason=reason.strip(),
    )

    return request_obj, None


# ─── Technician Portal Services ───────────────────────────────────────────────

def service_get_technician_dashboard_data(staff_id):
    queue = service_get_lab_queue(staff_id)
    total_requests = len(queue)
    total_records = MedicalRecordMeta.objects.filter(recorded_by_id=staff_id).count()
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
    assignment = LabAssignment.objects.filter(technician_id=staff_id).select_related('lab').first()
    if not assignment:
        return []

    requests = LabRequest.objects.filter(
        lab=assignment.lab,
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
    ).only('record_id').first()
    if not meta:
        return None

    ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)
    return MedicalRecord.objects.filter(
        record_id=meta.record_id,
        is_latest=True,
    ).first()


def _record_payload(data):
    return {
        'age': int(data['age']),
        'gender': data['gender'],
        'blood_pressure_systolic': int(data['blood_pressure_systolic']),
        'blood_pressure_diastolic': int(data['blood_pressure_diastolic']),
        'cholesterol': int(data['cholesterol']),
        'blood_glucose': float(data['blood_glucose']),
        'heart_rate': int(data['heart_rate']),
        'ecg_result': data['ecg_result'],
    }


def _payload_hash(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def service_create_medical_record(lab_request_id, technician_id, hospital_id, data, technician_reason=''):
    request_obj, error = service_get_lab_request(technician_id, lab_request_id)
    if error:
        return None, {'lab_request': error}

    ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)

    payload = _record_payload(data)

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

    record_hash = _payload_hash(payload)
    logical_record_id = uuid.uuid4()

    record = MedicalRecord.objects.create(
        record_id=logical_record_id,
        lab_request_id=request_obj.id,
        patient_id=request_obj.patient_id,
        hospital_id=request_obj.patient.registered_by_id,
        recorded_by_id=technician_id,
        version=1,
        is_latest=True,
        sha256_hash=record_hash,
        **payload,
    )

    MedicalRecordVersion.objects.create(
        record_id=logical_record_id,
        version_number=1,
        data_snapshot=payload,
        changed_by_id=technician_id,
        change_reason='Initial record submission',
    )

    MedicalRecordMeta.objects.create(
        record_id=logical_record_id,
        lab_request=request_obj,
        hospital_id=hospital_id,
        patient_id=request_obj.patient_id,
        recorded_by_id=technician_id,
        sha256_hash=record_hash,
        version=1,
    )

    request_obj.status = LabRequest.STATUS_COMPLETED
    request_obj.completed_at = timezone.now()
    request_obj.save(update_fields=['status', 'completed_at'])
    return record, None


def service_edit_medical_record(record_id, technician_id, hospital_id, data, change_reason):
    ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)

    old_record = MedicalRecord.objects.filter(record_id=record_id, is_latest=True).first()
    if not old_record:
        return None, {'record': 'Record not found'}

    payload = _record_payload(data)
    record_hash = _payload_hash(payload)
    next_version = old_record.version + 1

    old_record.is_latest = False
    old_record.save(update_fields=['is_latest'])

    new_record = MedicalRecord.objects.create(
        record_id=old_record.record_id,
        lab_request_id=old_record.lab_request_id,
        patient_id=old_record.patient_id,
        hospital_id=old_record.hospital_id,
        recorded_by_id=technician_id,
        version=next_version,
        is_latest=True,
        sha256_hash=record_hash,
        **payload,
    )

    MedicalRecordVersion.objects.create(
        record_id=old_record.record_id,
        version_number=next_version,
        data_snapshot=payload,
        changed_by_id=technician_id,
        change_reason=(change_reason or '').strip() or 'Record updated',
    )

    MedicalRecordMeta.objects.filter(record_id=old_record.record_id).update(
        sha256_hash=record_hash,
        version=next_version,
        recorded_by_id=technician_id,
        updated_at=timezone.now(),
    )
    return new_record, None


def service_get_record_history(record_id, hospital_id):
    ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)
    history = list(MedicalRecordVersion.objects.filter(record_id=record_id).order_by('version_number'))

    changed_by_ids = [h.changed_by_id for h in history]
    users = {
        user.id: user
        for user in HospitalUser.objects.filter(id__in=changed_by_ids).only('id', 'full_name', 'role')
    }

    timeline = []
    for item in history:
        actor = users.get(item.changed_by_id)
        timeline.append({
            'version_number': item.version_number,
            'changed_at': item.changed_at,
            'changed_by_id': item.changed_by_id,
            'changed_by_name': actor.full_name if actor else 'Unknown User',
            'changed_by_role': actor.role if actor else 'unknown',
            'change_reason': item.change_reason,
            'data_snapshot': item.data_snapshot,
            'event_type': 'created' if item.version_number == 1 else 'updated',
        })

    return list(reversed(timeline))


def service_get_patient_records(patient_id, hospital_id):
    ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)
    records = MedicalRecord.objects.filter(patient_id=patient_id, hospital_id=hospital_id, is_latest=True).order_by('-updated_at')
    return list(records)


def service_get_record_detail(record_id, hospital_id, version_number=None):
    ensure_db_exists(hospital_id)
    set_hospital_db(hospital_id)

    queryset = MedicalRecord.objects.filter(record_id=record_id)
    if version_number:
        record = queryset.filter(version=version_number).first()
    else:
        record = queryset.filter(is_latest=True).first()

    if not record:
        return None, None, None, 'Record not found'

    meta = MedicalRecordMeta.objects.select_related('lab_request', 'lab_request__requested_by', 'lab_request__lab').filter(record_id=record_id).first()
    if not meta:
        return None, None, None, 'Record metadata not found'

    history = service_get_record_history(record_id=record_id, hospital_id=hospital_id)
    history_asc = list(reversed(history))

    created_event = history_asc[0] if history_asc else None
    latest_event = history_asc[-1] if history_asc else None
    selected_event = next((h for h in history_asc if h['version_number'] == record.version), None)

    audit = {
        'created_by_id': created_event['changed_by_id'] if created_event else None,
        'created_by_name': created_event['changed_by_name'] if created_event else None,
        'created_by_role': created_event['changed_by_role'] if created_event else None,
        'created_at': created_event['changed_at'] if created_event else record.created_at,
        'latest_updated_by_id': latest_event['changed_by_id'] if latest_event else None,
        'latest_updated_by_name': latest_event['changed_by_name'] if latest_event else None,
        'latest_updated_by_role': latest_event['changed_by_role'] if latest_event else None,
        'latest_updated_at': latest_event['changed_at'] if latest_event else record.updated_at,
        'latest_update_reason': latest_event['change_reason'] if latest_event else 'Initial record submission',
        'selected_version': record.version,
        'selected_version_event_type': selected_event['event_type'] if selected_event else 'updated',
        'selected_version_changed_at': selected_event['changed_at'] if selected_event else record.updated_at,
        'selected_version_changed_by_name': selected_event['changed_by_name'] if selected_event else None,
        'selected_version_changed_by_role': selected_event['changed_by_role'] if selected_event else None,
        'selected_version_reason': selected_event['change_reason'] if selected_event else None,
    }

    return record, meta.lab_request, {'audit': audit, 'timeline': history}, None


def service_get_technician_records(staff_id, hospital_id):
    return MedicalRecordMeta.objects.filter(
        recorded_by_id=staff_id,
        hospital_id=hospital_id,
    ).select_related(
        'lab_request',
        'lab_request__patient',
        'lab_request__lab',
        'lab_request__requested_by',
    ).order_by('-updated_at')


# Backward compatibility for existing API modules that still import legacy names.
def service_get_technician_patients(staff_id):
    return service_get_lab_queue(staff_id)


def service_get_technician_patient_detail(staff_id, patient_id):
    return None, None, None, None, 'Legacy patient-based technician flow removed. Use lab request detail.'