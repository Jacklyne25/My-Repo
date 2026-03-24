import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from academic.models import Department, Program, CourseUnit
from scheduling.models import Room, TimetableEntry, LectureSession
from attendance.models import AttendanceRecord
from core.models import Alert

User = get_user_model()

def configure_hod_permissions():
    # 1. Create/Get the Group
    group_name = 'Heads of Department'
    group, created = Group.objects.get_or_create(name=group_name)
    print(f"Group '{group_name}' {'created' if created else 'found'}.")

    # 2. Define allowed content types
    # HOD needs access to their domain
    allowed_models = [
        # Academic (Programs, Courses - Full Control)
        (Program, ['add', 'change', 'delete', 'view']),
        (CourseUnit, ['add', 'change', 'delete', 'view']),
        
        # Academic (Department - View/Change ONLY, No Add/Delete)
        (Department, ['change', 'view']), 
        
        # Users (Managed via custom admin logic, but need validation permissions)
        (User, ['add', 'change', 'delete', 'view']),
        
        # Scheduling (Full Control)
        (Room, ['add', 'change', 'delete', 'view']),
        (TimetableEntry, ['add', 'change', 'delete', 'view']),
        (LectureSession, ['add', 'change', 'delete', 'view']),
        
        # Attendance (Full Control)
        (AttendanceRecord, ['add', 'change', 'delete', 'view']),
        
        # Alerts (Manage own)
        (Alert, ['change', 'delete', 'view']),
    ]

    permissions_to_add = []
    for model_class, actions in allowed_models:
        ct = ContentType.objects.get_for_model(model_class)
        for action in actions:
            codename = f'{action}_{model_class._meta.model_name}'
            try:
                perm = Permission.objects.get(content_type=ct, codename=codename)
                permissions_to_add.append(perm)
            except Permission.DoesNotExist:
                print(f"Warning: Permission {codename} not found.")

    # 3. Assign permissions to group
    group.permissions.set(permissions_to_add)
    print(f"Assigned {len(permissions_to_add)} permissions to group '{group_name}'.")

    # 4. Assign Group to HOD Users
    hods = User.objects.filter(role=User.Role.HOD)
    for hod in hods:
        hod.groups.add(group)
        hod.is_staff = True # Ensure they can login to admin
        hod.save()
        print(f"Added HOD '{hod.username}' to group.")

if __name__ == '__main__':
    configure_hod_permissions()
