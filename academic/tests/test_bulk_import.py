from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from users.models import User
from academic.models import Department, Program, CourseUnit
from academic.services import BulkImportService
from scheduling.models import Room, TimetableEntry, LectureSession
from sysadmin.models import GlobalSettings
from django.utils import timezone
from datetime import timedelta

class BulkImportTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Test Dept", code="TD")
        self.prog = Program.objects.create(name="Prog", code="P1", department=self.dept)
        self.course = CourseUnit.objects.create(name="Course", code="C1")
        self.room = Room.objects.create(name="R1", capacity=10)
        self.lecturer = User.objects.create_user(username="lecturer", role='LECTURER', department=self.dept)
        
        # Setup Semester
        start = timezone.now().date()
        end = start + timedelta(days=30)
        GlobalSettings.objects.create(semester_start=start, semester_end=end)

    def test_import_students(self):
        csv_content = b"username,email,first_name,last_name,registration no\nstudent1,s1@test.com,Job,Doe,REG100\nstudent2,s2@test.com,Jane,Doe,REG101"
        # Note: Updated service uses 'Registration No' as username. 
        # Updating content to match standardized schema
        csv_content = b"Registration No,Email,Name\nREG100,s1@test.com,Job Doe"
        file = SimpleUploadedFile("students.csv", csv_content)
        
        results = BulkImportService.import_students(file, self.dept)
        
        self.assertEqual(results['success'], 1)
        self.assertTrue(User.objects.filter(username='REG100').exists())

    def test_import_lecturers(self):
        # Staff ID, Full Name, Email, Phone, Department, Employment Type, Status, Specialization, Max Weekly Load
        csv_content = b"Staff ID,Full Name,Email,Phone,Department,Employment Type,Status,Specialization,Max Weekly Load\nSTF001,Dr. Test,doc@test.com,077123,Computing,FULL_TIME,Active,AI,15"
        file = SimpleUploadedFile("lecturers.csv", csv_content)
        
        results = BulkImportService.import_lecturers(file, self.dept)
        
        self.assertEqual(results['success'], 1)
        user = User.objects.get(username='STF001')
        self.assertEqual(user.role, 'LECTURER')
        self.assertEqual(user.phone_number, '077123')
        # Check Profile
        self.assertTrue(hasattr(user, 'lecturer_profile'))
        self.assertEqual(user.lecturer_profile.specialization, 'AI')
        self.assertEqual(user.lecturer_profile.max_weekly_load, 15)

    def test_import_timetable_success(self):
        # Format: Department, Programme, Day, Time, Course, Course Unit, Lecturer, Venue
        # Dept=Test Dept(by default), Prog=P1, CourseUnit=C1, Lecturer=lecturer, Venue=R1
        csv_content = f"Department,Programme,Day,Time,Course,Course Unit,Lecturer,Venue\nTest Dept,Day,MON,09:00-11:00,P1,C1,lecturer,R1".encode('utf-8')
        file = SimpleUploadedFile("timetable.csv", csv_content)
        
        results = BulkImportService.import_timetable(file, self.dept)
        
        self.assertEqual(results['success'], 1, f"Failed with errors: {results['errors']}")
        self.assertTrue(TimetableEntry.objects.filter(course_unit=self.course).exists())
        # Check sessions generated
        self.assertTrue(LectureSession.objects.filter(timetable_entry__course_unit=self.course).exists())

    def test_import_timetable_validation_error(self):
        # Invalid Room
        csv_content = f"Department,Programme,Day,Time,Course,Course Unit,Lecturer,Venue\nTest Dept,Day,MON,09:00-11:00,P1,C1,lecturer,INVALID_ROOM".encode('utf-8')
        file = SimpleUploadedFile("timetable.csv", csv_content)
        
        results = BulkImportService.import_timetable(file, self.dept)
        
        self.assertEqual(results['failed'], 1)
        self.assertIn("Object not found", results['errors'][0])

    def test_import_course_units(self):
        csv_content = b"Name,Code,Program Codes\nIntro to CS,CS101,P1"
        file = SimpleUploadedFile("course_units.csv", csv_content)
        
        results = BulkImportService.import_course_units(file, self.dept)
        
        self.assertEqual(results['success'], 1)
        self.assertTrue(CourseUnit.objects.filter(code='CS101').exists())
        cu = CourseUnit.objects.get(code='CS101')
        self.assertIn(self.prog, cu.programs.all())

    def test_import_rooms(self):
        csv_content = b"Name,Capacity\nLecture Hall 1,150"
        file = SimpleUploadedFile("rooms.csv", csv_content)
        
        results = BulkImportService.import_rooms(file)
        
        self.assertEqual(results['success'], 1)
        self.assertTrue(Room.objects.filter(name='Lecture Hall 1', capacity=150).exists())

    def test_import_course_groups(self):
        csv_content = b"Name,Program Code\nYear 1 Group A,P1"
        file = SimpleUploadedFile("course_groups.csv", csv_content)
        
        results = BulkImportService.import_course_groups(file, self.dept)
        from academic.models import CourseGroup
        self.assertEqual(results['success'], 1)
        self.assertTrue(CourseGroup.objects.filter(name='Year 1 Group A', program=self.prog).exists())
