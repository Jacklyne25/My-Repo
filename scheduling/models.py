from django.db import models
from django.conf import settings
from academic.models import CourseUnit, Program
from django.core.exceptions import ValidationError

class Room(models.Model):
    name = models.CharField(max_length=50, unique=True)
    capacity = models.PositiveIntegerField()

    def __str__(self):
        return self.name


class SchedulingParameters(models.Model):
    class StudyTime(models.TextChoices):
        DAY = 'DAY', 'Day'
        EVENING = 'EVENING', 'Evening'
        WEEKEND = 'WEEKEND', 'Weekend'

    class Cohort(models.TextChoices):
        EASTER = 'EASTER', 'Easter Intake'
        TRINITY = 'TRINITY', 'Trinity Intake'
        ADVENT = 'ADVENT', 'Advent Intake'

    department = models.ForeignKey(
        'academic.Department',
        on_delete=models.CASCADE,
        related_name='scheduling_params'
    )
    study_time = models.CharField(max_length=10, choices=StudyTime.choices, default=StudyTime.DAY)
    cohort = models.CharField(max_length=10, choices=Cohort.choices, default=Cohort.EASTER)
    academic_year = models.CharField(max_length=20, default='2026/2027')
    # Comma-separated e.g. 'MON,TUE,WED,THU,FRI'
    available_days = models.CharField(max_length=50, default='MON,TUE,WED,THU,FRI')
    day_start_time = models.TimeField(default='08:00')
    day_end_time = models.TimeField(default='17:00')
    slot_duration_hours = models.PositiveIntegerField(default=2)
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def days_list(self):
        return [d.strip() for d in self.available_days.split(',') if d.strip()]

    def get_timeslots(self):
        """Return list of (start_time, end_time) tuples based on parameters."""
        from datetime import datetime, timedelta, time
        slots = []
        current = datetime.combine(datetime.today(), self.day_start_time)
        end = datetime.combine(datetime.today(), self.day_end_time)
        delta = timedelta(hours=self.slot_duration_hours)
        
        lunch_start = time(12, 0)
        lunch_end = time(14, 0)
        
        while current + delta <= end:
            slot_start = current.time()
            slot_end = (current + delta).time()
            
            # Skip lunch period 12:00 - 14:00
            if lunch_start <= slot_start < lunch_end:
                current += delta
                continue
                
            slots.append((slot_start, slot_end))
            current += delta
        return slots

    def __str__(self):
        return f"{self.get_study_time_display()} ({self.get_cohort_display()}) {self.academic_year} – {self.department.code}"

class TimetableEntry(models.Model):
    class DayOfWeek(models.TextChoices):
        MONDAY = 'MON', 'Monday'
        TUESDAY = 'TUE', 'Tuesday'
        WEDNESDAY = 'WED', 'Wednesday'
        THURSDAY = 'THU', 'Thursday'
        FRIDAY = 'FRI', 'Friday'
        SATURDAY = 'SAT', 'Saturday'
        SUNDAY = 'SUN', 'Sunday'

    class TeachingMode(models.TextChoices):
        PHYSICAL = 'PHYSICAL', 'Physical'
        ONLINE = 'ONLINE', 'Online'
        
    course_unit = models.ForeignKey(CourseUnit, on_delete=models.CASCADE)
    lecturer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    program = models.ForeignKey(Program, on_delete=models.CASCADE)
    course_group = models.ForeignKey('academic.CourseGroup', on_delete=models.CASCADE, null=True, blank=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True)
    teaching_mode = models.CharField(max_length=15, choices=TeachingMode.choices, default=TeachingMode.PHYSICAL)
    scheduling_params = models.ForeignKey(SchedulingParameters, on_delete=models.CASCADE, related_name='entries', null=True, blank=True)
    day_of_week = models.CharField(max_length=3, choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def clean(self):
        # 1. Check if lecturer is actually a lecturer or admin allowed to teach
        allowed_roles = ['LECTURER', 'HOD', 'SYSTEM_ADMIN', 'FACULTY_ADMIN', 'ADMIN_ASSISTANT']
        if self.lecturer.role not in allowed_roles:
            raise ValidationError({'lecturer': f"The assigned user role '{self.lecturer.role}' is not allowed to teach."})

        # 2. Workload Validation
        from core.constraints import WorkloadManager
        # Only check workload if it's a new entry (to avoid blocking existing valid entries during minor edits)
        if not self.pk:
            can_assign, message = WorkloadManager.validate_assignment(
                self.lecturer, 
                course_unit=self.course_unit,
                day=self.day_of_week,
                start=self.start_time,
                end=self.end_time
            )
            if not can_assign:
                raise ValidationError({'lecturer': message})

        # 3. Rule: Each course unit must have exactly two sessions per week PER GROUP
        # If we are adding a 3rd session for the same group, block it.
        # ALSO: Rule - Two sessions of the same unit cannot be on the same day
        existing_sessions = TimetableEntry.objects.filter(
            course_unit=self.course_unit, 
            course_group=self.course_group
        ).exclude(pk=self.pk)
        
        if existing_sessions.count() >= 2:
            raise ValidationError({'course_unit': "Each course unit is limited to exactly two sessions per week for a specific class group."})
        
        if existing_sessions.filter(day_of_week=self.day_of_week).exists():
            raise ValidationError({'day_of_week': f"Each course unit can have only one session per day. A session for {self.course_unit.code} is already scheduled for this day."})

        # 4. Check for Room Conflicts
        if self.teaching_mode == self.TeachingMode.PHYSICAL:
            if not self.room:
                raise ValidationError({'room': "A physical lecture must be assigned to a room."})
                
            conflicting_room = TimetableEntry.objects.filter(
                day_of_week=self.day_of_week,
                room=self.room,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time
            ).exclude(pk=self.pk)
            
            if hasattr(self, 'course_unit') and hasattr(self, 'lecturer'):
                conflicting_room = conflicting_room.exclude(course_unit=self.course_unit, lecturer=self.lecturer)
                
            if conflicting_room.exists():
                raise ValidationError("Room conflict: This room is already occupied during this time.")

        # 5. Check for Lecturer Conflicts
        conflicting_lecturer = TimetableEntry.objects.filter(
            day_of_week=self.day_of_week,
            lecturer=self.lecturer,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exclude(pk=self.pk)
        
        if hasattr(self, 'course_unit'):
            conflicting_lecturer = conflicting_lecturer.exclude(course_unit=self.course_unit)
            
        if conflicting_lecturer.exists():
            raise ValidationError("Lecturer conflict: This lecturer is already scheduled during this time.")


    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.course_unit.code} - {self.day_of_week} ({self.start_time}-{self.end_time})"

class LectureSession(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        CONDUCTED = 'CONDUCTED', 'Conducted'
        SUBMITTED = 'SUBMITTED', 'Conducted & Attendance submitted'
        PENDING_VERIFICATION = 'PENDING_VERIFICATION', 'Pending Verification'
        APPROVED = 'APPROVED', 'Approved'
        AUTO_CONFIRMED = 'AUTO_CONFIRMED', 'Auto-Confirmed'
        MISSED = 'MISSED', 'Missed'
        RESCHEDULED = 'RESCHEDULED', 'Rescheduled'
        LECTURER_CONFIRMED = 'LECTURER_CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class RecordingMethod(models.TextChoices):
        DIGITAL = 'DIGITAL', 'Direct System Entry'
        PAPER = 'PAPER', 'Paper-based Upload'

    timetable_entry = models.ForeignKey(TimetableEntry, on_delete=models.CASCADE, related_name='sessions')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    recording_method = models.CharField(
        max_length=10, 
        choices=RecordingMethod.choices, 
        default=RecordingMethod.DIGITAL
    )
    signed_sheet = models.FileField(upload_to='attendance_sheets/', null=True, blank=True)
    lecturer_has_viewed = models.BooleanField(default=False, help_text="Has the lecturer opened the attendance list for review?")
    actual_duration = models.DecimalField(max_digits=4, decimal_places=2, default=2.00)
    verification_notes = models.TextField(blank=True, null=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_sessions'
    )
    verification_timestamp = models.DateTimeField(null=True, blank=True)

    def mark_conducted(self):
        if self.status == self.Status.SCHEDULED:
            self.status = self.Status.CONDUCTED
            self.save()

    def submit_attendance(self):
        self.status = self.Status.PENDING_VERIFICATION
        self.save()

    def approve_attendance(self):
        if self.status in [self.Status.PENDING_VERIFICATION, self.Status.SUBMITTED]:
            self.status = self.Status.CONDUCTED
            self.save()
            # Check for low attendance for all students in this session when approved
            from core.rules import check_low_attendance
            from attendance.models import AttendanceRecord
            for record in AttendanceRecord.objects.filter(session=self):
                check_low_attendance(record.student)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.status == self.Status.MISSED:
            from core.rules import check_missed_lecture
            check_missed_lecture(self)

    def __str__(self):
        return f"{self.timetable_entry.course_unit.code} on {self.date}"

class SchedulingRun(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    class Mode(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual'
        AUTO = 'AUTO', 'Auto'

    department = models.ForeignKey(
        'academic.Department',
        on_delete=models.CASCADE,
        related_name='scheduling_runs'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.MANUAL)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.mode} run for {self.department.code} @ {self.created_at:%Y-%m-%d %H:%M}"
