from core.models import Alert
from core.analytics import calculate_student_attendance

def check_low_attendance(student, programs=None):
    percentage = calculate_student_attendance(student, programs)
    if percentage < 75.0:
        Alert.objects.get_or_create(
            user=student,
            type=Alert.AlertType.LOW_ATTENDANCE,
            category=Alert.Category.GENERAL,
            severity=Alert.Severity.WARNING,
            message=f"Warning: Your attendance has dropped to {percentage}%."
        )

def check_missed_lecture(session):
    if session.status == 'MISSED':
        from users.models import User
        # Get HOD of the department for this session
        dept = session.timetable_entry.course_unit.programs.first().department
        hod = User.objects.filter(role=User.Role.HOD, department=dept).first()
        
        if hod:
            Alert.objects.get_or_create(
                user=hod,
                type=Alert.AlertType.MISSED_LECTURE,
                category=Alert.Category.COMPLIANCE,
                severity=Alert.Severity.CRITICAL,
                message=f"Lecturer {session.timetable_entry.lecturer.username} missed scheduled lecture – {session.timetable_entry.course_unit.code} ({session.date})"
            )

def check_unsubmitted_attendance(department):
    """Scan for sessions that have passed their end time but remain SCHEDULED."""
    from django.utils import timezone
    from scheduling.models import LectureSession
    from users.models import User
    
    now = timezone.now()
    today = now.date()
    current_time = now.time()
    
    # Sessions from today that have ended but are still SCHEDULED
    pending_sessions = LectureSession.objects.filter(
        date=today,
        status='SCHEDULED',
        timetable_entry__end_time__lt=current_time,
        timetable_entry__course_unit__programs__department=department
    )
    
    hod = User.objects.filter(role=User.Role.HOD, department=department).first()
    
    if hod:
        for session in pending_sessions:
            Alert.objects.get_or_create(
                user=hod,
                type=Alert.AlertType.PENDING_SUBMISSION,
                category=Alert.Category.COMPLIANCE,
                severity=Alert.Severity.WARNING,
                message=f"Coordinator has not submitted attendance – Today {session.timetable_entry.start_time.strftime('%I%p').lower()} class ({session.timetable_entry.course_unit.code})"
            )
