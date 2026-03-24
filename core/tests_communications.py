import pytest
from django.urls import reverse
from users.models import User
from core.models import Alert
from academic.models import Department, Program, CourseUnit, Faculty
from scheduling.models import TimetableEntry, Room

@pytest.fixture
def setup_data(db):
    faculty = Faculty.objects.create(name="Science", code="SCI")
    department = Department.objects.create(name="CS", code="CS", faculty=faculty)
    program = Program.objects.create(name="BSCS", code="BSCS", department=department)
    unit = CourseUnit.objects.create(name="Programming", code="PRG101", course_type='THEORY')
    unit.programs.add(program)

    hod = User.objects.create_user(username="hod1", password="pw", role=User.Role.HOD, department=department)
    coord = User.objects.create_user(username="coord1", password="pw", role=User.Role.COORDINATOR, department=department)
    lecturer = User.objects.create_user(username="lec1", password="pw", role=User.Role.LECTURER, department=department)
    student = User.objects.create_user(username="stu1", password="pw", role=User.Role.STUDENT, department=department, program=program)

    room = Room.objects.create(name="Room A", capacity=50)
    
    TimetableEntry.objects.create(
        program=program,
        course_unit=unit,
        lecturer=lecturer,
        room=room,
        day_of_week='MON',
        start_time='08:00',
        end_time='10:00'
    )

    return {
        'department': department,
        'program': program,
        'unit': unit,
        'hod': hod,
        'coord': coord,
        'lecturer': lecturer,
        'student': student
    }

@pytest.mark.django_db
def test_hod_announcement_to_students(client, setup_data):
    # Login as HOD
    client.force_login(setup_data['hod'])
    
    url = reverse('core:create_announcement')
    data = {
        'target_group': 'STUDENTS',
        'message': 'Welcome to the new semester!'
    }
    response = client.post(url, data)
    assert response.status_code == 302 # redirect after success
    
    # Check alert created for student, not for lecturer
    student_alerts = Alert.objects.filter(user=setup_data['student'])
    lec_alerts = Alert.objects.filter(user=setup_data['lecturer'])
    
    assert student_alerts.count() == 1
    assert "From hod1: Welcome to the new semester!" in student_alerts.first().message
    assert lec_alerts.count() == 0

@pytest.mark.django_db
def test_lecturer_announcement_to_course(client, setup_data):
    # Create another student not in the program
    other_prog = Program.objects.create(name="BA", code="BA", department=setup_data['department'])
    other_student = User.objects.create_user(username="stu2", password="pw", role=User.Role.STUDENT, department=setup_data['department'], program=other_prog)
    
    # Login as LECTURER
    client.force_login(setup_data['lecturer'])
    
    url = reverse('core:create_announcement')
    data = {
        'target_course_unit': setup_data['unit'].id,
        'message': 'Assignment 1 uploaded'
    }
    response = client.post(url, data)
    assert response.status_code == 302 # redirect after success
    
    # Expected: setup_data['student'] gets it, other_student does not
    student_alerts = Alert.objects.filter(user=setup_data['student'])
    other_student_alerts = Alert.objects.filter(user=other_student)
    
    assert student_alerts.count() == 1
    assert "Assignment 1 uploaded" in student_alerts.first().message
    assert other_student_alerts.count() == 0
