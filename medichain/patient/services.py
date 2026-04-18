import hashlib
import re

from django.contrib.auth.hashers import check_password, make_password

from hospitals.encryption import encrypt
from hospitals.models import Patient, LabRequest
from hospitals.utils import update_password_with_verification


EMAIL_REGEX = r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$'
INDIA_MOBILE_REGEX = r'^[6-9]\d{9}$'

REQUIRED_PROFILE_FIELDS = (
    'full_name',
    'email',
    'phone',
    'password_hash',
    'gender',
    'address',
    'date_of_birth',
    'blood_group',
    'gov_id_type',
    'gov_id_number',
)


def is_profile_complete(patient):
    """
    Full access requires registration + profile completion.
    This gate is used to protect medical records visibility.
    """
    return len(get_missing_profile_fields(patient)) == 0


def get_missing_profile_fields(patient):
    """
    Returns list of missing fields required to unlock records.
    """
    missing = []
    for field in REQUIRED_PROFILE_FIELDS:
        if not getattr(patient, field, None):
            missing.append('password' if field == 'password_hash' else field)
    return missing


def get_profile_completion_percent(patient):
    missing_count = len(get_missing_profile_fields(patient))
    required_count = len(REQUIRED_PROFILE_FIELDS)
    return int(((required_count - missing_count) / required_count) * 100)


def service_patient_register(full_name, email, phone, password, confirm_password):
    """
    Patient registration with required fields: name, email, phone, password
    """
    normalized_email = (email or '').strip().lower()
    cleaned_phone = (phone or '').replace(' ', '').strip()

    errors = {}
    if not full_name or not full_name.strip():
        errors['full_name'] = 'Full name is required'

    if not normalized_email:
        errors['email'] = 'Email is required'
    elif not re.match(EMAIL_REGEX, normalized_email):
        errors['email'] = 'Enter a valid email address'
    elif Patient.objects.filter(email=normalized_email).exists():
        errors['email'] = 'A patient with this email already exists'

    if not cleaned_phone:
        errors['phone'] = 'Phone number is required'
    elif not re.match(INDIA_MOBILE_REGEX, cleaned_phone):
        errors['phone'] = 'Enter a valid 10-digit Indian mobile number'

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

    patient = Patient.objects.create(
        gov_id_type=None,
        gov_id_number=None,
        gov_id_hash=None,
        full_name=full_name.strip(),
        gender=None,
        phone=cleaned_phone,
        email=normalized_email,
        address=None,
        password_hash=make_password(password),
        registered_by=None,
        registered_by_self=True,
        is_active=True,
    )
    return patient, None


def service_patient_update_profile(patient_id, full_name=None, email=None, phone=None,
                                   address=None, gender=None, date_of_birth=None, blood_group=None,
                                   gov_id_type=None, gov_id_number=None):
    """
    Update patient profile details.
    Returns (patient, errors) tuple
    """
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return None, {'error': 'Patient not found'}

    errors = {}

    # Full name (required)
    if full_name:
        if not full_name.strip():
            errors['full_name'] = 'Full name cannot be empty'
        else:
            patient.full_name = full_name.strip()
    else:
        if not patient.full_name:
            errors['full_name'] = 'Full name is required'

    # Email (required, unique)
    if email:
        email_normalized = email.strip().lower()
        if not re.match(EMAIL_REGEX, email_normalized):
            errors['email'] = 'Enter a valid email address'
        elif Patient.objects.filter(email=email_normalized).exclude(id=patient_id).exists():
            errors['email'] = 'This email is already in use'
        else:
            patient.email = email_normalized
    else:
        if not patient.email:
            errors['email'] = 'Email is required'

    # Phone (required, India mobile)
    if phone:
        cleaned_phone = phone.replace(' ', '').strip()
        if not re.match(INDIA_MOBILE_REGEX, cleaned_phone):
            errors['phone'] = 'Enter a valid 10-digit Indian mobile number'
        else:
            patient.phone = cleaned_phone
    else:
        if not patient.phone:
            errors['phone'] = 'Phone number is required'

    # Government ID (settable only if missing; locked once set)
    has_existing_gov_id = bool(patient.gov_id_type and patient.gov_id_number)
    if not has_existing_gov_id:
        cleaned_gov_id_type = (gov_id_type or '').strip().lower()
        cleaned_gov_id_number = (gov_id_number or '').replace(' ', '').strip()

        # ID is optional for profile update, but if user starts filling, validate fully.
        if cleaned_gov_id_type or cleaned_gov_id_number:
            if cleaned_gov_id_type not in {'aadhar', 'voter'}:
                errors['gov_id_type'] = 'Please select a valid government ID type'

            if not cleaned_gov_id_number:
                errors['gov_id_number'] = 'Government ID number is required'
            elif len(cleaned_gov_id_number) < 8:
                errors['gov_id_number'] = 'Government ID number is too short'

            if 'gov_id_type' not in errors and 'gov_id_number' not in errors:
                gov_id_hash = hashlib.sha256(
                    f"{cleaned_gov_id_type}{cleaned_gov_id_number}".encode()
                ).hexdigest()

                if Patient.objects.filter(gov_id_hash=gov_id_hash).exclude(id=patient_id).exists():
                    errors['gov_id_number'] = 'This government ID is already registered in the system'
                else:
                    patient.gov_id_type = cleaned_gov_id_type
                    patient.gov_id_number = encrypt(cleaned_gov_id_number)
                    patient.gov_id_hash = gov_id_hash

    # Address (optional)
    if address:
        patient.address = address.strip()

    # Gender (optional)
    if gender and gender in {'Male', 'Female', 'Other'}:
        patient.gender = gender

    # Date of birth (optional)
    if date_of_birth:
        patient.date_of_birth = date_of_birth

    # Blood group (optional)
    if blood_group and blood_group in {'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'}:
        patient.blood_group = blood_group

    if errors:
        return None, errors

    patient.save()
    return patient, None


def service_patient_update_password(patient_id, current_password, new_password, confirm_password):
    """
    Change patient password after verifying current password.
    Returns (success, error_message)
    """
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return False, 'Patient account not found.'

    return update_password_with_verification(
        instance=patient,
        current_password=current_password,
        new_password=new_password,
        confirm_password=confirm_password,
    )


def service_patient_complete_profile(patient_id, phone, address, gender=None):
    """
    Step 2: Complete profile after login
    Updates phone, address, gender (all optional for now)
    """
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return None, {'error': 'Patient not found'}

    errors = {}

    # Phone is optional in step 2
    if phone:
        if not re.match(INDIA_MOBILE_REGEX, phone.strip()):
            errors['phone'] = 'Enter a valid 10-digit Indian mobile number'
        else:
            patient.phone = phone.strip()

    # Address is optional
    if address:
        patient.address = address.strip()

    # Gender is optional
    if gender:
        if gender in {'Male', 'Female', 'Other'}:
            patient.gender = gender
        else:
            errors['gender'] = 'Invalid gender selection'

    if errors:
        return None, errors

    patient.save()
    return patient, None


def service_patient_login(email, password):
    normalized_email = (email or '').strip().lower()
    errors = {}

    if not normalized_email:
        errors['email'] = 'Email is required'
    if not password:
        errors['password'] = 'Password is required'
    if errors:
        return None, errors

    patient = Patient.objects.filter(email=normalized_email).first()
    if not patient:
        return None, {'email': 'No patient account found with this email'}

    if not patient.is_active:
        return None, {'email': 'Your patient account is inactive. Please contact your hospital.'}

    if not patient.password_hash or not check_password(password, patient.password_hash):
        return None, {'password': 'Incorrect password'}

    return patient, None


def service_get_patient_lab_requests(patient_id):
    """
    Get all lab requests for a patient (medical records).
    Only returns if profile is complete.
    """
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return None, []

    if not is_profile_complete(patient):
        return patient, []

    lab_requests = LabRequest.objects.filter(patient_id=patient_id).select_related(
        'lab', 'lab__hospital', 'requested_by', 'requested_by__hospital'
    ).prefetch_related(
        'record_meta'
    ).order_by('-created_at')

    return patient, lab_requests


def group_lab_requests_by_hospital(lab_requests):
    grouped = []
    by_hospital_id = {}

    for req in lab_requests:
        hospital = req.lab.hospital if getattr(req, 'lab', None) else None
        hospital_id = str(hospital.id) if hospital else 'self'
        hospital_name = hospital.hospital_name if hospital else 'Unknown Hospital'

        if hospital_id not in by_hospital_id:
            bucket = {
                'hospital_id': hospital_id,
                'hospital_name': hospital_name,
                'requests': [],
                'total_requests': 0,
                'pending_requests': 0,
                'completed_requests': 0,
            }
            by_hospital_id[hospital_id] = bucket
            grouped.append(bucket)

        bucket = by_hospital_id[hospital_id]
        record_meta = req.record_meta.first() if hasattr(req, 'record_meta') else None
        bucket['requests'].append({
            'request': req,
            'record_id': str(record_meta.record_id) if record_meta else None,
            'report_type': 'lab',
            'report_type_label': 'Lab Report',
        })
        bucket['total_requests'] += 1
        if req.status == LabRequest.STATUS_PENDING:
            bucket['pending_requests'] += 1
        elif req.status == LabRequest.STATUS_COMPLETED:
            bucket['completed_requests'] += 1

    return grouped


def service_get_patient_dashboard_data(patient_id):
    """
    Get patient dashboard data: profile info and lab requests count.
    """
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return None

    missing_fields = get_missing_profile_fields(patient)
    profile_complete = len(missing_fields) == 0
    lab_count = LabRequest.objects.filter(patient_id=patient_id).count()
    grouped_records = group_lab_requests_by_hospital(
        LabRequest.objects.filter(patient_id=patient_id).select_related('lab', 'lab__hospital').order_by('-created_at')
    )

    return {
        'patient': patient,
        'profile_complete': profile_complete,
        'missing_fields': missing_fields,
        'profile_completion_percent': get_profile_completion_percent(patient),
        'lab_count': lab_count,
        'hospitals_count': len(grouped_records),
        'grouped_records': grouped_records,
        'pending_labs': LabRequest.objects.filter(
            patient_id=patient_id, 
            status=LabRequest.STATUS_PENDING
        ).count(),
        'completed_labs': LabRequest.objects.filter(
            patient_id=patient_id,
            status=LabRequest.STATUS_COMPLETED
        ).count(),
    }
