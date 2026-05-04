import json
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render

from hospitals.encryption import decrypt
from hospitals.models import MedicalRecordMeta, Patient
from hospitals.services import (
    service_get_record_detail,
    service_get_record_history,
    service_get_patient_medical_records,
    service_get_finalized_medical_record_detail,
)

from .decorators import patient_required
from .services import (
    service_patient_login, 
    service_patient_register, 
    service_patient_complete_profile,
    service_patient_update_profile,
    service_patient_update_password,
    service_get_patient_dashboard_data,
    service_get_patient_lab_requests,
    is_profile_complete,
    get_missing_profile_fields,
    get_profile_completion_percent,
    group_lab_requests_by_hospital,
)


def patient_login(request):
    if request.session.get('user_type') == 'patient' and request.session.get('patient_id'):
        return redirect('patient_dashboard')

    if request.method == 'POST':
        patient, errors = service_patient_login(
            email=request.POST.get('email', ''),
            password=request.POST.get('password', ''),
        )
        
        # AJAX request — return JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                })
            request.session['user_type'] = 'patient'
            request.session['patient_id'] = str(patient.id)
            request.session['patient_name'] = patient.full_name
            return JsonResponse({
                'success': True,
                'redirect': '/patient/dashboard/',
            })
        
        # Regular form submission
        if errors:
            return render(request, 'patient/auth/auth.html', {
                'mode': 'login',
                'errors': errors,
                'form_data': request.POST,
            })

        request.session['user_type'] = 'patient'
        request.session['patient_id'] = str(patient.id)
        request.session['patient_name'] = patient.full_name
        return redirect('patient_dashboard')

    return render(request, 'patient/auth/auth.html', {
        'mode': 'login',
    })


def patient_register(request):
    if request.method == 'POST':
        patient, errors = service_patient_register(
            full_name=request.POST.get('full_name', '').strip(),
            email=request.POST.get('email', '').strip(),
            phone=request.POST.get('phone', '').strip(),
            password=request.POST.get('password', ''),
            confirm_password=request.POST.get('confirm_password', ''),
        )

        # AJAX request — return JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                })
            return JsonResponse({
                'success': True,
                'redirect': '/patient/login/?mode=login',
            })
        
        # Regular form submission
        if errors:
            return render(request, 'patient/auth/auth.html', {
                'mode': 'register',
                'errors': errors,
                'form_data': request.POST,
            })

        messages.success(request, f'{patient.full_name} registered successfully. Please login.')
        return redirect('patient_login')

    return render(request, 'patient/auth/auth.html', {
        'mode': 'register',
    })


@patient_required
def patient_complete_profile(request):
    """Step 2: Complete profile after registration/login"""
    patient_id = request.session.get('patient_id')
    patient = Patient.objects.filter(id=patient_id).first()
    
    if not patient:
        request.session.flush()
        return redirect('patient_login')

    if request.method == 'POST':
        patient, errors = service_patient_complete_profile(
            patient_id=patient_id,
            phone=request.POST.get('phone', '').strip(),
            address=request.POST.get('address', '').strip(),
            gender=request.POST.get('gender', '').strip(),
        )

        # AJAX request — return JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if errors:
                return JsonResponse({
                    'success': False,
                    'errors': errors,
                })
            return JsonResponse({
                'success': True,
                'redirect': '/patient/dashboard/',
            })

        # Regular form submission
        if errors:
            return render(request, 'patient/complete-profile.html', {
                'patient': patient,
                'errors': errors,
                'form_data': request.POST,
            })

        messages.success(request, 'Profile completed successfully!')
        return redirect('patient_dashboard')

    return render(request, 'patient/complete-profile.html', {
        'patient': patient,
    })


@patient_required
def patient_dashboard(request):
    """Patient dashboard with medical records and lab requests"""
    patient_id = request.session.get('patient_id')
    patient = Patient.objects.filter(id=patient_id).first()
    
    if not patient:
        request.session.flush()
        return redirect('patient_login')

    # Check if profile is complete
    if not is_profile_complete(patient):
        messages.warning(request, 'Complete all profile details to unlock medical records and reports.')
        return redirect('patient_profile')

    # Get dashboard data
    dashboard_data = service_get_patient_dashboard_data(patient_id)
    patient, lab_requests = service_get_patient_lab_requests(patient_id)
    hospital_record_groups = group_lab_requests_by_hospital(lab_requests)

    return render(request, 'patient/dashboard.html', {
        'patient': patient,
        'patient_hospital_name': patient.registered_by.hospital_name if patient.registered_by else 'Self Registered',
        'dashboard_data': dashboard_data,
        'lab_requests': lab_requests,
        'hospital_record_groups': hospital_record_groups,
    })


@patient_required
def patient_lab_reports(request):
    patient_id = request.session.get('patient_id')
    patient = Patient.objects.filter(id=patient_id).first()

    if not patient:
        request.session.flush()
        return redirect('patient_login')

    if not is_profile_complete(patient):
        messages.warning(request, 'Complete all profile details to unlock medical records and reports.')
        return redirect('patient_profile')

    _, lab_requests = service_get_patient_lab_requests(patient_id)
    hospital_record_groups = group_lab_requests_by_hospital(lab_requests)

    return render(request, 'patient/records.html', {
        'patient': patient,
        'patient_hospital_name': patient.registered_by.hospital_name if patient.registered_by else 'Self Registered',
        'hospital_record_groups': hospital_record_groups,
    })


@patient_required
def patient_medical_records(request):
    patient_id = request.session.get('patient_id')
    patient = Patient.objects.filter(id=patient_id).first()

    if not patient:
        request.session.flush()
        return redirect('patient_login')

    if not is_profile_complete(patient):
        messages.warning(request, 'Complete all profile details to unlock medical records and reports.')
        return redirect('patient_profile')

    records = service_get_patient_medical_records(patient_id=patient.id)
    
    # Get unique hospitals for filter dropdown
    hospital_ids = set(str(rec.doctor.hospital.id) for rec in records if rec.doctor and rec.doctor.hospital)
    from hospitals.models import Hospital
    hospitals = Hospital.objects.filter(id__in=hospital_ids).order_by('hospital_name')
    
    # Filter by hospital if hospital_id is provided
    hospital_id = request.GET.get('hospital_id', '').strip()
    if hospital_id:
        records = [rec for rec in records if rec.doctor and str(rec.doctor.hospital.id) == hospital_id]

    return render(request, 'patient/medical_records.html', {
        'patient': patient,
        'records': records,
        'hospitals': hospitals,
        'hospital_id': hospital_id,
        'patient_hospital_name': patient.registered_by.hospital_name if patient.registered_by else 'Self Registered',
    })


@patient_required
def patient_medical_record_detail(request, record_id):
    patient_id = request.session.get('patient_id')
    patient = Patient.objects.filter(id=patient_id).first()

    if not patient:
        request.session.flush()
        return redirect('patient_login')

    version_number = None
    version_query = request.GET.get('v', '').strip()
    if version_query:
        try:
            version_number = int(version_query)
        except ValueError:
            messages.error(request, 'Invalid medical record version requested.')
            return redirect('patient_medical_record_detail', record_id=record_id)

    record, detail_bundle, error = service_get_finalized_medical_record_detail(
        record_id=record_id,
        role='patient',
        patient_id=patient.id,
        version_number=version_number,
    )
    if error:
        messages.error(request, error)
        return redirect('patient_medical_records')

    return render(request, 'patient/medical_record_detail.html', {
        'patient': patient,
        'record_item': record,
        'detail_bundle': detail_bundle,
        'patient_hospital_name': patient.registered_by.hospital_name if patient.registered_by else 'Self Registered',
    })


@patient_required
def patient_records(request):
    return redirect('patient_lab_reports')


@patient_required
def patient_record_detail(request, record_id):
    patient_id = request.session.get('patient_id')
    patient = Patient.objects.filter(id=patient_id).first()

    if not patient:
        request.session.flush()
        return redirect('patient_login')

    meta = MedicalRecordMeta.objects.filter(record_id=record_id, patient_id=patient.id).first()
    if not meta:
        messages.error(request, 'Record not found for your account.')
        return redirect('patient_lab_reports')

    version_number = None
    version_query = request.GET.get('v', '').strip()
    if version_query:
        try:
            version_number = int(version_query)
        except ValueError:
            messages.error(request, 'Invalid record version requested.')
            return redirect('patient_record_detail', record_id=record_id)

    record, lab_request, detail_bundle, error = service_get_record_detail(
        record_id=record_id,
        hospital_id=str(meta.hospital_id),
        version_number=version_number,
    )
    if error:
        messages.error(request, error)
        return redirect('patient_lab_reports')

    return render(request, 'patient/record_detail.html', {
        'patient': patient,
        'patient_hospital_name': patient.registered_by.hospital_name if patient.registered_by else 'Self Registered',
        'record': record,
        'lab_request': lab_request,
        'audit': detail_bundle['audit'],
        'timeline': detail_bundle['timeline'],
        'custom_field_values': detail_bundle.get('custom_field_values', {}),
    })


@patient_required
def patient_record_history(request, record_id):
    patient_id = request.session.get('patient_id')
    patient = Patient.objects.filter(id=patient_id).first()

    if not patient:
        request.session.flush()
        return redirect('patient_login')

    meta = MedicalRecordMeta.objects.filter(record_id=record_id, patient_id=patient.id).first()
    if not meta:
        messages.error(request, 'Record history not found for your account.')
        return redirect('patient_lab_reports')

    history = service_get_record_history(
        record_id=record_id,
        hospital_id=str(meta.hospital_id),
    )
    return render(request, 'patient/record_history.html', {
        'patient': patient,
        'patient_hospital_name': patient.registered_by.hospital_name if patient.registered_by else 'Self Registered',
        'history': history,
        'record_id': record_id,
    })


@patient_required
def patient_profile(request):
    """Patient profile page to view and update personal information"""
    patient_id = request.session.get('patient_id')
    patient = Patient.objects.filter(id=patient_id).first()
    
    if not patient:
        request.session.flush()
        return redirect('patient_login')

    gov_id_is_locked = bool(patient.gov_id_type and patient.gov_id_number)
    gov_id_number_plain = ''
    if gov_id_is_locked:
        try:
            gov_id_number_plain = decrypt(patient.gov_id_number)
        except Exception:
            gov_id_number_plain = ''

    if request.method == 'POST':
        patient_updated, errors = service_patient_update_profile(
            patient_id=patient_id,
            full_name=request.POST.get('full_name', '').strip(),
            email=request.POST.get('email', '').strip(),
            phone=request.POST.get('phone', '').strip(),
            address=request.POST.get('address', '').strip(),
            gender=request.POST.get('gender', '').strip() or None,
            date_of_birth=request.POST.get('date_of_birth', '').strip() or None,
            blood_group=request.POST.get('blood_group', '').strip() or None,
            gov_id_type=request.POST.get('gov_id_type', '').strip(),
            gov_id_number=request.POST.get('gov_id_number', '').strip(),
        )

        if errors:
            messages.error(request, 'Failed to update profile. Please check the errors below.')
            missing_fields = get_missing_profile_fields(patient)
            return render(request, 'patient/profile.html', {
                'patient': patient,
                'patient_hospital_name': patient.registered_by.hospital_name if patient.registered_by else 'Self Registered',
                'errors': errors,
                'form_data': request.POST,
                'gov_id_is_locked': gov_id_is_locked,
                'gov_id_number_plain': gov_id_number_plain,
                'missing_fields': missing_fields,
                'profile_completion_percent': get_profile_completion_percent(patient),
                'profile_complete': len(missing_fields) == 0,
            })

        missing_after_save = get_missing_profile_fields(patient_updated)
        if missing_after_save:
            messages.warning(request, 'Profile saved, but some required fields are still missing to unlock records.')
            return redirect('patient_profile')

        messages.success(request, 'Profile completed successfully. Your account is now fully activated.')
        return redirect('patient_dashboard')

    missing_fields = get_missing_profile_fields(patient)
    return render(request, 'patient/profile.html', {
        'patient': patient,
        'patient_hospital_name': patient.registered_by.hospital_name if patient.registered_by else 'Self Registered',
        'gov_id_is_locked': gov_id_is_locked,
        'gov_id_number_plain': gov_id_number_plain,
        'missing_fields': missing_fields,
        'profile_completion_percent': get_profile_completion_percent(patient),
        'profile_complete': len(missing_fields) == 0,
    })


@patient_required
def patient_update_password(request):
    if request.method != 'POST':
        return redirect('patient_profile')

    success, error = service_patient_update_password(
        patient_id=request.session['patient_id'],
        current_password=request.POST.get('current_password', ''),
        new_password=request.POST.get('new_password', ''),
        confirm_password=request.POST.get('confirm_new_password', ''),
    )

    if error:
        messages.error(request, error)
        return redirect('patient_profile')

    messages.success(request, 'Password updated successfully.')
    return redirect('patient_profile')


@patient_required
def patient_logout(request):
    request.session.flush()
    return redirect('patient_login')
