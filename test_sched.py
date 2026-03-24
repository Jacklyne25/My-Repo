import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import Client
from users.models import User
import traceback

def run():
    c = Client()
    # Attempt to find user by email or username
    u = User.objects.filter(email='admin@example.com').first()
    if not u:
        u = User.objects.filter(username='admin').first()
        
    if not u:
        print("HOD user not found.")
        return

    u.set_password('password123')
    u.save()

    # Try login
    # The custom User model might use email as the USERNAME_FIELD
    login_success = c.login(email=u.email, password='password123')
    if not login_success:
         login_success = c.login(username=u.username, password='password123')

    print(f"Login success: {login_success} for user: {u}")

    try:
        response = c.get('/scheduling/')
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Successfully rendered styling without errors!")
        else:
            print(response.content.decode('utf-8')[:2000])
    except Exception as e:
        print("Exception raised:")
        traceback.print_exc()

if __name__ == '__main__':
    run()
