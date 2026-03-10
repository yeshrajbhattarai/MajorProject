import re
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password, check_password
from .models import Hospital


def hospital_register(request):
    if request.method != 'POST':
        return render(request, 'hospitals/register.html')

    # ── Read POST data ──
    hospital_name    = request.POST.get('hospital_name', '').strip()
    email            = request.POST.get('email', '').strip().lower()
    contact_number   = request.POST.get('contact_number', '').strip()
    password         = request.POST.get('password', '')
    confirm_password = request.POST.get('confirm_password', '')

    errors = {}

    # ── Hospital name ──
    if not hospital_name:
        errors['hospital_name'] = 'Hospital name is required'

    # ── Email: format → duplicate check ──
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$'
    if not email:
        errors['email'] = 'Email is required'
    elif not re.match(email_regex, email):
        errors['email'] = 'Enter a valid email address'
    elif Hospital.objects.filter(email=email).exists():
        errors['email'] = 'This email is already registered'

    # ── Phone: Indian mobile format → duplicate check ──
    india_mobile_regex = r'^[6-9]\d{9}$'
    if not contact_number:
        errors['contact_number'] = 'Contact number is required'
    elif not re.match(india_mobile_regex, contact_number):
        errors['contact_number'] = 'Enter a valid 10-digit Indian mobile number'
    elif Hospital.objects.filter(contact_number=contact_number).exists():
        errors['contact_number'] = 'This contact number is already registered'

    # ── Password: min length ──
    if not password:
        errors['password'] = 'Password is required'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters'

    # ── Confirm password: must match ──
    if not confirm_password:
        errors['confirm_password'] = 'Please confirm your password'
    elif password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match'

    # ── Return errors as JSON (AJAX — no page reload) ──
    if errors:
        return JsonResponse({'success': False, 'errors': errors})

    # ── Save to DB — password hashed with PBKDF2 by default ──
    Hospital.objects.create(
        hospital_name  = hospital_name,
        email          = email,
        contact_number = contact_number,
        password_hash  = make_password(password),
    )

    # ── Success — tell JS to redirect to login panel ──
    return JsonResponse({'success': True, 'redirect': '/?mode=login'})


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

    # ── Redirect: pending goes to profile setup, active goes to dashboard ──
    if hospital.account_status == 'pending':
        return JsonResponse({'success': True, 'redirect': '/profile/complete/'})

    return JsonResponse({'success': True, 'redirect': '/dashboard/'})
