from django.test import TestCase
from users.models import User
from academic.models import Department, Program, CourseUnit
from scheduling.models import Room, TimetableEntry, LectureSession
from core.models import Alert
from core.services import AlertService
from django.utils import timezone
from datetime import timedelta

class AlertServiceTest(TestCase):
    def setUp(self):
        # Setup clean data
        self.dept = Department.objects.create(name="Test Dept", code="TD")
        self.hod = User.objects.create_user(username="hod", role=User.Role.HOD, department=self.dept)
        self.coord = User.objects.create_user(username="coord", role=User.Role.COORDINATOR, department=self.dept)
        self.lecturer = User.objects.create_user(username="lecturer", role=User.Role.LECTURER, department=self.dept)
        self.student = User.objects.create_user(username="student", role=User.Role.STUDENT, department=self.dept)
        self.prog = Program.objects.create(name="Prog", code="P1", department=self.dept)
        self.course = CourseUnit.objects.create(name="Course", code="C1")
        self.course.programs.add(self.prog)
        self.room = Room.objects.create(name="R1", capacity=10)
        
        self.entry = TimetableEntry.objects.create(
            course_unit=self.course,
            lecturer=self.lecturer,
            program=self.prog,
            room=self.room,
            day_of_week='MON',
            start_time='10:00',
            end_time='12:00'
        )

    def test_compliance_alert(self):
        # Create 4 missed sessions
        for i in range(4):
            LectureSession.objects.create(
                timetable_entry=self.entry,
                date=timezone.now().date(),
                status=LectureSession.Status.MISSED
            )
            
        AlertService.check_compliance_and_integrity()
        
        alert = Alert.objects.filter(user=self.hod, category=Alert.Category.COMPLIANCE).first()
        self.assertIsNotNone(alert)
        self.assertIn("missed 4 lectures", alert.message)

    def test_integrity_alert(self):
        # Create stale conducted session
        LectureSession.objects.create(
            timetable_entry=self.entry,
            date=timezone.now().date() - timedelta(days=2),
            status=LectureSession.Status.CONDUCTED
        )
        
        AlertService.check_compliance_and_integrity()
        
        alert = Alert.objects.filter(user=self.coord, category=Alert.Category.INTEGRITY).first()
        self.assertIsNotNone(alert)
        self.assertIn("not been submitted", alert.message)

    def test_security_alert(self):
        AlertService.notify_security_breach(ip_address="127.0.0.1", details="Test")
        # Need a sysadmin
        sysadmin = User.objects.create_user(username="sysadmin", role=User.Role.SYSTEM_ADMIN)
        AlertService.notify_security_breach(ip_address="127.0.0.1", details="Test")
        
        alert = Alert.objects.filter(user=sysadmin, category=Alert.Category.SECURITY).first()
        self.assertIsNotNone(alert)
