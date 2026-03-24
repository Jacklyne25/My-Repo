from attendance.models import AttendanceRecord
from scheduling.models import LectureSession

def calculate_student_attendance(student, programs=None):
    """
    Calculates attendance percentage for a student.
    Can be filtered by specific programs.
    """
    attendance_qs = AttendanceRecord.objects.filter(student=student)
    if programs:
        attendance_qs = attendance_qs.filter(session__timetable_entry__program__in=programs)
    
    total = attendance_qs.count()
    if total == 0:
        return 100.0
    
    present = attendance_qs.filter(is_present=True).count()
    return round((present / total) * 100, 2)

def calculate_course_attendance(timetable_entry):
    """
    Calculates aggregate attendance for a specific course/program slot.
    """
    sessions = LectureSession.objects.filter(timetable_entry=timetable_entry, status=LectureSession.Status.CONDUCTED)
    total_records = AttendanceRecord.objects.filter(session__in=sessions).count()
    if total_records == 0:
        return 0.0
    
    present_records = AttendanceRecord.objects.filter(session__in=sessions, is_present=True).count()
    return round((present_records / total_records) * 100, 2)
