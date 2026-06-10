from django.core.mail import send_mail


def _send(to_email, subject, body):
    send_mail(
        subject=subject,
        message=body,
        from_email=None,  # uses DEFAULT_FROM_EMAIL from settings
        recipient_list=[to_email],
        fail_silently=False,
    )


# ─── OTP Emails ───────────────────────────────────────────────────────────────

def send_verification_otp(hospital_name, email, otp):
    _send(
        email,
        "MediChain — Email Verification OTP",
        (
            f"Hello {hospital_name},\n\n"
            f"Your MediChain email verification OTP is:\n\n"
            f"{otp}\n\n"
            f"This OTP is valid for 10 minutes.\n"
            f"If you did not register, ignore this email.\n\n"
            f"— MediChain Team"
        )
    )


def send_resend_otp(hospital_name, email, otp):
    _send(
        email,
        "MediChain — New Verification OTP",
        (
            f"Hello {hospital_name},\n\n"
            f"Your new OTP is:\n\n"
            f"{otp}\n\n"
            f"Valid for 10 minutes.\n\n"
            f"— MediChain Team"
        )
    )


# ─── Staff Credential Emails ──────────────────────────────────────────────────

def send_doctor_credentials(full_name, email, hospital_name, temp_password):
    _send(
        email,
        "MediChain — Your Doctor Account Credentials",
        (
            f"Hello Dr. {full_name},\n\n"
            f"Your MediChain doctor account has been created by {hospital_name}.\n\n"
            f"Login Email   : {email}\n"
            f"Temp Password : {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"— MediChain Team"
        )
    )


def send_nurse_credentials(full_name, email, hospital_name, temp_password):
    _send(
        email,
        "MediChain — Your Nurse Account Credentials",
        (
            f"Hello {full_name},\n\n"
            f"Your MediChain nurse account has been created by {hospital_name}.\n\n"
            f"Login Email   : {email}\n"
            f"Temp Password : {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"— MediChain Team"
        )
    )


def send_technician_credentials(full_name, email, hospital_name, temp_password):
    _send(
        email,
        "MediChain — Your Technician Account Credentials",
        (
            f"Hello {full_name},\n\n"
            f"Your MediChain technician account has been created by {hospital_name}.\n\n"
            f"Login Email   : {email}\n"
            f"Temp Password : {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"— MediChain Team"
        )
    )


def send_patient_credentials(full_name, email, hospital_name, temp_password):
    _send(
        email,
        "MediChain — Your Patient Account Credentials",
        (
            f"Hello {full_name},\n\n"
            f"Your MediChain patient account has been created by {hospital_name}.\n\n"
            f"Login Email   : {email}\n"
            f"Temp Password : {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"— MediChain Team"
        )
    )


def send_patient_verification_otp(full_name, email, otp):
    _send(
        email,
        "MediChain — Verify Your Patient Account",
        (
            f"Hello {full_name},\n\n"
            f"Your MediChain patient verification OTP is:\n\n"
            f"{otp}\n\n"
            f"This OTP is valid for 10 minutes.\n"
            f"After verification, you can log in and complete your profile later.\n\n"
            f"— MediChain Team"
        )
    )