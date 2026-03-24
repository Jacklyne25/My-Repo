from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ('role', 'department', 'program', 'course_group')
    fieldsets = UserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role', 'department', 'program', 'course_group')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role Information', {'fields': ('role', 'department', 'program', 'course_group')}),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'role' in form.base_fields:
            if request.user.role == User.Role.SYSTEM_ADMIN:
                # SysAdmin can only create HODs and SysAdmins
                allowed = [User.Role.SYSTEM_ADMIN, User.Role.HOD]
                form.base_fields['role'].choices = [
                    c for c in User.Role.choices if c[0] in allowed
                ]
            elif request.user.role == User.Role.HOD:
                # HOD can create Coordinators, Lecturers, and Students
                allowed = [User.Role.COORDINATOR, User.Role.LECTURER, User.Role.STUDENT]
                form.base_fields['role'].choices = [
                    c for c in User.Role.choices if c[0] in allowed
                ]
                form.base_fields['role'].choices = [
                    c for c in User.Role.choices if c[0] in allowed
                ]
        return form

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.role == User.Role.SYSTEM_ADMIN:
            # SysAdmin sees everything? Or just governance users?
            # User requirement: "Oversee... user governance". implies broad view.
            return qs
        if request.user.role == User.Role.HOD:
            # HOD sees only their department
            return qs.filter(department=request.user.department)
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and request.user.role == User.Role.HOD:
            obj.department = request.user.department
        super().save_model(request, obj, form, change)
