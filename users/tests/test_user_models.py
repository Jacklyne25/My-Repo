import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
def test_create_user_with_role():
    user = User.objects.create_user(
        username='testuser',
        password='testpassword',
        role='STUDENT'
    )
    assert user.role == 'STUDENT'
    assert user.is_student() is True
    assert user.is_hod() is False

@pytest.mark.django_db
def test_user_roles_choices():
    user = User.objects.create_user(
        username='hoduser',
        password='testpassword',
        role='HOD'
    )
    assert user.role == 'HOD'
    assert user.is_hod() is True
