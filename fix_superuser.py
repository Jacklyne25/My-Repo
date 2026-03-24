import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()

from users.models import User

def fix_permissions():
    # Find all HODs who are superusers
    hods = User.objects.filter(role=User.Role.HOD, is_superuser=True)
    
    for hod in hods:
        print(f"Demoting HOD '{hod.username}' from Superuser to Staff...")
        hod.is_superuser = False
        hod.is_staff = True # Keep access to admin panel
        hod.save()
        print("Done.")

    # Also check other roles
    others = User.objects.filter(is_superuser=True).exclude(role=User.Role.SYSTEM_ADMIN).exclude(username='sysadmin')
    # Maybe original admin is 'admin' with Role HOD?
    for u in others:
       print(f"Demoting user '{u.username}' (Role: {u.role}) from Superuser...")
       u.is_superuser = False
       u.is_staff = True
       u.save()

if __name__ == '__main__':
    fix_permissions()
