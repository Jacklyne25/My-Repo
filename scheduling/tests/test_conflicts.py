import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from academic.models import Department, Program, CourseUnit
from scheduling.models import Room, TimetableEntry
from datetime import time

User = get_user_model()

@pytest.fixture
def lecturer(db):
    return User.objects.create_user(username='lecturer1', password='password', role='LECTURER')

@pytest.fixture
def room(db):
    return Room.objects.create(name='Room 101', capacity=30)

@pytest.fixture
def program(db):
    dept = Department.objects.create(name='Computing', code='CT')
    return Program.objects.create(name='BSIT', code='BSIT', department=dept)

@pytest.fixture
def course(db):
    return CourseUnit.objects.create(name='Databases', code='DB101')

@pytest.mark.django_db
def test_detect_room_conflict(lecturer, room, program, course):
    # Entry 1: Mon 10-12 in Room 101
    TimetableEntry.objects.create(
        course_unit=course, lecturer=lecturer, program=program, room=room,
        day_of_week='MON', start_time=time(10, 0), end_time=time(12, 0)
    )
    
    # Entry 2: Mon 11-1 in Room 101 (Conflict)
    with pytest.raises(ValidationError) as exc:
        TimetableEntry.objects.create(
            course_unit=course, lecturer=lecturer, program=program, room=room,
            day_of_week='MON', start_time=time(11, 0), end_time=time(13, 0)
        )
    assert "Room conflict" in str(exc.value)

@pytest.mark.django_db
def test_detect_lecturer_conflict(lecturer, room, program, course):
    room2 = Room.objects.create(name='Room 102', capacity=30)
    # Entry 1: Mon 10-12 for Lecturer in Room 101
    TimetableEntry.objects.create(
        course_unit=course, lecturer=lecturer, program=program, room=room,
        day_of_week='MON', start_time=time(10, 0), end_time=time(12, 0)
    )
    
    # Entry 2: Mon 10-12 for same Lecturer in Room 102 (Conflict)
    with pytest.raises(ValidationError) as exc:
        TimetableEntry.objects.create(
            course_unit=course, lecturer=lecturer, program=program, room=room2,
            day_of_week='MON', start_time=time(10, 0), end_time=time(12, 0)
        )
    assert "Lecturer conflict" in str(exc.value)
