from django.contrib import admin
from .models import GlobalSettings, AuditLog

@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    # Only allow one instance effectively, but standard admin works for now.
    list_display = ('attendance_threshold', 'semester_start', 'semester_end')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'actor', 'action', 'target')
    list_filter = ('action', 'timestamp')
    search_fields = ('actor__username', 'action', 'object_id')
    readonly_fields = ('timestamp', 'actor', 'action', 'target', 'metadata', 'content_type', 'object_id')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
