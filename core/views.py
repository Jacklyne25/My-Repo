from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from users.models import User
from .models import Alert
from .forms import HODAnnouncementForm, CoordinatorAnnouncementForm, LecturerAnnouncementForm
from .services import AlertService

class NotificationsListView(LoginRequiredMixin, ListView):
    model = Alert
    template_name = 'core/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 15

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user).order_by('-created_at')

class MarkAlertReadView(LoginRequiredMixin, View):
    def post(self, request, alert_id):
        alert = get_object_or_404(Alert, id=alert_id, user=request.user)
        alert.is_read = True
        alert.save()
        return redirect('core:notifications')

class MarkAllAlertsReadView(LoginRequiredMixin, View):
    def post(self, request):
        Alert.objects.filter(user=request.user, is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        
        # Support redirecting back to the page that triggered the action
        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('core:notifications')

class CreateAnnouncementView(LoginRequiredMixin, View):
    template_name = 'core/create_announcement.html'

    def dispatch(self, request, *args, **kwargs):
        # Only roles that can send announcements are allowed
        if request.user.role not in [User.Role.HOD, User.Role.COORDINATOR, User.Role.LECTURER]:
            messages.error(request, "You do not have permission to send announcements.")
            if getattr(request.user, 'role', None) == User.Role.STUDENT:
                return redirect('users:student_dashboard')
            return redirect('users:home')
        return super().dispatch(request, *args, **kwargs)

    def get_form(self):
        user = self.request.user
        if user.role == User.Role.HOD:
            return HODAnnouncementForm(self.request.POST or None)
        elif user.role == User.Role.COORDINATOR:
            return CoordinatorAnnouncementForm(self.request.POST or None, department=user.department)
        elif user.role == User.Role.LECTURER:
            return LecturerAnnouncementForm(self.request.POST or None, lecturer=user)
        return None

    def get(self, request):
        form = self.get_form()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = self.get_form()
        user = request.user
        
        if form and form.is_valid():
            message = form.cleaned_data['message']
            sent_count = 0
            
            if user.role == User.Role.HOD:
                target_group = form.cleaned_data['target_group']
                sent_count = AlertService.send_announcement(
                    sender=user, 
                    target_group=target_group, 
                    message=message, 
                    department=user.department
                )
            
            elif user.role == User.Role.COORDINATOR:
                target_type = form.cleaned_data['target_type']
                target_program = form.cleaned_data['target_program']
                
                if target_type == 'MANAGED_GROUPS':
                    sent_count = AlertService.send_announcement(
                        sender=user,
                        target_group='MANAGED_GROUPS',
                        message=message
                    )
                else:
                    sent_count = AlertService.send_announcement(
                        sender=user,
                        target_group='PROGRAM',
                        message=message,
                        program=target_program
                    )
                
            elif user.role == User.Role.LECTURER:
                target_course_unit = form.cleaned_data['target_course_unit']
                sent_count = AlertService.send_announcement(
                    sender=user,
                    target_group='COURSE_UNIT',
                    message=message,
                    course_unit=target_course_unit
                )

            messages.success(request, f"Announcement sent to {sent_count} user(s).")
            # Redirect to home, which will route to the appropriate dashboard
            return redirect('users:home')
            
        return render(request, self.template_name, {'form': form})
