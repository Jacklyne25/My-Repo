import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()

from users.models import User
from academic.models import Department

def cleanup():
    print("Starting cleanup of test data...")
    
    # 1. Delete Test Users
    # The script used usernames: alert_hod, alert_coord, alert_lecturer, alert_admin
    test_usernames = ['alert_hod', 'alert_coord', 'alert_lecturer', 'alert_admin']
    deleted_count, _ = User.objects.filter(username__in=test_usernames).delete()
    print(f"Deleted {deleted_count} test users.")
    
    # 2. Delete Test Department
    # The script created Department with code="ALT"
    try:
        dept = Department.objects.get(code="ALT")
        dept.delete()
        print(f"Deleted test department: {dept}")
    except Department.DoesNotExist:
        print("Test department 'ALT' not found (might have been deleted cascade).")

    try:
        dept = Department.objects.get(code="TD") # specific to automated test setup if any leaked
        dept.delete()
        print(f"Deleted test department: {dept}")
    except Department.DoesNotExist:
        pass

if __name__ == '__main__':
    cleanup()
