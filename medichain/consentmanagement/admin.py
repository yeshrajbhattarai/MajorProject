from django.contrib import admin
from .models import ConsentRequest


@admin.register(ConsentRequest)
class ConsentRequestAdmin(admin.ModelAdmin):
    list_display  = ('consent_id', 'patient_id', 'requesting_hospital', 'requested_to_hospital', 'request_status', 'created_at')
    list_filter   = ('request_status', 'patient_choice', 'hospital_choice')
    search_fields = ('patient_id', 'requesting_hospital', 'requested_to_hospital')
    readonly_fields = ('consent_id', 'created_at', 'updated_at')
    ordering      = ('-created_at',)