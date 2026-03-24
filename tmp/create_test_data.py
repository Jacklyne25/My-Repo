import os
import sys
import django
import random
from datetime import date, time, timedelta

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()

from users.models import User
from academic.models import Department, Program, CourseUnit
from scheduling.models import TimetableEntry, Room, SchedulingParameters, LectureSession
from attendance.models import AttendanceRecord
from core.models import Alert

def create_test_enrollment():
    print("Creating test data...")
    
    # 1. Create Department
    dept, _ = Department.objects.get_or_create(code='TEST_DEPT', defaults={'name': 'Testing Department'})
    
    # 2. Create Program
    prog, _ = Program.objects.get_or_create(code='TEST_PROG', defaults={'name': 'Bachelor of Testing', 'department': dept})
    
    # 3. Create Rooms
    room1, _ = Room.objects.get_or_create(name='Room 101', defaults={'capacity': 50})
    room2, _ = Room.objects.get_or_create(name='Room 102', defaults={'capacity': 30})
    
    # 4. Create Scheduling Parameters
    params, _ = SchedulingParameters.objects.get_or_create(
        department=dept, 
        is_active=True,
        defaults={
            'semester_name': 'Semester 1',
            'academic_year': '2026/2027',
            'available_days': 'MON,TUE,WED,THU,FRI',
            'day_start_time': '08:00',
            'day_end_time': '17:00',
            'slot_duration_hours': 2
        }
    )
    
    # 5. Create Lecturer
    lecturer, _ = User.objects.get_or_create(
        username='test_lecturer',
        defaults={
            'first_name': 'John',
            'last_name': 'Lecturer',
            'role': User.Role.LECTURER,
            'department': dept,
            'is_active': True
        }
    )
    if lecturer.role != User.Role.LECTURER:
        lecturer.role = User.Role.LECTURER
        lecturer.save()
    lecturer.set_password('password123')
    lecturer.save()
    
    # 6. Create Student
    student, _ = User.objects.get_or_create(
        username='test_student',
        defaults={
            'first_name': 'Jane',
            'last_name': 'Student',
            'role': User.Role.STUDENT,
            'department': dept,
            'program': prog,
            'is_active': True
        }
    )
    if student.role != User.Role.STUDENT:
        student.role = User.Role.STUDENT
        student.save()
    student.program = prog # Ensure program is set
    student.set_password('password123')
    student.save()
    
    # 7. Create Course Units
    course1, _ = CourseUnit.objects.get_or_create(code='CS101', defaults={'name': 'Intro to Coding', 'lecturer': lecturer})
    course1.programs.add(prog)
    
    course2, _ = CourseUnit.objects.get_or_create(code='CS102', defaults={'name': 'Data Structures', 'lecturer': lecturer})
    course2.programs.add(prog)
    
    # 8. Create Timetable Entries
    # Monday 08:00-10:00 CS101
    TimetableEntry.objects.get_or_create(
        course_unit=course1, lecturer=lecturer, program=prog, room=room1,
        day_of_week='MON', start_time=time(8, 0), end_time=time(10, 0)
    )
    
    # Tuesday 10:00-12:00 CS102
    TimetableEntry.objects.get_or_create(
        course_unit=course2, lecturer=lecturer, program=prog, room=room2,
        day_of_week='TUE', start_time=time(10, 0), end_time=time(12, 0)
    )
    
    # Today's Entry (Dynamic)
    today = date.today()
    day_code = today.strftime('%a').upper()[:3]
    entry_today, _ = TimetableEntry.objects.get_or_create(
        course_unit=course1, lecturer=lecturer, program=prog, room=room1,
        day_of_week=day_code, start_time=time(14, 0), end_time=time(16, 0)
    )
    
    # 9. Create Lecture Sessions & Attendance
    # Past session for CS101
    last_week = today - timedelta(days=7)
    session_past, _ = LectureSession.objects.get_or_create(
        timetable_entry=entry_today,
        date=last_week,
        defaults={'status': LectureSession.Status.CONDUCTED}
    )
    AttendanceRecord.objects.get_or_create(session=session_past, student=student, defaults={'is_present': True})
    
    # Today's session
    LectureSession.objects.get_or_create(
        timetable_entry=entry_today,
        date=today,
        defaults={'status': LectureSession.Status.SCHEDULED}
    )
    
    # 10. Create Announcements/Alerts
    Alert.objects.get_or_create(
        user=student,
        type='TIMETABLE_UPDATE',
        defaults={
            'message': 'Welcome to your new Student Dashboard!',
            'category': Alert.Category.GENERAL,
            'severity': Alert.Severity.INFO
        }
    )
    
    print("Test data created successfully.")
    print(f"Student: {student.username} (P: password123)")

if __name__ == "__main__":
    create_test_enrollment()
