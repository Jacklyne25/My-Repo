from django.contrib import admin
from .models import AttendanceRecord

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'is_present')
    list_filter = ('is_present', 'session__date')
    search_fields = ('student__username', 'student__first_name', 'student__last_name', 'session__timetable_entry__course_unit__name')
