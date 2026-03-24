from datetime import timedelta
from django.db import transaction
from .models import LectureSession

def generate_sessions_for_range(timetable_entries, start_date, end_date):
    """
    Generates LectureSession objects for a list of TimetableEntry objects 
    within a specific date range.
    """
    sessions_to_create = []
    current_date = start_date
    
    # Map Django choices to python weekday() 
    # django: MON=MON, ..., SUN=SUN
    # weekday(): Mon=0, ..., Sun=6
    day_map = {
        'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 'FRI': 4, 'SAT': 5, 'SUN': 6
    }

    with transaction.atomic():
        while current_date <= end_date:
            weekday = current_date.weekday()
            # Find entries that occur on this weekday
            entries_on_day = timetable_entries.filter(
                day_of_week=[k for k, v in day_map.items() if v == weekday][0]
            )
            
            for entry in entries_on_day:
                # Check if session already exists for this entry/date
                if not LectureSession.objects.filter(timetable_entry=entry, date=current_date).exists():
                    sessions_to_create.append(
                        LectureSession(timetable_entry=entry, date=current_date)
                    )
            
            current_date += timedelta(days=1)
        
        LectureSession.objects.bulk_create(sessions_to_create)
    
    return len(sessions_to_create)
