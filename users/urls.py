from django.urls import path
from .views import (
    HODDashboardView, StudentDashboardView, CoordinatorDashboardView, TeachingStaffDashboardView, HomeView, 
    UserListView, ActivateAccountView, UserUpdateView, UserDeleteView, BulkUpdateUsersView,
    PasswordResetFirstLoginView, UserCreateView, RevokeActivationView
)

app_name = 'users'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('hod-dashboard/', HODDashboardView.as_view(), name='hod_dashboard'),
    path('student-dashboard/', StudentDashboardView.as_view(), name='student_dashboard'),
    path('coordinator-dashboard/', CoordinatorDashboardView.as_view(), name='coordinator_dashboard'),
    path('staff-dashboard/', TeachingStaffDashboardView.as_view(), name='teaching_staff_dashboard'),
    path('user-list/', UserListView.as_view(), name='user_list'),
    path('user-create/', UserCreateView.as_view(), name='user_create'),
    path('user-edit/<int:pk>/', UserUpdateView.as_view(), name='user_edit'),
    path('user-delete/<int:pk>/', UserDeleteView.as_view(), name='user_delete'),
    path('user-revoke-activation/<int:pk>/', RevokeActivationView.as_view(), name='user_revoke_activation'),
    path('bulk-promotion/', BulkUpdateUsersView.as_view(), name='bulk_update_users'),
    path('activate/', ActivateAccountView.as_view(), name='activate_account'),
    path('password-reset-first-login/', PasswordResetFirstLoginView.as_view(), name='password_reset_first_login'),
]
