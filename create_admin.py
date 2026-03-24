import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()

from users.models import User

username = 'admin'
email = 'admin@example.com'
password = 'adminpassword'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password, role='HOD')
    print(f"Superuser '{username}' (Role: HOD) created successfully.")
else:
    print(f"User '{username}' already exists.")
