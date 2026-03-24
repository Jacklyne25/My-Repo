from django.urls import path
from .views import SysAdminDashboardView, UserManagementView, UserToggleStatusView, RoleManagementView

app_name = 'sysadmin'

urlpatterns = [
    path('dashboard/', SysAdminDashboardView.as_view(), name='dashboard'),
    path('users/', UserManagementView.as_view(), name='user_management'),
    path('users/<int:pk>/toggle/', UserToggleStatusView.as_view(), name='user_toggle_status'),
    path('users/<int:pk>/role/', RoleManagementView.as_view(), name='user_change_role'),
]
