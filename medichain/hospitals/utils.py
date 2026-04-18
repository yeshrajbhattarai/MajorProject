import string
import secrets
from django.contrib.auth.hashers import check_password, make_password


# ─── Password Helpers ─────────────────────────────────────────────────────────

# generate a random 12-character temporary password for new staff accounts
def generate_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def update_password_with_verification(instance, current_password, new_password, confirm_password, password_field='password_hash'):
    """
    Shared password update helper used by hospital and patient services.
    Returns (success, error_message).
    """
    existing_hash = getattr(instance, password_field, '') or ''

    if not check_password(current_password or '', existing_hash):
        return False, 'Current password is incorrect.'

    if len(new_password or '') < 8:
        return False, 'New password must be at least 8 characters.'

    if (new_password or '') != (confirm_password or ''):
        return False, 'New passwords do not match.'

    setattr(instance, password_field, make_password(new_password))

    update_fields = [password_field]
    if hasattr(instance, 'updated_at'):
        update_fields.append('updated_at')
    instance.save(update_fields=update_fields)

    return True, None


# ─── Hospital Activation ──────────────────────────────────────────────────────

# auto-activate hospital when license is locked and address is fully filled
# used in session-based views — also updates session status
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


# same activation logic but without session — used in services.py and API views
def check_and_activate_without_session(hospital):
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
