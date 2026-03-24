import pytest
from django.urls import reverse
from django.test import Client
from django.contrib.auth import get_user_model
from academic.models import Department

User = get_user_model()

@pytest.fixture
def departments(db):
    dept_it = Department.objects.create(name='IT', code='IT001')
    dept_cs = Department.objects.create(name='CS', code='CS001')
    return dept_it, dept_cs

@pytest.fixture
def hod_it(db, departments):
    return User.objects.create_user(
        username='hod_it', 
        password='password', 
        role='HOD', 
        department=departments[0]
    )

@pytest.fixture
def student_it(db, departments):
    return User.objects.create_user(
        username='student_it', 
        password='password', 
        role='STUDENT', 
        department=departments[0]
    )

@pytest.fixture
def student_cs(db, departments):
    return User.objects.create_user(
        username='student_cs', 
        password='password', 
        role='STUDENT', 
        department=departments[1]
    )

@pytest.mark.django_db
def test_hod_can_only_see_users_in_their_department(hod_it, student_it, student_cs):
    client = Client()
    client.force_login(hod_it)
    response = client.get(reverse('users:user_list'))
    
    assert response.status_code == 200
    content = response.content.decode()
    assert 'student_it' in content
    assert 'student_cs' not in content
    assert 'IT' in content

@pytest.mark.django_db
def test_non_hod_cannot_access_user_list(student_it):
    client = Client()
    client.force_login(student_it)
    response = client.get(reverse('users:user_list'))
    assert response.status_code == 403
