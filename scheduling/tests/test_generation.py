import pytest
from datetime import date
from django.contrib.auth import get_user_model
from academic.models import Department, Program, CourseUnit
from scheduling.models import Room, TimetableEntry, LectureSession
from scheduling.utils import generate_sessions_for_range
from datetime import time

User = get_user_model()

@pytest.mark.django_db
def test_generate_sessions(db):
    dept = Department.objects.create(name='C', code='C')
    prog = Program.objects.create(name='P', code='P', department=dept)
    course = CourseUnit.objects.create(name='C1', code='C1')
    lecturer = User.objects.create_user(username='lect1', password='pw', role='LECTURER')
    room = Room.objects.create(name='R1', capacity=10)
    
    # Entry: Every Monday 10-12
    entry = TimetableEntry.objects.create(
        course_unit=course, lecturer=lecturer, program=prog, room=room,
        day_of_week='MON', start_time=time(10,0), end_time=time(12,0)
    )
    
    # Generate sessions for Feb 2026 (Mondays are 2, 9, 16, 23)
    start = date(2026, 2, 1)
    end = date(2026, 2, 28)
    
    count = generate_sessions_for_range(TimetableEntry.objects.all(), start, end)
    
    assert count == 4
    assert LectureSession.objects.count() == 4
    assert LectureSession.objects.filter(date=date(2026, 2, 2)).exists()
    assert LectureSession.objects.filter(date=date(2026, 2, 23)).exists()
