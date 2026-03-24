import os
import django
from django.contrib.auth import authenticate

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()

from users.models import User

username = 'admin'
password = 'password123'

user = authenticate(username=username, password=password)
if user is not None:
    print(f"SUCCESS: User {username} authenticated successfully.")
    print(f"User role: {user.role}")
    print(f"User is_active: {user.is_active}")
    print(f"User account_status: {user.account_status}")
else:
    print(f"FAILURE: Authentication failed for user {username}.")
    # Check if user exists
    try:
        u = User.objects.get(username=username)
        print(f"User exists. is_active: {u.is_active}, account_status: {u.account_status}")
        # Try authenticate with email
        user_email = authenticate(username=u.email, password=password)
        if user_email:
            print(f"SUCCESS with email: {u.email}")
        else:
            print(f"FAILURE even with email: {u.email}")
    except User.DoesNotExist:
        print("User does not exist.")
