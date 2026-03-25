from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Avg, Count, Case, When, FloatField
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from .mixins import RoleRequiredMixin
from django.utils import timezone
from .models import User, LecturerProfile
from .forms import AccountActivationForm, DepartmentUserEditForm, UserCreateForm
from academic.models import CourseUnit
from scheduling.models import LectureSession, TimetableEntry, SchedulingParameters
from attendance.models import AttendanceRecord
from core.utils import ratelimit
from core.rules import check_unsubmitted_attendance
from core.models import Alert
from sysadmin.models import AuditLog

class WelcomeView(View):
    template_name = 'users/welcome.html'

    def get(self, request):
        if request.user.is_authenticated:
            # Re-use HomeView logic for authenticated users
            if request.user.role == User.Role.SYSTEM_ADMIN:
                return redirect('sysadmin:dashboard')
            elif request.user.role == User.Role.FACULTY_ADMIN:
                return redirect('academic:faculty_dashboard')
            elif request.user.role == User.Role.HOD:
                return redirect('users:hod_dashboard')
            elif request.user.role == User.Role.COORDINATOR:
                return redirect('users:coordinator_dashboard')
            elif request.user.role == User.Role.LECTURER:
                return redirect('users:teaching_staff_dashboard')
            elif request.user.role == User.Role.STUDENT:
                return redirect('users:student_dashboard')
        return render(request, self.template_name)

class ActivateAccountView(View):
    template_name = 'users/activate_account.html'

    def get(self, request):
        form = AccountActivationForm()
        context = {'form': form}
        
        # If HOD is logged in, show pending activations for their department
        if request.user.is_authenticated and request.user.role == User.Role.HOD:
            context['pending_users'] = User.objects.filter(
                department=request.user.department,
                account_status=User.AccountStatus.NOT_ACTIVATED
            ).order_by('-date_joined')
            
        return render(request, self.template_name, context)

    @method_decorator(ratelimit(key_prefix='activation', limit=5, period=3600))
    def post(self, request):
        # Handle HOD Quick Activation
        if request.user.is_authenticated and request.user.role == User.Role.HOD:
            action = request.POST.get('action')
            if action == 'quick_activate':
                user_id = request.POST.get('user_id')
                target_user = get_object_or_404(User, id=user_id, department=request.user.department)
                
                # Perform Quick Activation
                target_user.set_password('welcome@DSAMS')
                target_user.is_active = True
                target_user.account_status = User.AccountStatus.ACTIVE
                target_user.requires_password_reset = True
                target_user.save()
                
                messages.success(request, f"Account for {target_user.username} activated. They will be prompted to change their password on first login.")
                return redirect('users:activate_account')

        # Handle Standard Self-Activation
        form = AccountActivationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']

            user = User.objects.filter(username__iexact=username).first()

            if user:
                if user.account_status == User.AccountStatus.ACTIVE:
                    messages.info(request, "Your account is already active. Please sign in.")
                    return redirect('login')
                
                # Activate user with temp password for transition
                user.set_password('DSAMS@initial')
                user.is_active = True
                user.account_status = User.AccountStatus.ACTIVE
                user.requires_password_reset = True 
                user.save()

                AuditLog.objects.create(
                    actor=user,
                    action="Account Activated (Streamlined Flow)",
                    target=user,
                    metadata={'ip_address': request.META.get('REMOTE_ADDR')}
                )

                # Automatic Login for seamless transition to password reset
                from django.contrib.auth import login
                login(request, user)

                messages.success(request, "Identity verified! Please set your new secure password to complete your account setup.")
                return redirect('users:home')
            else:
                messages.error(request, "User not found. Please ensure you enter the correct Registration No / Staff ID.")

        return render(request, self.template_name, {'form': form})

class PasswordResetFirstLoginView(LoginRequiredMixin, View):
    template_name = 'users/password_reset_first_login.html'

    def get(self, request):
        if not request.user.requires_password_reset:
            return redirect('users:home')
        return render(request, self.template_name)

    def post(self, request):
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if not password or password != confirm_password:
            messages.error(request, "Passwords do not match or are empty.")
            return render(request, self.template_name)

        # Update password and clear flag
        user = request.user
        user.set_password(password)
        user.requires_password_reset = False
        user.save()
        
        # Re-login the user since setting password logs them out
        from django.contrib.auth import login
        login(request, user)
        
        messages.success(request, "Password updated successfully.")
        return redirect('users:home')

class HODDashboardView(RoleRequiredMixin, View):
    allowed_roles = [User.Role.HOD]
    
    def get(self, request):
        department = request.user.department
        context = {}
        
        if department:
            today = timezone.now().date()
            # Statistics
            context['total_lecturers'] = User.objects.filter(
                department=department, role=User.Role.LECTURER
            ).count()
            context['total_students'] = User.objects.filter(
                department=department, role=User.Role.STUDENT
            ).count()
            context['total_courses'] = CourseUnit.objects.filter(
                programs__department=department
            ).distinct().count()
            context['active_classes_today'] = LectureSession.objects.filter(
                date=today,
                timetable_entry__course_unit__programs__department=department
            ).distinct().count()

            # Today's Schedule Widget
            context['today_sessions'] = LectureSession.objects.filter(
                date=today,
                timetable_entry__course_unit__programs__department=department
            ).select_related(
                'timetable_entry__course_unit',
                'timetable_entry__lecturer',
                'timetable_entry__room'
            ).order_by('timetable_entry__start_time')

            # Attendance Today Summary
            attendance_sessions = context['today_sessions']
            context['recorded_lectures'] = attendance_sessions.filter(
                status__in=[
                    LectureSession.Status.CONDUCTED,
                    LectureSession.Status.SUBMITTED,
                    LectureSession.Status.APPROVED
                ]
            ).count()
            context['pending_attendance'] = attendance_sessions.filter(
                status=LectureSession.Status.SCHEDULED
            ).count()

            # Calculate average attendance rate
            total_students_present = AttendanceRecord.objects.filter(
                session__in=attendance_sessions,
                is_present=True
            ).count()
            total_records = AttendanceRecord.objects.filter(
                session__in=attendance_sessions
            ).count()

            if total_records > 0:
                context['avg_attendance_rate'] = round((total_students_present / total_records) * 100, 1)
            else:
                context['avg_attendance_rate'] = 0

            # Run compliance checks
            check_unsubmitted_attendance(department)
            
            # Fetch Latest Unread Alerts for HOD
            context['hod_alerts'] = Alert.objects.filter(
                user=request.user, is_read=False
            ).order_by('-created_at')[:5]

            # Monitoring Metrics
            past_sessions = LectureSession.objects.filter(
                date__lt=today,
                timetable_entry__course_unit__programs__department=department
            )
            context['missed_sessions_count'] = past_sessions.filter(status=LectureSession.Status.SCHEDULED).count()
            context['conducted_sessions_total'] = past_sessions.filter(status__in=[LectureSession.Status.CONDUCTED, LectureSession.Status.SUBMITTED, LectureSession.Status.APPROVED]).count()
            total_past = past_sessions.count()
            context['completion_rate'] = round((context['conducted_sessions_total'] / total_past * 100), 1) if total_past > 0 else 100
            
        return render(request, 'users/hod_dashboard.html', context)

class UserListView(RoleRequiredMixin, View):
    allowed_roles = [User.Role.HOD]

    def get(self, request):
        department = request.user.department
        if not department:
            return render(request, 'users/user_list.html', {
                'error': 'You are not assigned to any department.'
            })

        # Filter parameters
        program_id = request.GET.get('program')
        group_id = request.GET.get('group')

        users = User.objects.filter(department=department)
        
        # Apply filters ONLY to students
        students = users.filter(role=User.Role.STUDENT)
        if program_id:
            students = students.filter(program_id=program_id)
        if group_id:
            students = students.filter(course_group_id=group_id)

        # Context for filters
        from academic.models import Program, CourseGroup
        programs = Program.objects.filter(department=department)
        groups = CourseGroup.objects.filter(program__department=department)

        context = {
            'students': students,
            'lecturers': users.filter(role=User.Role.LECTURER),
            'coordinators': users.filter(role=User.Role.COORDINATOR),
            'department': department,
            'programs': programs,
            'groups': groups,
            'selected_program': int(program_id) if program_id and program_id.isdigit() else None,
            'selected_group': int(group_id) if group_id and group_id.isdigit() else None,
        }
        return render(request, 'users/user_list.html', context)
    
class UserCreateView(RoleRequiredMixin, View):
    allowed_roles = [User.Role.HOD]
    template_name = 'users/user_form.html'

    def get(self, request):
        form = UserCreateForm()
        # Pre-set department if needed, though it's handled in post()
        return render(request, self.template_name, {'form': form, 'is_create': True})

    def post(self, request):
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.department = request.user.department
            user.set_password('welcome@DSAMS') # Default password for manual creation
            user.account_status = User.AccountStatus.NOT_ACTIVATED
            user.requires_password_reset = True
            user.is_active = True # Allow login for activation
            user.save()
            
            # Save role-specific profile data if role is LECTURER
            if user.role == User.Role.LECTURER:
                employment_type = form.cleaned_data.get('employment_type')
                min_weekly_load = form.cleaned_data.get('min_weekly_load') or 16
                max_weekly_load = form.cleaned_data.get('max_weekly_load') or 20
                specialization = form.cleaned_data.get('specialization')
                
                LecturerProfile.objects.create(
                    user=user,
                    employment_type=employment_type,
                    min_weekly_load=min_weekly_load,
                    max_weekly_load=max_weekly_load,
                    specialization=specialization
                )
            
            messages.success(request, f"User {user.username} created successfully. Default password: welcome@DSAMS")
            return redirect('users:user_list')
            
        return render(request, self.template_name, {'form': form, 'is_create': True})

class UserUpdateView(RoleRequiredMixin, View):
    allowed_roles = [User.Role.HOD]
    template_name = 'users/user_form.html'

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        
        # Ensure HOD can only edit users in their own department
        if user.department != request.user.department:
            messages.error(request, "You can only edit users within your department.")
            return redirect('users:user_list')
            
        form = DepartmentUserEditForm(instance=user)
        return render(request, self.template_name, {'form': form, 'target_user': user})

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        
        # Ensure HOD can only edit users in their own department
        if user.department != request.user.department:
            messages.error(request, "You can only edit users within your department.")
            return redirect('users:user_list')
        
        old_role = user.role
        form = DepartmentUserEditForm(request.POST, instance=user)
        
        if form.is_valid():
            user = form.save()
            
            # Handle profile creation/update if role changed to LECTURER
            if user.role == User.Role.LECTURER:
                employment_type = form.cleaned_data.get('employment_type')
                min_weekly_load = form.cleaned_data.get('min_weekly_load')
                max_weekly_load = form.cleaned_data.get('max_weekly_load')
                specialization = form.cleaned_data.get('specialization')
                
                LecturerProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        'employment_type': employment_type,
                        'min_weekly_load': min_weekly_load,
                        'max_weekly_load': max_weekly_load,
                        'specialization': specialization
                    }
                )
            elif old_role == User.Role.LECTURER and user.role != User.Role.LECTURER:
                # Optional: Handle removal of profile if role is no longer LECTURER?
                # For now we'll keep it to avoid data loss, but maybe mark as inactive.
                pass
                
            messages.success(request, f"User {user.username} updated successfully.")
            return redirect('users:user_list')
            
        return render(request, self.template_name, {'form': form, 'target_user': user})


class StudentDashboardView(RoleRequiredMixin, View):
    allowed_roles = [User.Role.STUDENT]
    template_name = 'users/student_dashboard.html'
    
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        # 1. Fetch Unread Alerts
        alerts = Alert.objects.filter(user=user, is_read=False).order_by('-created_at')[:5]
        
        # 2. Fetch Weekly Timetable
        from scheduling.models import SchedulingParameters, TimetableEntry, LectureSession
        params = SchedulingParameters.objects.filter(department=user.department, is_active=True).first()
        
        grid = []
        days = [('MON', 'Monday'), ('TUE', 'Tuesday'), ('WED', 'Wednesday'), ('THU', 'Thursday'), ('FRI', 'Friday')]
        
        if params and user.department and user.program:
            slots = params.get_timeslots()
            entries = TimetableEntry.objects.filter(
                program=user.program
            ).select_related('course_unit', 'room')
            
            for start, end in slots:
                row = {'time': f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}", 'slots': []}
                for day_code, day_name in days:
                    entry = entries.filter(day_of_week=day_code, start_time=start).first()
                    row['slots'].append(entry)
                grid.append(row)

        # 3. Today's Sessions
        today_sessions = LectureSession.objects.filter(
            date=today,
            timetable_entry__program=user.program
        ).select_related('timetable_entry__course_unit', 'timetable_entry__room', 'timetable_entry__lecturer').order_by('timetable_entry__start_time') if user.program else []

        # 4. Attendance Summary
        from attendance.models import AttendanceRecord
        attendance_records = AttendanceRecord.objects.filter(student=user).select_related('session__timetable_entry__course_unit')
        
        # Group attendance by course
        course_attendance = []
        courses = attendance_records.values('session__timetable_entry__course_unit__code', 'session__timetable_entry__course_unit__name').annotate(
            total=Count('id'),
            present=Count(Case(When(is_present=True, then=1)))
        )
        
        for item in courses:
            total = item['total']
            present = item['present']
            percentage = round((present / total * 100), 1) if total > 0 else 0
            course_attendance.append({
                'course_code': item['session__timetable_entry__course_unit__code'],
                'course_name': item['session__timetable_entry__course_unit__name'],
                'total': total,
                'present': present,
                'percentage': percentage
            })

        context = {
            'today': today,
            'alerts': alerts,
            'grid': grid,
            'days': days,
            'today_sessions': today_sessions,
            'course_attendance': course_attendance,
        }
        return render(request, self.template_name, context)

class HomeView(LoginRequiredMixin, View):
    def get(self, request):
        # Force password reset if flag is set
        if request.user.requires_password_reset:
            return redirect('users:password_reset_first_login')

        if request.user.role == User.Role.SYSTEM_ADMIN:
            return redirect('sysadmin:dashboard')
        elif request.user.role == User.Role.FACULTY_ADMIN:
            return redirect('academic:faculty_dashboard')
        elif request.user.role == User.Role.HOD:
            return redirect('users:hod_dashboard')
        elif request.user.role == User.Role.COORDINATOR:
            return redirect('users:coordinator_dashboard')
        elif request.user.role == User.Role.LECTURER:
            return redirect('users:teaching_staff_dashboard')
        elif request.user.role == User.Role.STUDENT:
            return redirect('users:student_dashboard')
        return redirect('users:login')

class CoordinatorDashboardView(RoleRequiredMixin, View):
    allowed_roles = [User.Role.COORDINATOR]
    template_name = 'users/coordinator_dashboard.html'

    def get(self, request):
        user = request.user
        group = user.course_group
        program = group.program if group else None
        department = user.department
        today = timezone.now().date()

        if not group:
            messages.warning(request, "You have not been assigned to a course group yet.")
        
        # 1. Unread Alerts for Coordinator
        alerts = Alert.objects.filter(user=user, is_read=False).order_by('-created_at')[:5]

        # 2. Today's Timetable Entities and Sessions
        today_day_code = today.strftime('%a').upper()[:3] # e.g., 'MON'
        today_sessions_data = []
        if program:
            from scheduling.models import TimetableEntry, LectureSession
            entries = TimetableEntry.objects.filter(
                course_group=group,
                day_of_week=today_day_code
            ).select_related('course_unit', 'lecturer', 'room').order_by('start_time')
            
            for entry in entries:
                session = LectureSession.objects.filter(timetable_entry=entry, date=today).first()
                today_sessions_data.append({
                    'entry': entry,
                    'session': session
                })

        # 3. Timetable Grid for the group
        grid = []
        from scheduling.models import SchedulingParameters, TimetableEntry
        days = [('MON', 'Monday'), ('TUE', 'Tuesday'), ('WED', 'Wednesday'), ('THU', 'Thursday'), ('FRI', 'Friday')]
        
        if program and department:
            params = SchedulingParameters.objects.filter(department=department, is_active=True).first()
            if params:
                slots = params.get_timeslots()
                entries = TimetableEntry.objects.filter(course_group=group).select_related('course_unit', 'room')
                for start, end in slots:
                    row = {'time': f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}", 'slots': []}
                    for day_code, day_name in days:
                        entry = entries.filter(day_of_week=day_code, start_time=start).first()
                        row['slots'].append(entry)
                    grid.append(row)

        context = {
            'today': today,
            'alerts': alerts,
            'today_sessions': today_sessions_data,
            'grid': grid,
            'days': days,
            'group': group,
        }
        return render(request, self.template_name, context)

class TeachingStaffDashboardView(RoleRequiredMixin, View):
    allowed_roles = [User.Role.LECTURER]
    template_name = 'users/lecturer_dashboard.html'

    def get(self, request):
        user = request.user
        department = user.department
        today = timezone.now().date()

        # 1. Unread Alerts for Teaching Staff
        alerts = Alert.objects.filter(user=user, is_read=False).order_by('-created_at')[:5]

        # 1.5 Auto-mark missed sessions for today
        from core.services import AlertService
        AlertService.auto_mark_missed_sessions()

        # 2. Today's Sessions for the lecturer
        # Derive today's day code (e.g. 'MON', 'TUE', 'WED', ...)
        today_day_code = today.strftime('%a').upper()[:3]

        # Query timetable entries for this lecturer on today's day
        today_entries = TimetableEntry.objects.filter(
            lecturer=user,
            day_of_week=today_day_code
        ).select_related('course_unit', 'program', 'room').order_by('start_time')

        # For each entry, find or pair the LectureSession for today
        from datetime import datetime, timedelta
        now = timezone.now()
        today_sessions = []
        for entry in today_entries:
            session = LectureSession.objects.filter(timetable_entry=entry, date=today).first()
            if not session:
                session = LectureSession.objects.create(
                    timetable_entry=entry,
                    date=today,
                    status='SCHEDULED'
                )

            # Build interaction metadata
            start_time = entry.start_time
            session_start = timezone.make_aware(datetime.combine(today, start_time))
            window_start = session_start - timedelta(minutes=30)

            if window_start <= now <= session_start:
                can_interact = True
                interaction_message = "Active"
            elif now < window_start:
                can_interact = False
                mins_left = int((window_start - now).total_seconds() / 60)
                interaction_message = f"Interaction opens in {mins_left}m"
            else:
                can_interact = False
                interaction_message = "Interaction closed"

            today_sessions.append({
                'entry': entry,
                'session': session,
                'can_interact': can_interact,
                'interaction_message': interaction_message,
            })


        # 3. Timetable Grid for the lecturer
        grid = []
        days = [('MON', 'Monday'), ('TUE', 'Tuesday'), ('WED', 'Wednesday'), ('THU', 'Thursday'), ('FRI', 'Friday')]
        
        if department:
            params = SchedulingParameters.objects.filter(department=department, is_active=True).first()
            if params:
                slots = params.get_timeslots()
                entries = TimetableEntry.objects.filter(lecturer=user).select_related('course_unit', 'room', 'program')
                for start, end in slots:
                    row = {'time': f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}", 'slots': []}
                    for day_code, day_name in days:
                        entry = entries.filter(day_of_week=day_code, start_time=start).first()
                        row['slots'].append(entry)
                    grid.append(row)

        # 4. My Courses Summary
        my_courses = TimetableEntry.objects.filter(lecturer=user).values(
            'course_unit__name', 'course_unit__code', 'course_unit__id'
        ).distinct()

        context = {
            'today': today,
            'alerts': alerts,
            'today_sessions': today_sessions,
            'grid': grid,
            'days': days,
            'my_courses': my_courses,
        }
        return render(request, self.template_name, context)

class UserDeleteView(RoleRequiredMixin, View):
    allowed_roles = [User.Role.HOD]
    
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        
        # Ensure HOD can only delete users in their own department
        if user.department != request.user.department:
            messages.error(request, "You can only delete users within your department.")
            return redirect('users:user_list')
        
        username = user.username
        user.delete()
        messages.success(request, f"User {username} has been successfully deleted.")
        return redirect('users:user_list')

class BulkUpdateUsersView(RoleRequiredMixin, View):
    allowed_roles = [User.Role.HOD]
    
    def post(self, request):
        user_ids = request.POST.get('user_ids', '').split(',')
        new_group_id = request.POST.get('new_group')
        
        if not user_ids or not new_group_id:
            messages.error(request, "Invalid request. Please select users and a target group.")
            return redirect('users:user_list')
            
        from academic.models import CourseGroup
        new_group = get_object_or_404(CourseGroup, pk=new_group_id)
        
        # Security: Check if group belongs to HOD's department
        if new_group.program.department != request.user.department:
            messages.error(request, "Permission denied.")
            return redirect('users:user_list')
            
        updated_count = 0
        for uid in user_ids:
            if not uid: continue
            user = User.objects.filter(pk=uid, department=request.user.department).first()
            if user:
                user.course_group = new_group
                # Reset coordinator_id if they are a coordinator so save() re-generates it for the new group
                if user.role == User.Role.COORDINATOR:
                    user.coordinator_id = ""
                user.save()
                updated_count += 1
                
        messages.success(request, f"Successfully updated {updated_count} students to {new_group.name}.")
        return redirect('users:user_list')


class RevokeActivationView(RoleRequiredMixin, View):
    allowed_roles = [User.Role.HOD]

    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        
        # Security: Only HOD of the same department can revoke
        if target_user.department != request.user.department:
            messages.error(request, "Permission denied. You can only manage users within your department.")
            return redirect('users:user_list')
        
        # Revoke logic
        target_user.account_status = User.AccountStatus.NOT_ACTIVATED
        target_user.requires_password_reset = True
        target_user.set_unusable_password() # Prevent normal login with old password
        target_user.save()

        AuditLog.objects.create(
            actor=request.user,
            action="Account Activation Revoked",
            target=target_user,
            metadata={'message': f"HOD {request.user.username} revoked activation for {target_user.username}. User must now re-activate."}
        )

        messages.warning(request, f"Activation for {target_user.get_full_name()} has been revoked. They can now re-activate their account using the 'Activate Account' portal.")
        return redirect('users:user_list')

