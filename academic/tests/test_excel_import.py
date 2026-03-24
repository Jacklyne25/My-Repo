from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from users.models import User
from academic.models import Department, Program, CourseUnit
from academic.services import BulkImportService
import pandas as pd
import io

class ExcelImportTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.dept = Department.objects.create(name="Computing", code="CMP")
        self.user = User.objects.create_user(
            username="admin", 
            role=User.Role.HOD, 
            department=self.dept,
            is_active=True,
            account_status=User.AccountStatus.ACTIVE
        )
        self.user.set_password("password123")
        self.user.save()
        self.client.login(username="admin", password="password123")

    def test_download_template_xlsx(self):
        url = reverse('academic:download_template', kwargs={'type': 'students'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(response['Content-Disposition'].endswith('.xlsx"'))
        
        # Verify Excel content
        df = pd.read_excel(io.BytesIO(response.content))
        self.assertIn('Registration No', df.columns)
        self.assertEqual(df.iloc[0]['Name'], 'John Doe')

    def test_import_students_xlsx(self):
        # Create Excel file
        data = {
            'Registration No': ['REG200', 'REG201'],
            'Email': ['s200@test.com', 's201@test.com'],
            'Name': ['Student 200', 'Student 201']
        }
        df = pd.DataFrame(data)
        out = io.BytesIO()
        df.to_excel(out, index=False)
        out.seek(0)
        
        file = SimpleUploadedFile("students.xlsx", out.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        results = BulkImportService.import_students(file, self.dept)
        
        self.assertEqual(results['success'], 2)
        self.assertTrue(User.objects.filter(username='REG200').exists())
        self.assertTrue(User.objects.filter(username='REG201').exists())

    def test_import_unsupported_format(self):
        file = SimpleUploadedFile("test.txt", b"some text", content_type="text/plain")
        results = BulkImportService.import_students(file, self.dept)
        self.assertTrue(any("Unsupported file format" in err for err in results['errors']))
