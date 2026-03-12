import string
import secrets


# ─── Password Helpers ─────────────────────────────────────────────────────────

# generate a random 12-character temporary password for new staff accounts
def generate_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ─── Hospital Activation ──────────────────────────────────────────────────────

# auto-activate hospital when license is locked and address is fully filled
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
