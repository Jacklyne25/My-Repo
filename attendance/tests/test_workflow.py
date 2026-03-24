import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from academic.models import Department, Program, CourseUnit
from scheduling.models import Room, TimetableEntry, LectureSession
from attendance.models import AttendanceRecord
from datetime import date, time, timedelta
from django.utils import timezone

User = get_user_model()

@pytest.fixture
def base_data(db):
    dept = Department.objects.create(name='C', code='C')
    prog = Program.objects.create(name='P', code='P', department=dept)
    course = CourseUnit.objects.create(name='C1', code='C1')
    lecturer = User.objects.create_user(username='lect1', password='pw', role='LECTURER')
    student = User.objects.create_user(username='stud1', password='pw', role='STUDENT')
    room = Room.objects.create(name='R1', capacity=10)
    entry = TimetableEntry.objects.create(
        course_unit=course, lecturer=lecturer, program=prog, room=room,
        day_of_week='MON', start_time=time(10,0), end_time=time(12,0)
    )
    session = LectureSession.objects.create(timetable_entry=entry, date=date.today() - timedelta(days=1))
    return {'lecturer': lecturer, 'student': student, 'session': session}

@pytest.mark.django_db
def test_create_attendance_record(base_data):
    record = AttendanceRecord.objects.create(
        session=base_data['session'],
        student=base_data['student'],
        is_present=True
    )
    assert record.is_present is True
    assert str(record) == f"stud1 - Present for {base_data['session']}"

@pytest.mark.django_db
def test_prevent_future_attendance(base_data):
    future_session = LectureSession.objects.create(
        timetable_entry=base_data['session'].timetable_entry,
        date=date.today() + timedelta(days=1)
    )
    with pytest.raises(ValidationError) as exc:
        AttendanceRecord.objects.create(
            session=future_session,
            student=base_data['student'],
            is_present=True
        )
    assert "future session" in str(exc.value).lower()

@pytest.mark.django_db
def test_workflow_transitions(base_data):
    session = base_data['session']
    assert session.status == LectureSession.Status.SCHEDULED
    
    # Conducted
    session.mark_conducted()
    assert session.status == LectureSession.Status.CONDUCTED
    
    # Submitted
    session.submit_attendance()
    assert session.status == LectureSession.Status.SUBMITTED
    
    # Approved
    session.approve_attendance()
    assert session.status == LectureSession.Status.APPROVED
