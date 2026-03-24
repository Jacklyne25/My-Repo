import pytest
from core.analytics import calculate_student_attendance
from core.models import Alert
from scheduling.models import LectureSession
from attendance.models import AttendanceRecord
from django.contrib.auth import get_user_model
from academic.models import Department, Program, CourseUnit
from scheduling.models import Room, TimetableEntry
from datetime import date, time, timedelta

User = get_user_model()

@pytest.fixture
def complex_data(db):
    dept = Department.objects.create(name='C', code='C')
    prog = Program.objects.create(name='P', code='P', department=dept)
    course = CourseUnit.objects.create(name='C1', code='C1')
    lecturer = User.objects.create_user(username='lecturer1', password='pw', role='LECTURER')
    student = User.objects.create_user(username='student1', password='pw', role='STUDENT')
    hod = User.objects.create_user(username='hod1', password='pw', role='HOD')
    room = Room.objects.create(name='R1', capacity=10)
    entry = TimetableEntry.objects.create(
        course_unit=course, lecturer=lecturer, program=prog, room=room,
        day_of_week='MON', start_time=time(10,0), end_time=time(12,0)
    )
    # create 4 sessions
    sessions = []
    for i in range(4):
        s = LectureSession.objects.create(timetable_entry=entry, date=date.today() - timedelta(days=i+1))
        sessions.append(s)
    
    return {'student': student, 'sessions': sessions, 'hod': hod}

@pytest.mark.django_db
def test_calculate_student_attendance_logic(complex_data):
    student = complex_data['student']
    sessions = complex_data['sessions']
    
    # 3 present, 1 absent -> 75%
    AttendanceRecord.objects.create(session=sessions[0], student=student, is_present=True)
    AttendanceRecord.objects.create(session=sessions[1], student=student, is_present=True)
    AttendanceRecord.objects.create(session=sessions[2], student=student, is_present=True)
    AttendanceRecord.objects.create(session=sessions[3], student=student, is_present=False)
    
    assert calculate_student_attendance(student) == 75.0

@pytest.mark.django_db
def test_low_attendance_alert_trigger(complex_data):
    student = complex_data['student']
    sessions = complex_data['sessions']
    
    # Mark 4 sessions, 2 present -> 50% (below 75%)
    # Use the session.approve_attendance to trigger
    for i in range(4):
        AttendanceRecord.objects.create(session=sessions[i], student=student, is_present=(i < 2))
        sessions[i].status = LectureSession.Status.SUBMITTED
        sessions[i].approve_attendance()
        
    assert Alert.objects.filter(user=student, type=Alert.AlertType.LOW_ATTENDANCE).exists()

@pytest.mark.django_db
def test_missed_lecture_alert_trigger(complex_data):
    session = complex_data['sessions'][0]
    session.status = LectureSession.Status.MISSED
    session.save()
    
    assert Alert.objects.filter(user=complex_data['hod'], type=Alert.AlertType.MISSED_LECTURE).exists()
