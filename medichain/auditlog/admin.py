from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ('action', 'severity', 'performed_by', 'consent_id', 'timestamp')
    list_filter   = ('severity', 'action')
    search_fields = ('performed_by', 'action', 'consent_id', 'extra_info')
    readonly_fields = ('log_id', 'action', 'severity', 'performed_by', 'consent_id', 'scope_hospitals', 'extra_info', 'timestamp')
    ordering      = ('-timestamp',)

    # prevent anyone from adding or deleting logs through admin
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False