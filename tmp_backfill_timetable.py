import django
import os
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dsams.settings')
django.setup()

from scheduling.models import TimetableEntry, SchedulingParameters

def backfill():
    # Attempt to find the active parameters for each department
    params_map = {p.department_id: p for p in SchedulingParameters.objects.filter(is_active=True)}
    
    entries = TimetableEntry.objects.filter(scheduling_params__isnull=True)
    count = 0
    for entry in entries:
        dept_id = entry.program.department_id
        if dept_id in params_map:
            entry.scheduling_params = params_map[dept_id]
            entry.save()
            count += 1
    
    print(f"Successfully backfilled {count} entries.")

if __name__ == "__main__":
    backfill()
