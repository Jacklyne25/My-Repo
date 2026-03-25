from django.utils import timezone
from django.db.models import Count
from .models import Alert
from users.models import User
from scheduling.models import LectureSession
from datetime import datetime, timedelta

class AlertService:
    @staticmethod
    def create_alert(user, category, severity, alert_type, message):
        return Alert.objects.create(
            user=user,
            category=category,
            severity=severity,
            type=alert_type,
            message=message
        )

    @staticmethod
    def notify_security_breach(user=None, ip_address=None, details=None):
        sysadmins = User.objects.filter(role=User.Role.SYSTEM_ADMIN)
        message = f"Security Alert: {details}. Source IP: {ip_address}"
        if user:
            message += f", Target User: {user.username}"

        for admin in sysadmins:
            AlertService.create_alert(
                user=admin,
                category=Alert.Category.SECURITY,
                severity=Alert.Severity.CRITICAL,
                alert_type="SECURITY_BREACH",
                message=message
            )

    @staticmethod
    def notify_compliance_issue(hod, message):
        AlertService.create_alert(
            user=hod,
            category=Alert.Category.COMPLIANCE,
            severity=Alert.Severity.WARNING,
            alert_type="COMPLIANCE_ISSUE",
            message=message
        )

    @staticmethod
    def notify_integrity_issue(coordinator, message):
         AlertService.create_alert(
            user=coordinator,
            category=Alert.Category.INTEGRITY,
            severity=Alert.Severity.WARNING,
            alert_type="INTEGRITY_ISSUE",
            message=message
        )

    @staticmethod
    def notify_student_risk(coordinator, student, course_unit, current_attendance):
        message = f"Student {student.username} is at risk in {course_unit.name} (Attendance: {current_attendance:.1f}%)"
        AlertService.create_alert(
            user=coordinator,
            category=Alert.Category.STUDENT_RISK,
            severity=Alert.Severity.WARNING,
            alert_type="RISK_DETECTED",
            message=message
        )

    @staticmethod
    def notify_timetable_change(users, session, change_details):
        message = f"Timetable Change for {session.course_unit.name}: {change_details}"
        for user in users:
            AlertService.create_alert(
                user=user,
                category=Alert.Category.TIMETABLE,
                severity=Alert.Severity.INFO,
                alert_type="TIMETABLE_UPDATE",
                message=message
            )

    @staticmethod
    def notify_timetable_published(department):
        users = User.objects.filter(department=department, role__in=[User.Role.LECTURER, User.Role.STUDENT], is_active=True)
        message = f"The official timetable for {department.name} has been published/updated."
        alerts = [
            Alert(
                user=user,
                category=Alert.Category.TIMETABLE,
                severity=Alert.Severity.INFO,
                type="TIMETABLE_PUBLISHED",
                message=message
            ) for user in users
        ]
        if alerts:
            Alert.objects.bulk_create(alerts)

    @staticmethod
    def notify_lecture_rescheduled(entry, old_day, old_start):
        # Notify students in the program
        users = User.objects.filter(program=entry.program, role=User.Role.STUDENT, is_active=True)
        message = f"RESCHEDULED: {entry.course_unit.code} was moved from {old_day} at {old_start} to {entry.get_day_of_week_display()} at {entry.start_time.strftime('%H:%M')}."
        alerts = [
            Alert(
                user=user,
                category=Alert.Category.TIMETABLE,
                severity=Alert.Severity.WARNING,
                type="LECTURE_RESCHEDULED",
                message=message
            ) for user in users
        ]
        if alerts:
            Alert.objects.bulk_create(alerts)

    @staticmethod
    def notify_session_rescheduled(session, lecturer):
        # Notify coordinator of the group
        coordinator = User.objects.filter(course_group=session.timetable_entry.course_group, role=User.Role.COORDINATOR).first()
        message = f"LECTURE RESCHEDULED: {session.timetable_entry.course_unit.code} has been moved to {session.date} by {lecturer.get_full_name() or lecturer.username}."
        
        if coordinator:
            AlertService.create_alert(
                user=coordinator,
                category=Alert.Category.TIMETABLE,
                severity=Alert.Severity.WARNING,
                alert_type="SESSION_RESCHEDULED",
                message=message
            )
            
        # Notify affected students
        students = User.objects.filter(course_group=session.timetable_entry.course_group, role=User.Role.STUDENT, is_active=True)
        alerts = [
            Alert(
                user=str,
                category=Alert.Category.TIMETABLE,
                severity=Alert.Severity.WARNING,
                type="SESSION_RESCHEDULED",
                message=message
            ) for str in students
        ]
        if alerts:
            Alert.objects.bulk_create(alerts)

    @staticmethod
    def notify_session_confirmed(session, lecturer):
        # Notify affected students
        students = User.objects.filter(course_group=session.timetable_entry.course_group, role=User.Role.STUDENT, is_active=True)
        room_name = session.timetable_entry.room.name if session.timetable_entry.room else "the assigned room"
        message = f"LECTURE CONFIRMED: {session.timetable_entry.course_unit.code} is confirmed to take place today in {room_name}."
        alerts = [
            Alert(
                user=student,
                category=Alert.Category.TIMETABLE,
                severity=Alert.Severity.INFO,
                type="SESSION_CONFIRMED",
                message=message
            ) for student in students
        ]
        if alerts:
            Alert.objects.bulk_create(alerts)

    @staticmethod
    def notify_session_cancelled(session, lecturer):
        # Notify coordinator
        coordinator = User.objects.filter(course_group=session.timetable_entry.course_group, role=User.Role.COORDINATOR).first()
        message = f"LECTURE CANCELLED: {session.timetable_entry.course_unit.code} scheduled for today has been cancelled by {lecturer.get_full_name() or lecturer.username}."
        
        if coordinator:
            AlertService.create_alert(
                user=coordinator,
                category=Alert.Category.TIMETABLE,
                severity=Alert.Severity.CRITICAL,
                alert_type="SESSION_CANCELLED",
                message=message
            )
            
        # Notify affected students
        students = User.objects.filter(course_group=session.timetable_entry.course_group, role=User.Role.STUDENT, is_active=True)
        alerts = [
            Alert(
                user=student,
                category=Alert.Category.TIMETABLE,
                severity=Alert.Severity.CRITICAL,
                type="SESSION_CANCELLED",
                message=message
            ) for student in students
        ]
        if alerts:
            Alert.objects.bulk_create(alerts)

    @staticmethod
    def notify_attendance_recorded(session, recorded_by):
        lecturer = session.timetable_entry.lecturer
        message = f"Attendance for {session.timetable_entry.course_unit.code} ({session.date}) has been recorded by {recorded_by.get_full_name() or recorded_by.username}."
        AlertService.create_alert(
            user=lecturer,
            category=Alert.Category.REMINDER,
            severity=Alert.Severity.INFO,
            alert_type="ATTENDANCE_RECORDED",
            message=message
        )

    @staticmethod
    def notify_report_generated(hod, report_name):
        AlertService.create_alert(
            user=hod,
            category=Alert.Category.OPERATIONAL,
            severity=Alert.Severity.INFO,
            alert_type="REPORT_READY",
            message=f"A new {report_name} has been generated and is ready for review."
        )

    @staticmethod
    def check_compliance_and_integrity():
        """
        Runs periodic checks.
        """
        # 1. HOD Compliance: > 3 missed lectures
        # Group by lecturer and count MISSED sessions
        missed_stats = LectureSession.objects.filter(status=LectureSession.Status.MISSED)\
            .values('timetable_entry__lecturer')\
            .annotate(missed_count=Count('id'))\
            .filter(missed_count__gt=3)
            
        for stat in missed_stats:
            lecturer_id = stat['timetable_entry__lecturer']
            count = stat['missed_count']
            lecturer = User.objects.get(pk=lecturer_id)
            
            # Find HOD for this lecturer
            if lecturer.department:
                hods = User.objects.filter(department=lecturer.department, role=User.Role.HOD)
                for hod in hods:
                    AlertService.notify_compliance_issue(
                        hod,
                        f"Lecturer {lecturer.username} has missed {count} lectures."
                    )
        
        # 2. Coordinator Integrity: Unsubmitted attendance (CONDUCTED but not SUBMITTED > 24h)
        cutoff = timezone.now().date() # Simplified to date for this logic
        # Ideally check time, but date is safer for now. Sessions from *yesterday* or before.
        # Find sessions marked CONDUCTED but created distinct from now?
        # LectureSession has 'date'.
        
        # Sessions where date < today AND (status=CONDUCTED or status=SCHEDULED)
        # If SCHEDULED and past date => Should be marked MISSED usually. 
        # Checking for CONDUCTED (Took place) but not SUBMITTED (No record).
        
        stale_sessions = LectureSession.objects.filter(
            date__lt=cutoff,
            status=LectureSession.Status.CONDUCTED
        )
        
        for session in stale_sessions:
            # Find Coordinator (Assume Dept Coordinator)
            # Session -> Timetable -> CourseUnit -> Program -> Dept -> Coordinator
            # Simplified: Use User who is COORDINATOR in that Dept
            dept = session.timetable_entry.course_unit.programs.first().department
            coordinators = User.objects.filter(department=dept, role=User.Role.COORDINATOR)
            
            for coord in coordinators:
                AlertService.notify_integrity_issue(
                    coord,
                    f"Attendance for {session.timetable_entry.course_unit.name} on {session.date} has not been submitted."
                )

    @staticmethod
    def send_announcement(sender, target_group, message, department=None, program=None, course_unit=None):
        """
        Sends an announcement to a specific group of users.
        target_group can be: 'ALL', 'LECTURERS', 'STUDENTS', 'COORDINATORS', 'COURSE_UNIT'
        """
        users = User.objects.none()
        
        if target_group == 'ALL' and department:
            users = User.objects.filter(department=department, is_active=True)
        elif target_group == 'LECTURERS' and department:
            users = User.objects.filter(department=department, role=User.Role.LECTURER, is_active=True)
        elif target_group == 'STUDENTS' and department:
            users = User.objects.filter(department=department, role=User.Role.STUDENT, is_active=True)
        elif target_group == 'COORDINATORS' and department:
            users = User.objects.filter(department=department, role=User.Role.COORDINATOR, is_active=True)
        elif target_group == 'PROGRAM' and program:
            users = User.objects.filter(program=program, role=User.Role.STUDENT, is_active=True)
        elif target_group == 'COURSE_UNIT' and course_unit:
            # All students in all programs that include this course unit
            programs_with_unit = course_unit.programs.all()
            users = User.objects.filter(
                program__in=programs_with_unit, 
                role=User.Role.STUDENT, 
                is_active=True
            ).distinct()
        elif target_group == 'MANAGED_GROUPS' and sender.role == User.Role.COORDINATOR:
            managed_groups = sender.get_managed_course_groups()
            users = User.objects.filter(
                course_group__in=managed_groups,
                role=User.Role.STUDENT,
                is_active=True
            ).distinct()
            
        alerts = [
            Alert(
                user=user,
                category=Alert.Category.GENERAL,
                severity=Alert.Severity.INFO,
                type="ANNOUNCEMENT",
                message=f"From {sender.get_full_name() or sender.username}: {message}"
            ) for user in users
        ]
        
        if alerts:
            Alert.objects.bulk_create(alerts)
        return len(alerts)

    @staticmethod
    def auto_mark_missed_sessions():
        """Automatically mark sessions as missed 45 minutes after start time if no interaction."""
        now = timezone.now()
        today = now.date()
        
        sessions = LectureSession.objects.filter(
            date=today,
            status=LectureSession.Status.SCHEDULED
        )
        
        marked_count = 0
        for session in sessions:
            # Combine current date and start_time to get aware datetime
            start_time = session.timetable_entry.start_time
            session_start = timezone.make_aware(datetime.combine(today, start_time))
            
            if now > session_start + timedelta(minutes=45):
                session.status = LectureSession.Status.MISSED
                session.save()
                marked_count += 1
        return marked_count
