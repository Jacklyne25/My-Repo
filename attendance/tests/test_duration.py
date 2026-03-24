import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from academic.models import Department, Program, CourseUnit
from scheduling.models import Room, TimetableEntry, LectureSession
from attendance.models import AttendanceRecord
from datetime import date, time, timedelta

User = get_user_model()

@pytest.fixture
def setup_data(db):
    dept = Department.objects.create(name='IT', code='IT01')
    prog = Program.objects.create(name='CS', code='CS01', department=dept)
    course = CourseUnit.objects.create(name='Programming', code='CS101', required_contact_hours=45)
    course.programs.add(prog)
    
    lecturer = User.objects.create_user(username='lecturer1', password='pw', role=User.Role.LECTURER)
    room = Room.objects.create(name='Lab 2', capacity=30)
    entry = TimetableEntry.objects.create(
        course_unit=course, lecturer=lecturer, program=prog, room=room,
        day_of_week='MON', start_time=time(8,0), end_time=time(10,0)
    )
    session = LectureSession.objects.create(timetable_entry=entry, date=date.today() - timedelta(days=1), status=LectureSession.Status.SUBMITTED)
    
    return {
        'lecturer': lecturer,
        'course': course,
        'session': session
    }

@pytest.mark.django_db
def test_lecturer_validation_with_duration(client, setup_data):
    client.login(username='lecturer1', password='pw')
    session = setup_data['session']
    url = reverse('attendance:validate_attendance', args=[session.pk])
    
    # 1. Validate with non-default duration (1.5 hours)
    response = client.post(url, {'actual_duration': '1.5'})
    assert response.status_code == 302
    
    session.refresh_from_db()
    assert session.status == LectureSession.Status.APPROVED
    assert float(session.actual_duration) == 1.5
    
    # 2. Check course contact hours
    course = setup_data['course']
    assert course.completed_contact_hours == 1.5
    
    # 3. Add another session with different duration
    session2 = LectureSession.objects.create(
        timetable_entry=session.timetable_entry, 
        date=date.today(), 
        status=LectureSession.Status.APPROVED,
        actual_duration=2.25
    )
    
    # 1.5 + 2.25 = 3.75
    assert course.completed_contact_hours == 3.75

@pytest.mark.django_db
def test_invalid_duration_handling(client, setup_data):
    client.login(username='lecturer1', password='pw')
    session = setup_data['session']
    url = reverse('attendance:validate_attendance', args=[session.pk])
    
    # Should handle invalid input gracefully (reverting to default or showing error)
    response = client.post(url, {'actual_duration': 'invalid'})
    assert response.status_code == 302
    
    session.refresh_from_db()
    assert session.status != LectureSession.Status.APPROVED # Should have failed validation
