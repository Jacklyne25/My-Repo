from django.contrib import admin
from .models import Department, Program, CourseUnit

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

    def has_add_permission(self, request):
        # Only System Admin or Superuser can add departments
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'role') and request.user.role == 'SYSTEM_ADMIN'

    def has_change_permission(self, request, obj=None):
        # SysAdmin or HOD (for their own dept) can change
        if request.user.is_superuser:
            return True
        if hasattr(request.user, 'role'):
            if request.user.role == 'SYSTEM_ADMIN':
                return True
            if request.user.role == 'HOD':
                # HOD can edit, but queryset will limit to their own
                return True
        return False

    def has_delete_permission(self, request, obj=None):
        # Only System Admin or Superuser can delete
        if request.user.is_superuser:
            return True
        return hasattr(request.user, 'role') and request.user.role == 'SYSTEM_ADMIN'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'role'):
            if request.user.role == 'SYSTEM_ADMIN':
                return qs
            if request.user.role == 'HOD':
                # HOD only sees their own department
                return qs.filter(id=request.user.department_id)
        return qs.none()

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department')
    list_filter = ('department',)
    search_fields = ('name', 'code')

@admin.register(CourseUnit)
class CourseUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'course_category', 'is_active')
    list_filter = ('is_active', 'course_category', 'programs')
    search_fields = ('name', 'code')
    filter_horizontal = ('programs',)
