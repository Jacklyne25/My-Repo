from django.test import TestCase, Client
from django.urls import reverse
from users.models import User
from academic.models import Department, Faculty

class PasswordResetTests(TestCase):
    def setUp(self):
        self.faculty = Faculty.objects.create(name="IT", code="IT")
        self.dept = Department.objects.create(name="CS", code="CS", faculty=self.faculty)
        self.hod = User.objects.create_user(username="hod", password="pw", role="HOD", department=self.dept)
        self.student = User.objects.create_user(username="student", password="pw", role="STUDENT", department=self.dept, account_status="NOT_ACTIVATED")
        self.client = Client()

    def test_hod_activation_forces_reset(self):
        # 1. HOD activates student
        self.client.login(username="hod", password="pw")
        self.client.post(reverse('users:activate_account'), {
            'action': 'quick_activate',
            'user_id': self.student.id
        })
        self.student.refresh_from_db()
        self.assertTrue(self.student.requires_password_reset)
        
        # 2. Student logs in and is redirected
        self.client.logout()
        # Note: default password is 'welcome@DSAMS' for HOD activation
        self.client.login(username="student", password="welcome@DSAMS")
        response = self.client.get(reverse('users:home'), follow=True)
        # Check if redirected to reset page
        self.assertContains(response, "Account Security")
        self.assertEqual(response.resolver_match.view_name, 'users:password_reset_first_login')

    def test_self_activation_forces_reset(self):
        # 1. Student self-activates with ID only
        response = self.client.post(reverse('users:activate_account'), {
            'username': 'student',
        })
        self.student.refresh_from_db()
        self.assertEqual(self.student.account_status, "ACTIVE")
        self.assertTrue(self.student.requires_password_reset)
        
        # 2. Verify auto-login and redirection to security setup
        # The view redirects to 'users:home' after auto-login, which then forces password reset
        response = self.client.get(reverse('users:home'), follow=True)
        self.assertContains(response, "Account Security")
        self.assertEqual(response.resolver_match.view_name, 'users:password_reset_first_login')

