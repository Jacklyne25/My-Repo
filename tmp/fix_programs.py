import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()

from users.models import User
from django.db.models import F

# Backfill program from course_group for all students/coordinators
users_to_fix = User.objects.filter(program__isnull=True, course_group__isnull=False)
count = 0
for u in users_to_fix:
    u.program = u.course_group.program
    u.save()
    count += 1

print(f"Successfully backfilled 'program' for {count} users.")
