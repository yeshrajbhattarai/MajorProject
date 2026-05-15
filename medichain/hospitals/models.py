
import uuid
from django.db import models
from django.utils import timezone

#####################################
class Hospital(models.Model):

    # ── Account Status Choices ──
    PENDING   = 'pending'
    ACTIVE    = 'active'
    SUSPENDED = 'suspended'

    STATUS_CHOICES = [
        (PENDING,   'Pending'),
        (ACTIVE,    'Active'),
        (SUSPENDED, 'Suspended'),
    ]

    # ── Phase 1 fields (filled at registration) ──
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital_name  = models.CharField(max_length=255)
    email          = models.EmailField(unique=True)
    password_hash  = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=10, unique=True)
    account_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    api_key        = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    # ── Phase 2 fields (filled after login to activate) ──
    license_number   = models.CharField(max_length=100, null=True, blank=True)
    license_document = models.FileField(upload_to='licenses/', null=True, blank=True)
    address          = models.TextField(null=True, blank=True)
    city             = models.CharField(max_length=100, null=True, blank=True)
    state            = models.CharField(max_length=100, null=True, blank=True)
    country          = models.CharField(max_length=100, null=True, blank=True)

    name_locked    = models.BooleanField(default=False)
    license_locked = models.BooleanField(default=False)
    email_verified          = models.BooleanField(default=False)
    email_verify_otp        = models.CharField(max_length=6, null=True, blank=True)
    email_verify_otp_expiry = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'hospitals'

    def __str__(self):
        return self.hospital_name


###################################
class HospitalUser(models.Model):

    ROLE_CHOICES = [
        ('doctor',      'Doctor'),
        ('nurse',       'Nurse'),
        ('technician',  'Technician'),   # ← was missing
    ]

    STATUS_CHOICES = [
        ('active',   'Active'),
        ('inactive', 'Inactive'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital       = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='staff')
    full_name      = models.CharField(max_length=255)
    email          = models.EmailField(unique=True)
    phone          = models.CharField(max_length=10, unique=True)
    employee_id    = models.CharField(max_length=50)
    role           = models.CharField(max_length=15, choices=ROLE_CHOICES)
    specialization = models.CharField(max_length=255, null=True, blank=True)
    password_hash  = models.CharField(max_length=255)
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_by     = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    # Staff fills these from their own profile page
    date_of_birth    = models.DateField(null=True, blank=True)
    gender           = models.CharField(max_length=10, null=True, blank=True)
    home_address     = models.TextField(null=True, blank=True)
    years_experience = models.PositiveIntegerField(null=True, blank=True)
    license_number   = models.CharField(max_length=100, null=True, blank=True)
    bio              = models.TextField(null=True, blank=True)
    profile_photo    = models.ImageField(upload_to='staff_photos/', null=True, blank=True)

    class Meta:
        db_table = 'hospital_users'

    def __str__(self):
        return f"{self.full_name} ({self.role})"

    @property
    def age(self):
        """Return age in years calculated from `date_of_birth`, or None."""
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        dob = self.date_of_birth
        years = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            years -= 1
        return years if years >= 0 else None


######################################
class Patient(models.Model):

    GOV_ID_CHOICES = [
        ('aadhar', 'Aadhar Card'),
        ('voter',  'Voter ID'),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gov_id_type   = models.CharField(max_length=10, choices=GOV_ID_CHOICES)
    gov_id_number = models.CharField(max_length=500)   # Fernet encrypted
    gov_id_hash   = models.CharField(max_length=64, unique=True)  # SHA-256 for dup check

    # Hospital fills at registration
    full_name  = models.CharField(max_length=255)
    gender     = models.CharField(max_length=10, null=True, blank=True)
    phone      = models.CharField(max_length=10, null=True, blank=True)
    email      = models.EmailField(null=True, blank=True)
    address    = models.TextField(null=True, blank=True)

    # Patient fills themselves (Phase 2 — planned)
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group   = models.CharField(max_length=5, null=True, blank=True)
    profile_photo = models.ImageField(upload_to='patient_photos/', null=True, blank=True)
    password_hash = models.CharField(max_length=255, null=True, blank=True)

    # Meta
    registered_by      = models.ForeignKey(
        Hospital, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='registered_patients'
    )
    registered_by_self = models.BooleanField(default=False)
    is_active          = models.BooleanField(default=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'patients'

    def __str__(self):
        return self.full_name

    @property
    def age(self):
        """Return age in years calculated from `date_of_birth`, or None."""
        if not self.date_of_birth:
            return None
        today = timezone.localdate()
        dob = self.date_of_birth
        years = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            years -= 1
        return years if years >= 0 else None


######################################
class PatientAssignment(models.Model):
    """
    Tracks which nurses and technicians are assigned to a patient.
    A patient can have multiple nurses and multiple technicians.
    Each assignment row = one staff member assigned to one patient.
    """

    ROLE_CHOICES = [
        ('nurse', 'Nurse'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient     = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='assignments'
    )
    staff       = models.ForeignKey(
        HospitalUser, on_delete=models.CASCADE, related_name='patient_assignments'
    )
    role        = models.CharField(max_length=15, choices=ROLE_CHOICES)
    assigned_by = models.ForeignKey(
        HospitalUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assignments_made'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'patient_assignments'
        # prevent duplicate — same staff cannot be assigned to same patient twice
        unique_together = ('patient', 'staff')

    def __str__(self):
        return f"{self.staff.full_name} → {self.patient.full_name} ({self.role})"


class Lab(models.Model):
    LAB_TYPE_CHOICES = [
        ('ckd', 'Chronic Kidney Disease'),
        ('pathology', 'Pathology'),
        ('radiology', 'Radiology'),
        ('cardiology', 'Cardiology'),
        ('microbiology', 'Microbiology'),
        ('biochemistry', 'Biochemistry'),
        ('hematology', 'Hematology'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='labs')
    lab_type = models.CharField(max_length=50, choices=LAB_TYPE_CHOICES)
    name = models.CharField(max_length=255)
    custom_field_schema = models.JSONField(default=list, blank=True, help_text='JSON list of extra fields for this lab.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'labs'
        unique_together = ('hospital', 'lab_type')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.hospital.hospital_name})"


class LabAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='assignments')
    technician = models.ForeignKey(HospitalUser, on_delete=models.CASCADE, related_name='lab_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lab_assignments'
        unique_together = ('lab', 'technician')
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.technician.full_name} -> {self.lab.name}"


class LabRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    CHEST_PAIN_CHOICES = [
        ('typical', 'Typical'),
        ('atypical', 'Atypical'),
        ('non_anginal', 'Non-anginal'),
        ('asymptomatic', 'Asymptomatic'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_requests')
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='requests')
    requested_by = models.ForeignKey(HospitalUser, on_delete=models.CASCADE, related_name='requested_lab_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    chest_pain_type = models.CharField(max_length=20, choices=CHEST_PAIN_CHOICES)
    diagnosis = models.TextField()
    treatment_plan = models.TextField()
    notes = models.TextField(null=True, blank=True)
    custom_field_values = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'lab_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.patient.full_name} - {self.lab.name} ({self.status})"


class LabRequestRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab_request = models.ForeignKey(LabRequest, on_delete=models.CASCADE, related_name='revisions')
    revised_by = models.ForeignKey(HospitalUser, on_delete=models.CASCADE, related_name='lab_request_revisions')
    changed_fields = models.JSONField(default=list, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lab_request_revisions'
        ordering = ['-created_at']

    def __str__(self):
        return f"Revision for {self.lab_request_id} by {self.revised_by.full_name}"


class MedicalRecordMeta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record_id = models.UUIDField(db_index=True)
    RECORD_TYPE_LAB = 'lab'
    RECORD_TYPE_MEDICAL = 'medical'
    RECORD_TYPE_CHOICES = [
        (RECORD_TYPE_LAB, 'Lab Record'),
        (RECORD_TYPE_MEDICAL, 'Medical Record'),
    ]

    record_type = models.CharField(max_length=16, choices=RECORD_TYPE_CHOICES, default=RECORD_TYPE_LAB, db_index=True)
    lab_request = models.ForeignKey(LabRequest, on_delete=models.CASCADE, related_name='record_meta', null=True, blank=True)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='record_meta')
    patient_id = models.UUIDField()
    recorded_by_id = models.UUIDField()
    sha256_hash = models.CharField(max_length=64)
    version = models.IntegerField(default=1)
    custom_field_values = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'medical_record_meta'
        unique_together = ('record_id', 'version')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.get_record_type_display()} {self.record_id} v{self.version}"


class NurseQueueItem(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='nurse_queue_items')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='nurse_queue_items')
    doctor = models.ForeignKey(HospitalUser, on_delete=models.CASCADE, related_name='nurse_queue_items_created')
    title = models.CharField(max_length=255)
    primary_diagnosis = models.CharField(max_length=255)
    key_instruction = models.TextField()
    doctor_note = models.TextField(null=True, blank=True)
    handwritten_file = models.FileField(upload_to='nurse_queue/', null=True, blank=True)
    blood_pressure = models.CharField(max_length=32, null=True, blank=True)
    pulse_rate = models.PositiveIntegerField(null=True, blank=True)
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    spo2_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    random_blood_sugar = models.CharField(max_length=32, null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Patient weight in kg (optional)")
    nurse_tests_performed = models.TextField(null=True, blank=True)
    nurse_observation = models.TextField(null=True, blank=True)
    treatment_given = models.TextField(null=True, blank=True)
    medications_administered = models.TextField(null=True, blank=True)
    follow_up_notes = models.TextField(null=True, blank=True)
    doctor_medical_record_file = models.FileField(upload_to='doctor_final_records/', null=True, blank=True)
    next_appointment_date = models.DateField(null=True, blank=True)
    closing_statement = models.TextField(null=True, blank=True)
    nurse_discharge_statement = models.TextField(null=True, blank=True)
    doctor_final_notes = models.TextField(null=True, blank=True)
    doctor_finalized = models.BooleanField(default=False)
    finalized_record_id = models.UUIDField(null=True, blank=True, unique=True)
    finalized_record_hash = models.CharField(max_length=64, null=True, blank=True)
    finalized_record_payload = models.JSONField(default=dict, blank=True)
    finalized_record_history = models.JSONField(default=list, blank=True)
    doctor_finalized_by = models.ForeignKey(HospitalUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctor_finalized_queue_items')
    doctor_finalized_at = models.DateTimeField(null=True, blank=True)
    # Fields to support doctor rejection and change-requests
    doctor_rejection_reason = models.TextField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(HospitalUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='nurse_queue_items_rejected')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    picked_by = models.ForeignKey(HospitalUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='nurse_queue_items_picked')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'nurse_queue_items'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.patient.full_name}"
