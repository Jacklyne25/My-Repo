import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from academic.models import Department
from sysadmin.models import GlobalSettings, AuditLog
from core.models import Alert

User = get_user_model()

def configure_sysadmin_permissions():
    # 1. Create/Get the Group
    group_name = 'System Administrators'
    group, created = Group.objects.get_or_create(name=group_name)
    print(f"Group '{group_name}' {'created' if created else 'found'}.")

    # 2. Define allowed content types
    # Users, Departments, GlobalSettings, AuditLog, Alerts
    allowed_models = [
        (User, ['add', 'change', 'delete', 'view']),
        (Department, ['add', 'change', 'delete', 'view']),
        (GlobalSettings, ['add', 'change', 'view']), # Singleton, maybe no delete
        (AuditLog, ['view']), # Read-only
        (Alert, ['view', 'change', 'delete']), # Manage alerts
        (Group, ['add', 'change', 'delete', 'view']), # Manage groups (optional, but good for admin)
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

    # 4. Update the User
    username = 'sysadmin'
    try:
        user = User.objects.get(username=username)
        # CRITICAL: Remove superuser, keep staff
        user.is_superuser = False
        user.is_staff = True
        user.groups.add(group)
        user.save()
        print(f"User '{username}' updated: is_superuser=False, is_staff=True, Group='{group_name}' added.")
    except User.DoesNotExist:
        print(f"Error: User '{username}' does not exist. Please run the creation script first.")

if __name__ == '__main__':
    configure_sysadmin_permissions()
