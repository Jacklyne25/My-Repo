from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from users.models import User
from academic.models import Department
from academic.services import BulkImportService

class AuthenticationFlowTest(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Computing", code="COMP")

    def test_bulk_import_creates_inactive_users(self):
        # Test student import
        csv_content = b"Registration No,Email,Name\nREG001,student@univ.ac.ug,John Doe"
        file = SimpleUploadedFile("students.csv", csv_content)
        BulkImportService.import_students(file, self.dept)
        
        user = User.objects.get(username="REG001")
        self.assertFalse(user.is_active)
        self.assertEqual(user.account_status, User.AccountStatus.NOT_ACTIVATED)
        self.assertFalse(user.has_usable_password())

    def test_account_activation_success(self):
        # Setup inactive user
        user = User.objects.create_user(
            username="STF001",
            email="lecturer@univ.ac.ug",
            is_active=False,
            account_status=User.AccountStatus.NOT_ACTIVATED
        )
        
        # Simulate activation via view logic (tested via Client)
        response = self.client.post('/users/activate/', {
            'username_or_email': 'lecturer@univ.ac.ug',
            'identifier': 'STF001',
            'password': 'NewPassword123',
            'confirm_password': 'NewPassword123'
        })
        
        self.assertEqual(response.status_code, 302) # Redirect to login
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(user.account_status, User.AccountStatus.ACTIVE)
        self.assertTrue(user.check_password('NewPassword123'))

    def test_account_activation_failure_mismatch(self):
        user = User.objects.create_user(
            username="STF002",
            email="wrong@univ.ac.ug",
            is_active=False
        )
        
        response = self.client.post('/users/activate/', {
            'username_or_email': 'wrong@univ.ac.ug',
            'identifier': 'WRONG_ID',
            'password': 'NewPassword123',
            'confirm_password': 'NewPassword123'
        })
        
        self.assertEqual(response.status_code, 200) # Re-render form with error
        user.refresh_from_db()
        self.assertFalse(user.is_active)
