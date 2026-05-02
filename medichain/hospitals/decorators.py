from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

from .models import Hospital


def hospital_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Basic session checks
        if 'hospital_id' not in request.session:
            return redirect('/')
        if request.session.get('staff_id'):  # staff member trying to access admin
            return redirect('/')

        # Check if hospital account is active
        try:
            hospital = Hospital.objects.get(id=request.session['hospital_id'])
        except Hospital.DoesNotExist:
            return redirect('/')

        # If account is not active, add warning but allow page to render
        if hospital.account_status != 'active':
            messages.warning(request, 'Complete your hospital profile to activate your account and perform actions.')
            # Pass flag to context so template can disable forms
            request.profile_incomplete = True
        else:
            request.profile_incomplete = False

        return view_func(request, *args, **kwargs)

    return wrapper


def doctor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'staff_id' not in request.session:
            return redirect('/')
        if request.session.get('staff_role') != 'doctor':
            return redirect('/')
        return view_func(request, *args, **kwargs)
    return wrapper


def nurse_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'staff_id' not in request.session:
            return redirect('/')
        if request.session.get('staff_role') != 'nurse':
            return redirect('/')
        return view_func(request, *args, **kwargs)
    return wrapper

def technician_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'staff_id' not in request.session:
            return redirect('/')
        if request.session.get('staff_role') != 'technician':
            return redirect('/')
        return view_func(request, *args, **kwargs)
    return wrapper