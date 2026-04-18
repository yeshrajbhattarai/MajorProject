from functools import wraps

from django.shortcuts import redirect


def patient_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.session.get('user_type') != 'patient' or not request.session.get('patient_id'):
            return redirect('patient_login')
        return view_func(request, *args, **kwargs)

    return _wrapped
