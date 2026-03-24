from django.test import TestCase, Client
from django.urls import reverse
from users.models import User
from academic.models import Department, Faculty, Program, CourseUnit, CourseGroup
from scheduling.models import TimetableEntry, Room, SchedulingParameters, LectureSession
from attendance.models import AttendanceRecord
from datetime import time, date, timedelta
from django.core.files.uploadedfile import SimpleUploadedFile

class HybridAttendanceTests(TestCase):
    def setUp(self):
        self.faculty = Faculty.objects.create(name="IT", code="IT")
        self.dept = Department.objects.create(name="CS", code="CS", faculty=self.faculty)
        self.program = Program.objects.create(name="BSCS", code="BSCS", department=self.dept)
        self.group = CourseGroup.objects.create(name="Year 1", program=self.program)
        
        self.lecturer = User.objects.create_user(username="lecturer", password="pw", role="LECTURER", department=self.dept)
        self.coordinator = User.objects.create_user(username="coord", password="pw", role="COORDINATOR", department=self.dept, course_group=self.group)
        self.student = User.objects.create_user(username="student", password="pw", role="STUDENT", department=self.dept, course_group=self.group)
        
        self.course = CourseUnit.objects.create(code="CS101", name="Intro")
        self.course.programs.add(self.program)
        self.room = Room.objects.create(name="Lab 1", capacity=50)
        
        self.entry = TimetableEntry.objects.create(
            course_unit=self.course,
            lecturer=self.lecturer,
            program=self.program,
            room=self.room,
            day_of_week="MON",
            start_time=time(8, 0),
            end_time=time(10, 0)
        )
        
        # Create a session for this week
        self.session = LectureSession.objects.create(
            timetable_entry=self.entry,
            date=date.today(),
            status='SCHEDULED'
        )
        
        self.client = Client()

    def test_signed_sheet_upload(self):
        self.client.login(username="coord", password="pw")
        mock_file = SimpleUploadedFile("sheet.jpg", b"file_content", content_type="image/jpeg")
        
        response = self.client.post(reverse('attendance:upload_sheet', args=[self.session.pk]), {
            'signed_sheet': mock_file
        })
        self.assertEqual(response.status_code, 302)
        
        self.session.refresh_from_db()
        self.assertTrue(self.session.signed_sheet)
        self.assertEqual(self.session.recording_method, 'PAPER')

    def test_weekly_dashboard_summary(self):
        self.client.login(username="lecturer", password="pw")
        response = self.client.get(reverse('attendance:weekly_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('weekly_summary', response.context)
        # Check if our session is counted
        summary = response.context['weekly_summary'][0]
        self.assertEqual(summary['timetable_entry__course_unit__code'], 'CS101')

    def test_batch_approval_flow(self):
        # 1. Coordinator marks session as CONDUCTED and SUBMITS
        self.session.status = 'CONDUCTED'
        self.session.save()
        
        self.client.login(username="coord", password="pw")
        self.client.post(reverse('attendance:submit_validation', args=[self.session.pk]))
        
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'SUBMITTED')
        
        # 2. Lecturer approves the whole week
        self.client.login(username="lecturer", password="pw")
        week_str = (self.session.date - timedelta(days=self.session.date.weekday())).strftime('%Y-%m-%d')
        response = self.client.post(reverse('attendance:review_week', args=[week_str, self.course.pk]))
        self.assertEqual(response.status_code, 302)
        
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'APPROVED')
