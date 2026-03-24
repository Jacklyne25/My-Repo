import pytest
from django.urls import reverse
from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def student_user(db):
    return User.objects.create_user(username='student', password='password', role='STUDENT')

@pytest.fixture
def hod_user(db):
    return User.objects.create_user(username='hod', password='password', role='HOD')

@pytest.fixture
def coordinator_user(db):
    return User.objects.create_user(username='coordinator', password='password', role='COORDINATOR')

@pytest.fixture
def lecturer_user(db):
    return User.objects.create_user(username='lecturer', password='password', role='LECTURER')

@pytest.mark.django_db
def test_student_cannot_access_hod_dashboard(student_user):
    client = Client()
    client.force_login(student_user)
    response = client.get(reverse('users:hod_dashboard'))
    assert response.status_code == 403

@pytest.mark.django_db
def test_hod_can_access_hod_dashboard(hod_user):
    client = Client()
    client.force_login(hod_user)
    response = client.get(reverse('users:hod_dashboard'))
    assert response.status_code == 200
    assert response.content.decode() == "HOD Dashboard"

@pytest.mark.django_db
def test_student_can_access_student_dashboard(student_user):
    client = Client()
    client.force_login(student_user)
    response = client.get(reverse('users:student_dashboard'))
    assert response.status_code == 200
    assert response.content.decode() == "Student Dashboard"
