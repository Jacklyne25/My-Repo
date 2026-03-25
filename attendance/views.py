from django.shortcuts import render, get_object_or_404, redirect
from django.db.models.functions import TruncWeek
from django.db.models import Count, Q
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from scheduling.models import LectureSession, TimetableEntry
from django.utils import timezone
from .models import AttendanceRecord
from users.models import User
from academic.models import CourseUnit
from core.services import AlertService
from datetime import datetime, timedelta

class LecturerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == User.Role.LECTURER

class CoordinatorRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == User.Role.COORDINATOR

class SessionListView(LoginRequiredMixin, View):
    def get(self, request):
        # Base Queryset
        if request.user.role == User.Role.LECTURER:
            sessions = LectureSession.objects.filter(timetable_entry__lecturer=request.user)
        elif request.user.role == User.Role.COORDINATOR:
            program = request.user.course_group.program if request.user.course_group else None
            if program:
                sessions = LectureSession.objects.filter(timetable_entry__program=program)
            else:
                sessions = LectureSession.objects.none()
        elif request.user.role in [User.Role.HOD, User.Role.SYSTEM_ADMIN, User.Role.FACULTY_ADMIN]:
            sessions = LectureSession.objects.all()
            if request.user.department:
                sessions = sessions.filter(timetable_entry__course_unit__programs__department=request.user.department)
        else:
            sessions = LectureSession.objects.none()

        # Advanced Filtering
        status = request.GET.get('status')
        course = request.GET.get('course')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        if status:
            sessions = sessions.filter(status=status)
        if course:
            sessions = sessions.filter(timetable_entry__course_unit__id=course)
        if date_from:
            sessions = sessions.filter(date__gte=date_from)
        if date_to:
            sessions = sessions.filter(date__lte=date_to)

        sessions = sessions.select_related('timetable_entry__course_unit', 'timetable_entry__lecturer', 'timetable_entry__room').order_by('-date')

        # Context for filters
        courses = CourseUnit.objects.all()
        if request.user.department:
            courses = courses.filter(programs__department=request.user.department).distinct()

        return render(request, 'attendance/session_list.html', {
            'sessions': sessions,
            'stat_choices': LectureSession.Status.choices,
            'courses': courses,
            'selected_status': status,
            'selected_course': int(course) if course and course.isdigit() else None,
        })

class CaptureAttendanceView(LoginRequiredMixin, View):
    template_name = 'attendance/capture_attendance.html'

    def get(self, request, pk):
        session = get_object_or_404(LectureSession, pk=pk)
        
        # Lockout for coordinators after submission/approval
        if request.user.role == User.Role.COORDINATOR and session.status in [LectureSession.Status.SUBMITTED, LectureSession.Status.APPROVED]:
            messages.warning(request, "This session has already been submitted for evaluation and cannot be modified.")
            return redirect('attendance:session_list')

        # Check permissions
        if request.user.role == User.Role.LECTURER and session.timetable_entry.lecturer != request.user:
             messages.error(request, "You are not the assigned lecturer for this session.")
             return redirect('attendance:session_list')
        
        # Get students in the program/group
        if request.user.role == User.Role.COORDINATOR:
             students = User.objects.filter(role=User.Role.STUDENT, course_group=request.user.course_group)
        else:
             students = User.objects.filter(role=User.Role.STUDENT, department=session.timetable_entry.course_unit.programs.first().department)
        
        existing_records = {r.student_id: r.is_present for r in session.attendance_records.all()}
        
        return render(request, self.template_name, {
            'session': session,
            'students': students,
            'existing_records': existing_records
        })

    def post(self, request, pk):
        session = get_object_or_404(LectureSession, pk=pk)
        
        # Lockout for coordinators
        if request.user.role == User.Role.COORDINATOR and session.status in [LectureSession.Status.SUBMITTED, LectureSession.Status.APPROVED]:
            messages.error(request, "This session is locked and cannot be updated.")
            return redirect('attendance:session_list')

        present_student_ids = request.POST.getlist('present_students')
        
        # Clear existing records for this session
        session.attendance_records.all().delete()
        
        # Create new records
        if request.user.role == User.Role.COORDINATOR:
             students = User.objects.filter(role=User.Role.STUDENT, course_group=request.user.course_group)
        else:
             students = User.objects.filter(role=User.Role.STUDENT, department=session.timetable_entry.course_unit.programs.first().department)
        
        for student in students:
            is_present = str(student.id) in present_student_ids
            AttendanceRecord.objects.create(
                session=session,
                student=student,
                is_present=is_present
            )
        
        if request.user.role == User.Role.COORDINATOR:
            session.status = LectureSession.Status.CONDUCTED
            messages.success(request, "Attendance captured. Please submit for validation.")
            # Notify lecturer
            AlertService.notify_attendance_recorded(session, request.user)
        else:
            session.status = LectureSession.Status.CONDUCTED
            messages.success(request, "Attendance recorded.")
        
        session.save()
        return redirect('attendance:session_list')

class SubmitValidationView(CoordinatorRequiredMixin, View):
    def post(self, request, pk):
        session = get_object_or_404(LectureSession, pk=pk)
        
        if session.status == LectureSession.Status.SUBMITTED:
            messages.warning(request, "This attendance has already been submitted for verification.")
            return redirect('attendance:session_list')
        elif session.status == LectureSession.Status.APPROVED:
            messages.info(request, "This session has already been verified and approved.")
            return redirect('attendance:session_list')
        elif session.status != LectureSession.Status.CONDUCTED:
            messages.error(request, "Attendance must be captured before it can be submitted for verification.")
            return redirect('attendance:session_list')
            
        session.status = LectureSession.Status.SUBMITTED
        session.save()
        messages.success(request, "Attendance submitted for lecturer validation.")
        return redirect('attendance:session_list')

class StartAttendanceView(CoordinatorRequiredMixin, View):
    def post(self, request, entry_id):
         from datetime import timedelta
         entry = get_object_or_404(TimetableEntry, pk=entry_id)
         today = timezone.now().date()
         
         # Check if session already exists for this entry/date
         existing_session = LectureSession.objects.filter(
             timetable_entry=entry,
             date=today
         ).first()

         if existing_session:
             return redirect('attendance:capture_attendance', pk=existing_session.pk)

         # Rule: Uphold the standard two lecture sessions per week per course per group
         # Calculate the current week (Monday start)
         current_week_start = today - timedelta(days=today.weekday())
         existing_weekly_sessions = LectureSession.objects.filter(
             timetable_entry__course_unit=entry.course_unit,
             timetable_entry__course_group=entry.course_group,
             date__gte=current_week_start,
             date__lte=current_week_start + timedelta(days=6)
         ).exclude(status=LectureSession.Status.MISSED).count()

         if existing_weekly_sessions >= 2:
             messages.error(request, f"Action Blocked: The standard limit of two sessions per week for {entry.course_unit.code} has already been reached for this group.")
             return redirect('attendance:session_list')
         
         # If limit not reached, create the session
         session = LectureSession.objects.create(
             timetable_entry=entry,
             date=today,
             status=LectureSession.Status.SCHEDULED
         )
         
         messages.success(request, f"New session started for {entry.course_unit.code}.")
         return redirect('attendance:capture_attendance', pk=session.pk)

class ValidateAttendanceView(LecturerRequiredMixin, View):
    def post(self, request, pk):
        session = get_object_or_404(LectureSession, pk=pk)
        
        # Check permissions: Only the assigned lecturer or HOD can approve
        if request.user.role != User.Role.HOD and session.timetable_entry.lecturer != request.user:
             raise PermissionDenied

        # Get actual duration from form
        try:
            duration = request.POST.get('actual_duration', '2.00')
            session.actual_duration = float(duration)
        except (ValueError, TypeError):
            messages.error(request, "Invalid duration provided.")
            return redirect('attendance:session_list')

        session.status = LectureSession.Status.APPROVED
        session.save()
        messages.success(request, f"Attendance session validated and approved ({session.actual_duration} hrs).")
        return redirect('attendance:session_list')

class RescheduleSessionView(LecturerRequiredMixin, View):
    """Allow lecturers to reschedule a session to a future date."""
    def post(self, request, pk):
        session = get_object_or_404(LectureSession, pk=pk, timetable_entry__lecturer=request.user)
        
        if session.status == LectureSession.Status.LECTURER_CONFIRMED:
            messages.error(request, "Action Blocked: A confirmed session cannot be rescheduled.")
            return redirect(request.META.get('HTTP_REFERER', 'users:teaching_staff_dashboard'))

        new_date_str = request.POST.get('new_date')
        
        if not new_date_str:
            messages.error(request, "Please provide a valid reschedule date.")
            return redirect(request.META.get('HTTP_REFERER', 'users:teaching_staff_dashboard'))
            
        try:
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            if new_date < timezone.now().date():
                messages.error(request, "Action Blocked: You cannot reschedule a session to a past date.")
            else:
                # Check interaction window (0-30 mins before)
                now = timezone.now()
                start_time = session.timetable_entry.start_time
                session_start = timezone.make_aware(datetime.combine(session.date, start_time))
                window_start = session_start - timedelta(minutes=30)
                
                if now < window_start:
                    messages.error(request, "Interaction Window Error: You can only reschedule sessions starting within the next 30 minutes.")
                elif now > session_start:
                    messages.error(request, "Interaction Window Error: The session has already started. Use the 'Missed' flow if you didn't attend.")
                else:
                    old_date = session.date
                    session.date = new_date
                    session.status = LectureSession.Status.RESCHEDULED
                    session.save()
                    messages.success(request, f"Session originally for {old_date} has been rescheduled to {new_date}.")
                    # Notify coordinator and students
                    AlertService.notify_session_rescheduled(session, request.user)
        except ValueError:
            messages.error(request, "Invalid date format.")
            
        return redirect(request.META.get('HTTP_REFERER', 'users:teaching_staff_dashboard'))

class ConfirmSessionView(LecturerRequiredMixin, View):
    """Lecturer confirms they are available and starting the session."""
    def post(self, request, pk):
        session = get_object_or_404(LectureSession, pk=pk, timetable_entry__lecturer=request.user)
        
        if session.status == LectureSession.Status.LECTURER_CONFIRMED:
            messages.info(request, "Session is already confirmed.")
            return redirect(request.META.get('HTTP_REFERER', 'users:teaching_staff_dashboard'))

        # Check interaction window (0-30 mins before)
        now = timezone.now()
        start_time = session.timetable_entry.start_time
        session_start = timezone.make_aware(datetime.combine(session.date, start_time))
        window_start = session_start - timedelta(minutes=30)
        
        if now < window_start:
            messages.error(request, "Interaction Window Error: Confirmation is only allowed 30 minutes before the session starts.")
        elif now > session_start:
             messages.success(request, "Session already active. Setting status to Confirmed.")
             session.status = LectureSession.Status.LECTURER_CONFIRMED
             session.save()
             AlertService.notify_session_confirmed(session, request.user)
        else:
            session.status = LectureSession.Status.LECTURER_CONFIRMED
            session.save()
            messages.success(request, "Session confirmed. You are expected for this lecture.")
            AlertService.notify_session_confirmed(session, request.user)
            
        return redirect(request.META.get('HTTP_REFERER', 'users:teaching_staff_dashboard'))

class CancelSessionView(LecturerRequiredMixin, View):
    """Lecturer cancels the session within the interaction window."""
    def post(self, request, pk):
        session = get_object_or_404(LectureSession, pk=pk, timetable_entry__lecturer=request.user)
        
        if session.status == LectureSession.Status.LECTURER_CONFIRMED:
            messages.error(request, "Action Blocked: A confirmed session cannot be cancelled.")
            return redirect(request.META.get('HTTP_REFERER', 'users:teaching_staff_dashboard'))

        # Interaction window check
        now = timezone.now()
        start_time = session.timetable_entry.start_time
        session_start = timezone.make_aware(datetime.combine(session.date, start_time))
        window_start = session_start - timedelta(minutes=30)
        
        if now < window_start:
            messages.error(request, "Interaction Window Error: Cancellation is only allowed 30 minutes before the session starts.")
        elif now > session_start:
            messages.error(request, "Session already started. Cancellation window closed.")
        else:
            session.status = LectureSession.Status.CANCELLED
            session.save()
            messages.warning(request, "Session has been cancelled. Coordination staff and students will be notified.")
            AlertService.notify_session_cancelled(session, request.user)
            
        return redirect(request.META.get('HTTP_REFERER', 'users:teaching_staff_dashboard'))

class MarkMissedSessionsView(LoginRequiredMixin, View):
    """Identify sessions that passed without capture and mark as MISSED."""
    def post(self, request):
        if request.user.role not in [User.Role.HOD, User.Role.SYSTEM_ADMIN]:
            raise PermissionDenied

        today = timezone.now().date()
        # Find SCHEDULED sessions in the past
        past_pending_sessions = LectureSession.objects.filter(
            status=LectureSession.Status.SCHEDULED,
            date__lt=today
        )
        
        count = past_pending_sessions.count()
        for session in past_pending_sessions:
            session.status = LectureSession.Status.MISSED
            session.save()
            
        messages.success(request, f"Monitoring Update: {count} past sessions have been marked as MISSED.")
        return redirect(request.META.get('HTTP_REFERER', 'users:hod_dashboard'))

class CourseAttendanceSummaryView(LecturerRequiredMixin, View):
    template_name = 'attendance/course_summary.html'

    def get(self, request, pk):
        course = get_object_or_404(CourseUnit, pk=pk)
        sessions = LectureSession.objects.filter(
            timetable_entry__course_unit=course,
            timetable_entry__lecturer=request.user
        ).order_by('-date')

        summary_data = []
        total_present = 0
        total_records = 0

        for session in sessions:
            present = session.attendance_records.filter(is_present=True).count()
            total = session.attendance_records.count()
            total_present += present
            total_records += total
            summary_data.append({
                'session': session,
                'present': present,
                'total': total,
                'percentage': (present / total * 100) if total > 0 else 0
            })

        overall_percentage = (total_present / total_records * 100) if total_records > 0 else 0

        # Calculate Contact Hour Progress
        completed_hours = course.completed_contact_hours
        required_hours = course.required_contact_hours
        hours_status = "Complete" if completed_hours >= required_hours else "Incomplete"

        return render(request, self.template_name, {
            'course': course,
            'summary_data': summary_data,
            'overall_percentage': overall_percentage,
            'total_sessions': sessions.count(),
            'completed_hours': completed_hours,
            'required_hours': required_hours,
            'hours_status': hours_status,
        })


class WeeklyAttendanceView(LoginRequiredMixin, View):
    """View to manage attendance on a weekly basis."""
    template_name = 'attendance/weekly_dashboard.html'

    def get(self, request):
        if request.user.role == User.Role.LECTURER:
            sessions = LectureSession.objects.filter(timetable_entry__lecturer=request.user)
        elif request.user.role == User.Role.COORDINATOR:
            program = request.user.course_group.program if request.user.course_group else None
            if program:
                sessions = LectureSession.objects.filter(timetable_entry__program=program)
            else:
                sessions = LectureSession.objects.none()
        else:
            sessions = LectureSession.objects.none()

        # Group by week and course unit
        weekly_data = sessions.annotate(week=TruncWeek('date')).values(
            'week', 'timetable_entry__course_unit__id', 'timetable_entry__course_unit__code', 'timetable_entry__course_unit__name'
        ).annotate(
            total_sessions=Count('id'),
            conducted_count=Count('id', filter=Q(status=LectureSession.Status.CONDUCTED)),
            submitted_count=Count('id', filter=Q(status=LectureSession.Status.SUBMITTED)),
            approved_count=Count('id', filter=Q(status=LectureSession.Status.APPROVED)),
            missed_count=Count('id', filter=Q(status=LectureSession.Status.MISSED)),
        ).order_by('-week', 'timetable_entry__course_unit__code')

        # To get the actual session objects for each week-course group (for detailed view)
        # We'll pass the grouped data and the user can drill down.
        
        return render(request, self.template_name, {
            'weekly_summary': weekly_data,
        })


class UploadSignedSheetView(CoordinatorRequiredMixin, View):
    """Allow coordinators to upload scanned attendance sheets."""
    def post(self, request, pk):
        session = get_object_or_404(LectureSession, pk=pk)
        
        if session.status in [LectureSession.Status.SUBMITTED, LectureSession.Status.APPROVED]:
            messages.error(request, "Cannot upload sheet for a submitted or approved session.")
            return redirect(request.META.get('HTTP_REFERER', 'attendance:session_list'))

        if 'signed_sheet' in request.FILES:
            session.signed_sheet = request.FILES['signed_sheet']
            session.recording_method = LectureSession.RecordingMethod.PAPER
            # Automatically trigger CONDUCTED status if it was SCHEDULED
            if session.status == LectureSession.Status.SCHEDULED:
                session.status = LectureSession.Status.CONDUCTED
            session.save()
            messages.success(request, f"Signed sheet uploaded and session marked as CONDUCTED for {session.timetable_entry.course_unit.code}.")
        else:
            messages.error(request, "No file uploaded.")
        return redirect(request.META.get('HTTP_REFERER', 'attendance:session_list'))


class WeekCourseDetailView(LoginRequiredMixin, View):
    """Detailed view for a specific week and course unit."""
    template_name = 'attendance/week_detail.html'

    def get(self, request, week_str, course_id):
        from datetime import datetime, timedelta
        week_date = datetime.strptime(week_str, '%Y-%m-%d').date()
        course = get_object_or_404(CourseUnit, pk=course_id)
        
        sessions = LectureSession.objects.filter(
            timetable_entry__course_unit=course,
            date__range=[week_date, week_date + timedelta(days=6)]
        ).order_by('date')

        # Check permission: Lecturer must be the one for these sessions OR HOD
        if request.user.role == User.Role.LECTURER:
            if not sessions.filter(timetable_entry__lecturer=request.user).exists():
                raise PermissionDenied

        return render(request, self.template_name, {
            'week_date': week_date,
            'course': course,
            'sessions': sessions,
        })


class LecturerReviewWeekView(LecturerRequiredMixin, View):
    """Batch approve all sessions for a course unit in a specific week."""
    def post(self, request, week_str, course_id):
        from datetime import datetime, timedelta
        week_date = datetime.strptime(week_str, '%Y-%m-%d').date()
        
        sessions = LectureSession.objects.filter(
            timetable_entry__course_unit_id=course_id,
            timetable_entry__lecturer=request.user,
            date__range=[week_date, week_date + timedelta(days=6)]
        ).filter(status=LectureSession.Status.SUBMITTED)
        
        count = sessions.count()
        for session in sessions:
            session.approve_attendance()
        
        messages.success(request, f"Approved {count} sessions for this week.")
        return redirect('attendance:weekly_dashboard')


class GenerateReportView(LoginRequiredMixin, View):
    """Trigger a 'Report Generated' notification for the HOD."""
    def post(self, request):
        if request.user.role != User.Role.HOD:
             raise PermissionDenied
        
        report_name = request.POST.get('report_name', 'General Attendance Report')
        AlertService.notify_report_generated(request.user, report_name)
        
        messages.success(request, f"{report_name} generated successfully. You have been notified.")
        return redirect(request.META.get('HTTP_REFERER', 'users:hod_dashboard'))




