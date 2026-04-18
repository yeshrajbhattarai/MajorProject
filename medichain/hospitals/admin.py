from django.contrib import admin
from .models import (
    Hospital,
    HospitalUser,
    Patient,
    PatientAssignment,
    Lab,
    LabAssignment,
    LabRequest,
    LabRequestRevision,
    MedicalRecordMeta
)


# ─────────────────────────────────────────────────────────────
# 🏥 Hospital Admin
# ─────────────────────────────────────────────────────────────
@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = (
        'hospital_name',
        'email',
        'contact_number',
        'account_status',
        'email_verified',
        'created_at',
    )

    list_filter = (
        'account_status',
        'email_verified',
        'created_at',
    )

    search_fields = (
        'hospital_name',
        'email',
        'contact_number',
    )

    readonly_fields = (
        'id',
        'api_key',
        'created_at',
        'updated_at',
    )

    ordering = ('-created_at',)


# ─────────────────────────────────────────────────────────────
# 👨‍⚕️ Hospital User Admin
# ─────────────────────────────────────────────────────────────
@admin.register(HospitalUser)
class HospitalUserAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'email',
        'hospital',
        'role',
        'status',
        'created_at',
    )

    list_filter = (
        'role',
        'status',
        'hospital',
    )

    search_fields = (
        'full_name',
        'email',
        'employee_id',
    )

    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
    )

    ordering = ('-created_at',)


# ─────────────────────────────────────────────────────────────
# 🧑 Patient Admin
# ─────────────────────────────────────────────────────────────
@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'gov_id_type',
        'registered_by',
        'is_active',
        'created_at',
    )

    list_filter = (
        'gov_id_type',
        'is_active',
        'registered_by',
    )

    search_fields = (
        'full_name',
        'phone',
        'email',
    )

    readonly_fields = (
        'id',
        'gov_id_hash',
        'created_at',
        'updated_at',
    )

    ordering = ('-created_at',)


# ─────────────────────────────────────────────────────────────
# 🔗 Patient Assignment
# ─────────────────────────────────────────────────────────────
@admin.register(PatientAssignment)
class PatientAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'patient',
        'staff',
        'role',
        'assigned_by',
        'assigned_at',
    )

    list_filter = (
        'role',
        'assigned_at',
    )

    search_fields = (
        'patient__full_name',
        'staff__full_name',
    )

    ordering = ('-assigned_at',)


# ─────────────────────────────────────────────────────────────
# 🧪 Lab Admin
# ─────────────────────────────────────────────────────────────
@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'hospital',
        'lab_type',
        'is_active',
        'created_at',
    )

    list_filter = (
        'lab_type',
        'hospital',
        'is_active',
    )

    search_fields = (
        'name',
        'hospital__hospital_name',
    )

    fieldsets = (
        (None, {
            'fields': ('hospital', 'lab_type', 'name', 'is_active', 'custom_field_schema'),
        }),
    )

    ordering = ('name',)


# ─────────────────────────────────────────────────────────────
# 🧑‍🔬 Lab Assignment
# ─────────────────────────────────────────────────────────────
@admin.register(LabAssignment)
class LabAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'lab',
        'technician',
        'assigned_at',
    )

    list_filter = (
        'lab',
    )

    search_fields = (
        'technician__full_name',
        'lab__name',
    )

    ordering = ('-assigned_at',)


# ─────────────────────────────────────────────────────────────
# 📋 Lab Request
# ─────────────────────────────────────────────────────────────
@admin.register(LabRequest)
class LabRequestAdmin(admin.ModelAdmin):
    list_display = (
        'patient',
        'lab',
        'requested_by',
        'status',
        'created_at',
    )

    list_filter = (
        'status',
        'lab',
    )

    search_fields = (
        'patient__full_name',
        'requested_by__full_name',
    )

    readonly_fields = ('custom_field_values',)

    ordering = ('-created_at',)


# ─────────────────────────────────────────────────────────────
# 🔁 Lab Request Revision
# ─────────────────────────────────────────────────────────────
@admin.register(LabRequestRevision)
class LabRequestRevisionAdmin(admin.ModelAdmin):
    list_display = (
        'lab_request',
        'revised_by',
        'created_at',
    )

    search_fields = (
        'lab_request__id',
        'revised_by__full_name',
    )

    ordering = ('-created_at',)


# ─────────────────────────────────────────────────────────────
# 📄 Medical Record Meta
# ─────────────────────────────────────────────────────────────
@admin.register(MedicalRecordMeta)
class MedicalRecordMetaAdmin(admin.ModelAdmin):
    list_display = (
        'record_id',
        'hospital',
        'version',
        'created_at',
    )

    list_filter = (
        'hospital',
    )

    readonly_fields = (
        'record_id',
        'sha256_hash',
        'custom_field_values',
        'created_at',
        'updated_at',
    )

    ordering = ('-updated_at',)