from functools import wraps
from django.shortcuts import redirect


def hospital_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if 'hospital_id' not in request.session:
            return redirect('/')
        if request.session.get('staff_id'):  # staff member trying to access admin
            return redirect('/')
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