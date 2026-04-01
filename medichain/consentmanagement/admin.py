from django.contrib import admin
from .models import ConsentRequest


@admin.register(ConsentRequest)
class ConsentRequestAdmin(admin.ModelAdmin):
    list_display = (
        'consent_id',
        'patient_id',
        'requesting_hospital',
        'requested_to_hospital',
        'patient_choice',
        'hospital_choice',
        'request_status',
        'created_at',
    )

    list_filter = (
        'request_status',
        'patient_choice',
        'hospital_choice',
        'created_at',
    )

    search_fields = (
        'patient_id',
        'requesting_hospital',
        'requested_to_hospital',
        'consent_id',
    )

    readonly_fields = (
        'consent_id',
        'created_at',
        'updated_at',
    )

    ordering = ('-created_at',)

    fieldsets = (
        ('Basic Info', {
            'fields': (
                'consent_id',
                'patient_id',
                'record_id',
            )
        }),
        ('Hospitals', {
            'fields': (
                'requesting_hospital',
                'requested_to_hospital',
            )
        }),
        ('Decisions', {
            'fields': (
                'patient_choice',
                'hospital_choice',
                'request_status',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )