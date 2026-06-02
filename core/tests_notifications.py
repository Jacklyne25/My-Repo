from django.test import TestCase, Client
from django.urls import reverse
from users.models import User
from academic.models import Department, Faculty, Program, CourseUnit
from scheduling.models import TimetableEntry, Room, SchedulingParameters, LectureSession
from core.models import Alert
from datetime import time, date

class NotificationTests(TestCase):
    def setUp(self):
        self.faculty = Faculty.objects.create(name="IT")
        self.dept = Department.objects.create(name="CS", faculty=self.faculty)
        self.program = Program.objects.create(name="BSCS", department=self.dept)
        
        self.hod = User.objects.create_user(username="hod", password="pw", role="HOD", department=self.dept)
        self.lecturer = User.objects.create_user(username="lecturer", password="pw", role="LECTURER", department=self.dept)
        self.student = User.objects.create_user(username="student", password="pw", role="STUDENT", department=self.dept)
        self.coordinator = User.objects.create_user(username="coord", password="pw", role="COORDINATOR", department=self.dept)
        
        # Link student to program
        self.student.program = self.program
        self.student.save()
        
        self.course = CourseUnit.objects.create(code="CS101", name="Intro")
        self.course.programs.add(self.program)
        
        self.room = Room.objects.create(name="Lab 1", capacity=50)
        
        self.params = SchedulingParameters.objects.create(
            department=self.dept,
            cohort='EASTER',
            academic_year="2026/2027",
            available_days="MON,TUE",
            is_active=True
        )
        
        self.entry = TimetableEntry.objects.create(
            course_unit=self.course,
            lecturer=self.lecturer,
            program=self.program,
            room=self.room,
            day_of_week="MON",
            start_time=time(8, 0),
            end_time=time(10, 0)
        )
        
        self.client = Client()

    def test_timetable_published_notification(self):
        self.client.login(username="hod", password="pw")
        response = self.client.post(reverse('scheduling:publish_timetable'))
        self.assertEqual(response.status_code, 302)
        
        # Check alerts for lecturer and student
        self.assertTrue(Alert.objects.filter(user=self.lecturer, type='TIMETABLE_PUBLISHED').exists())
        self.assertTrue(Alert.objects.filter(user=self.student, type='TIMETABLE_PUBLISHED').exists())
        
        alert = Alert.objects.get(user=self.lecturer, type='TIMETABLE_PUBLISHED')
        self.assertIn("timetable", alert.message)
        self.assertIn("published", alert.message)

    def test_lecture_rescheduled_notification(self):
        self.client.login(username="hod", password="pw")
        
        # Reschedule: change day to TUE
        response = self.client.post(reverse('scheduling:update_entry', args=[self.entry.pk]), {
            'day': 'TUE',
            'slot': '10:00-12:00',
            'room': self.room.pk,
            'lecturer': self.lecturer.pk
        })
        self.assertEqual(response.status_code, 302)
        
        # Check alerts for student in the program
        self.assertTrue(Alert.objects.filter(user=self.student, type='LECTURE_RESCHEDULED').exists())
        
        alert = Alert.objects.get(user=self.student, type='LECTURE_RESCHEDULED')
        self.assertIn("CS101", alert.message)
        self.assertIn("Monday at 08:00", alert.message)
        self.assertIn("Tuesday at 10:00", alert.message)

    def test_attendance_recorded_notification(self):
        # Create a session
        session = LectureSession.objects.create(
            timetable_entry=self.entry,
            date=date.today(),
            status='SCHEDULED'
        )
        
        self.client.login(username="coord", password="pw")
        response = self.client.post(reverse('attendance:capture_attendance', args=[session.pk]), {
            'student_ids': [] # Mocking empty attendance
        })
        self.assertEqual(response.status_code, 302)
        
        # Check alert for lecturer
        self.assertTrue(Alert.objects.filter(user=self.lecturer, type='ATTENDANCE_RECORDED').exists())
        
        alert = Alert.objects.get(user=self.lecturer, type='ATTENDANCE_RECORDED')
        self.assertIn("recorded", alert.message)
        self.assertIn("coord", alert.message)

    def test_report_generated_notification(self):
        self.client.login(username="hod", password="pw")
        response = self.client.post(reverse('attendance:generate_report'), {
            'report_name': 'Semester High-Level Summary'
        })
        self.assertEqual(response.status_code, 302)
        
        # Check alert for HOD
        self.assertTrue(Alert.objects.filter(user=self.hod, type='REPORT_READY').exists())
        
        alert = Alert.objects.get(user=self.hod, type='REPORT_READY')
        self.assertIn("Semester High-Level Summary", alert.message)
        self.assertIn("is ready", alert.message)

    def test_missed_lecture_alert(self):
        # Triggering MISSED status would usually be a rule check or manual mark.
        # Let's manually trigger it to see if the rule works.
        session = LectureSession.objects.create(
            timetable_entry=self.entry,
            date=date.today(),
            status='MISSED'
        )
        
        from core.rules import check_missed_lecture
        check_missed_lecture(session)
        
        # Check alert for HOD
        self.assertTrue(Alert.objects.filter(user=self.hod, type='MISSED_LECTURE').exists())
        
        alert = Alert.objects.get(user=self.hod, type='MISSED_LECTURE')
        self.assertIn("missed scheduled lecture", alert.message)
