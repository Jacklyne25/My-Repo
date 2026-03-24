import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def create_sysadmin():
    username = 'sysadmin'
    password = 'sysadminpassword'
    email = 'sysadmin@dsams.local'
    
    if User.objects.filter(username=username).exists():
        print(f"User '{username}' already exists.")
        user = User.objects.get(username=username)
        user.role = User.Role.SYSTEM_ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        print(f"Updated '{username}' to SYSTEM_ADMIN role and reset password.")
    else:
        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=User.Role.SYSTEM_ADMIN,
            is_staff=True,
            is_superuser=True
        )
        print(f"Successfully created user '{username}' with SYSTEM_ADMIN role.")

if __name__ == '__main__':
    create_sysadmin()
