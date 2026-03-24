import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from sysadmin.models import GlobalSettings, AuditLog
from django.core.exceptions import ValidationError

User = get_user_model()

@pytest.mark.django_db
class TestSysAdminAccess(TestCase):
    def setUp(self):
        self.client = Client()
        self.sysadmin = User.objects.create_user(username='sysadmin', password='password', role=User.Role.SYSTEM_ADMIN)
        self.hod = User.objects.create_user(username='hod', password='password', role=User.Role.HOD)
        self.url = reverse('sysadmin:dashboard')

    def test_sysadmin_can_access_dashboard(self):
        self.client.force_login(self.sysadmin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_hod_cannot_access_dashboard(self):
        self.client.force_login(self.hod)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

@pytest.mark.django_db
class TestGlobalSettings(TestCase):
    def test_singleton_enforcement(self):
        GlobalSettings.objects.create(attendance_threshold=80.0)
        # Try to create a second one
        with self.assertRaises(ValidationError):
            GlobalSettings(attendance_threshold=70.0).save()
            
    def test_default_values(self):
        settings = GlobalSettings.objects.create()
        self.assertEqual(settings.attendance_threshold, 75.00)

@pytest.mark.django_db
class TestAuditLog(TestCase):
    def test_log_creation(self):
        user = User.objects.create_user(username='actor', role=User.Role.SYSTEM_ADMIN)
        log = AuditLog.objects.create(
            actor=user,
            action='TEST_ACTION',
            metadata={'ip': '127.0.0.1'}
        )
        self.assertEqual(log.action, 'TEST_ACTION')
        self.assertEqual(log.actor, user)
