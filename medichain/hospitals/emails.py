from django.core.mail import send_mail


# ─── OTP Emails ───────────────────────────────────────────────────────────────

# send verification OTP during hospital registration
def send_verification_otp(hospital_name, email, otp):
    send_mail(
        subject        = 'MediChain — Email Verification OTP',
        message        = (
            f"Hello {hospital_name},\n\n"
            f"Your MediChain email verification OTP is:\n\n"
            f"{otp}\n\n"
            f"This OTP is valid for 10 minutes.\n"
            f"If you did not register, ignore this email.\n\n"
            f"— MediChain Team"
        ),
        from_email     = None,
        recipient_list = [email],
        fail_silently  = False,
    )


# send a fresh OTP when the user requests resend
def send_resend_otp(hospital_name, email, otp):
    send_mail(
        subject        = 'MediChain — New Verification OTP',
        message        = (
            f"Hello {hospital_name},\n\n"
            f"Your new OTP is:\n\n"
            f"{otp}\n\n"
            f"Valid for 10 minutes.\n\n"
            f"— MediChain Team"
        ),
        from_email     = None,
        recipient_list = [email],
        fail_silently  = False,
    )


# ─── Staff Credential Emails ──────────────────────────────────────────────────

# send login credentials to a newly created doctor
def send_doctor_credentials(full_name, email, hospital_name, temp_password):
    send_mail(
        subject        = 'MediChain — Your Doctor Account Credentials',
        message        = (
            f"Hello Dr. {full_name},\n\n"
            f"Your MediChain doctor account has been created by {hospital_name}.\n\n"
            f"Login Email   : {email}\n"
            f"Temp Password : {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"— MediChain Team"
        ),
        from_email     = None,
        recipient_list = [email],
        fail_silently  = False,
    )


# send login credentials to a newly created nurse
def send_nurse_credentials(full_name, email, hospital_name, temp_password):
    send_mail(
        subject        = 'MediChain — Your Nurse Account Credentials',
        message        = (
            f"Hello {full_name},\n\n"
            f"Your MediChain nurse account has been created by {hospital_name}.\n\n"
            f"Login Email   : {email}\n"
            f"Temp Password : {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"— MediChain Team"
        ),
        from_email     = None,
        recipient_list = [email],
        fail_silently  = False,
    )

# send login credentials to a newly created technician
def send_technician_credentials(full_name, email, hospital_name, temp_password):
    send_mail(
        subject        = 'MediChain — Your Technician Account Credentials',
        message        = (
            f"Hello {full_name},\n\n"
            f"Your MediChain technician account has been created by {hospital_name}.\n\n"
            f"Login Email   : {email}\n"
            f"Temp Password : {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"— MediChain Team"
        ),
        from_email     = None,
        recipient_list = [email],
        fail_silently  = False,
    )


def send_patient_credentials(full_name, email, hospital_name, temp_password):
    send_mail(
        subject='MediChain - Your Patient Account Credentials',
        message=(
            f"Hello {full_name},\n\n"
            f"Your MediChain patient account has been created by {hospital_name}.\n\n"
            f"Login Email   : {email}\n"
            f"Temp Password : {temp_password}\n\n"
            f"Please log in and change your password immediately.\n\n"
            f"- MediChain Team"
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )


def send_patient_verification_otp(full_name, email, otp):
    send_mail(
        subject='MediChain — Verify Your Patient Account',
        message=(
            f"Hello {full_name},\n\n"
            f"Your MediChain patient verification OTP is:\n\n"
            f"{otp}\n\n"
            f"This OTP is valid for 10 minutes.\n"
            f"After verification, you can log in and complete your profile later.\n\n"
            f"- MediChain Team"
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )
