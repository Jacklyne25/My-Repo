from django.views.generic import TemplateView, ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from users.models import User
from academic.models import Department
from .models import AuditLog, GlobalSettings

from django.core.exceptions import PermissionDenied

class SysAdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_sysadmin()

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()

class SysAdminDashboardView(SysAdminRequiredMixin, TemplateView):
    template_name = 'sysadmin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.count()
        context['total_depts'] = Department.objects.count()
        context['recent_audit_logs'] = AuditLog.objects.order_by('-timestamp')[:10]
        context['system_settings'] = GlobalSettings.objects.first()
        return context

class UserManagementView(SysAdminRequiredMixin, ListView):
    model = User
    template_name = 'sysadmin/user_management.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        return User.objects.all().order_by('-date_joined')

class UserToggleStatusView(SysAdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            messages.error(request, "You cannot deactivate yourself!")
        else:
            user.is_active = not user.is_active
            user.save()
            action = "activated" if user.is_active else "deactivated"
            AuditLog.objects.create(
                actor=request.user,
                action=f"User {action}",
                target=user
            )
            messages.success(request, f"User {user.username} has been {action}.")
        return redirect('sysadmin:user_management')

class RoleManagementView(SysAdminRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        new_role = request.POST.get('role')
        if new_role in User.Role.values:
            old_role = user.role
            user.role = new_role
            user.save()
            AuditLog.objects.create(
                actor=request.user,
                action=f"Role changed from {old_role} to {new_role}",
                target=user
            )
            messages.success(request, f"Updated role for {user.username} to {user.get_role_display()}.")
        else:
            messages.error(request, "Invalid role selected.")
        return redirect('sysadmin:user_management')
