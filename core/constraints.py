from django.db.models import Sum
from users.models import User, LecturerProfile
from academic.models import CourseUnit
from scheduling.models import TimetableEntry, LectureSession
from core.models import Alert

class WorkloadManager:
    """Enforces teaching load policies based on staff roles."""
    
    POLICY_LIMITS = {
        User.Role.LECTURER: (16, 20),
        User.Role.HOD: (8, 12),
        User.Role.SYSTEM_ADMIN: (8, 12),
        User.Role.FACULTY_ADMIN: (8, 12),
        User.Role.ADMIN_ASSISTANT: (0, 4),
    }

    @staticmethod
    def get_lecturer_limits(user):
        """Returns (min, max) hours allowed for a user."""
        # Start with role-based defaults
        min_load, max_load = WorkloadManager.POLICY_LIMITS.get(user.role, (0, 0))
        
        if hasattr(user, 'lecturer_profile'):
            profile = user.lecturer_profile
            
            # If it's a standard Lecturer, use employment type defaults
            if user.role == User.Role.LECTURER:
                if profile.employment_type == LecturerProfile.EmploymentType.FULL_TIME:
                    min_load, max_load = 16, 20
                elif profile.employment_type == LecturerProfile.EmploymentType.PART_TIME:
                    min_load, max_load = 12, 16

            # If profile has specific overrides that differ from defaults, they could be used here.
            # But for now, we enforce the HOD interview policies strictly.
            # If we want to allow manual overrides in the profile, we'd check if they were edited.
            # We'll allow the profile to override ONLY if it's NOT the default 16/20.
            if profile.max_weekly_load not in [20, 0]:
                max_load = profile.max_weekly_load
            if profile.min_weekly_load not in [16, 0]:
                min_load = profile.min_weekly_load

        return min_load, max_load


    @staticmethod
    def calculate_current_load(user):
        """Calculates total weekly hours assigned in the timetable."""
        # Each TimetableEntry is 2 hours as per system rules
        # Use distinct on day_of_week, start_time, and course_unit to count combined classes once
        entries_count = TimetableEntry.objects.filter(lecturer=user).values('day_of_week', 'start_time', 'course_unit').distinct().count()
        return entries_count * 2

    @staticmethod
    def validate_assignment(user, course_unit=None, day=None, start=None, end=None):
        """Checks if a lecturer can take more courses."""
        current_load = WorkloadManager.calculate_current_load(user)
        min_load, max_load = WorkloadManager.get_lecturer_limits(user)
        
        # Default duration to 2 if not provided
        duration = 2
        if start and end:
            # Simple duration calculation
            try:
                from datetime import datetime, date
                d1 = datetime.combine(date.today(), end)
                d2 = datetime.combine(date.today(), start)
                duration = (d1 - d2).seconds / 3600
            except:
                pass

        # If lecturer is ALREADY teaching this specific course unit at this specific time,
        # then adding another group (shared session) does NOT increase their workload.
        if day and start and course_unit:
            already_scheduled = TimetableEntry.objects.filter(
                lecturer=user,
                course_unit=course_unit,
                day_of_week=day,
                start_time=start
            ).exists()
            if already_scheduled:
                # Load is already accounted for in calculate_current_load
                if current_load <= max_load:
                    return True, "Workload within limits (shared session)."
                else:
                    return False, f"Staff is already over their limit of {max_load} hours."

        if current_load + duration > max_load:
            return False, f"Assignment exceeds maximum workload of {max_load} hours for this role."
        
        return True, "Workload within limits."

class CourseProgressTracker:
    """Tracks and alerts on contact hour requirements."""
    
    @staticmethod
    def check_progress(course_unit):
        """Compares completed vs required hours and issues alerts if needed."""
        completed = course_unit.completed_contact_hours
        required = course_unit.required_contact_hours
        
        # Example check at mid-semester or end-of-semester (mocking logic here)
        if completed < required:
            # Generate alert for the lecturer
            if course_unit.lecturer:
                Alert.objects.get_or_create(
                    user=course_unit.lecturer,
                    category=Alert.Category.REMINDER,
                    type="HOUR_LAG",
                    message=f"Course {course_unit.code} has only {completed}/{required} contact hours completed.",
                    defaults={'severity': Alert.Severity.WARNING}
                )
        return completed, required
