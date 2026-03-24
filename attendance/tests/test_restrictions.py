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
    course = CourseUnit.objects.create(name='Programming', code='CS101')
    course.programs.add(prog)
    
    lecturer = User.objects.create_user(username='lecturer', password='pw', role=User.Role.LECTURER)
    coordinator = User.objects.create_user(username='coordinator', password='pw', role=User.Role.COORDINATOR)
    student = User.objects.create_user(username='student', password='pw', role=User.Role.STUDENT)
    
    from academic.models import CourseGroup
    group = CourseGroup.objects.create(name='Group A', program=prog)
    coordinator.course_group = group
    coordinator.save()
    student.course_group = group
    student.save()
    
    room = Room.objects.create(name='Lab 1', capacity=30)
    entry = TimetableEntry.objects.create(
        course_unit=course, lecturer=lecturer, program=prog, room=room,
        day_of_week='MON', start_time=time(8,0), end_time=time(10,0)
    )
    session = LectureSession.objects.create(timetable_entry=entry, date=date.today() - timedelta(days=1))
    
    return {
        'lecturer': lecturer,
        'coordinator': coordinator,
        'student': student,
        'session': session
    }

@pytest.mark.django_db
def test_coordinator_lockout_get(client, setup_data):
    coordinator = setup_data['coordinator']
    session = setup_data['session']
    client.login(username='coordinator', password='pw')
    
    url = reverse('attendance:capture_attendance', args=[session.pk])
    
    # 1. Allowed when SCHEDULED
    response = client.get(url)
    assert response.status_code == 200
    
    # 2. Blocked when SUBMITTED
    session.status = LectureSession.Status.SUBMITTED
    session.save()
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse('attendance:session_list')
    
    # 3. Blocked when APPROVED
    session.status = LectureSession.Status.APPROVED
    session.save()
    response = client.get(url)
    assert response.status_code == 302

@pytest.mark.django_db
def test_coordinator_lockout_post(client, setup_data):
    coordinator = setup_data['coordinator']
    session = setup_data['session']
    client.login(username='coordinator', password='pw')
    
    url = reverse('attendance:capture_attendance', args=[session.pk])
    data = {'present_students': [setup_data['student'].id]}
    
    # Blocked when SUBMITTED
    session.status = LectureSession.Status.SUBMITTED
    session.save()
    response = client.post(url, data)
    assert response.status_code == 302
    assert session.attendance_records.count() == 0

@pytest.mark.django_db
def test_upload_sheet_lockout(client, setup_data):
    client.login(username='coordinator', password='pw')
    session = setup_data['session']
    url = reverse('attendance:upload_sheet', args=[session.pk])
    
    session.status = LectureSession.Status.SUBMITTED
    session.save()
    
    # Should be blocked
    response = client.post(url, {'signed_sheet': 'dummy_file'})
    assert response.status_code == 302
    session.refresh_from_db()
    assert not session.signed_sheet

@pytest.mark.django_db
def test_lecturer_can_still_review(client, setup_data):
    client.login(username='lecturer', password='pw')
    session = setup_data['session']
    session.status = LectureSession.Status.SUBMITTED
    session.save()
    
    url = reverse('attendance:capture_attendance', args=[session.pk])
    response = client.get(url)
    assert response.status_code == 200 # Lecturers can still see/review
