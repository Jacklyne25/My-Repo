from django.db import models
from django.conf import settings

class Alert(models.Model):
    class AlertType(models.TextChoices):
        LOW_ATTENDANCE = 'LOW_ATTENDANCE', 'Low Attendance'
        MISSED_LECTURE = 'MISSED_LECTURE', 'Missed Lecture'
        PENDING_SUBMISSION = 'PENDING_SUBMISSION', 'Pending Submission'
        SYSTEM = 'SYSTEM', 'System Alert'

    class Category(models.TextChoices):
        COMPLIANCE = 'COMPLIANCE', 'Compliance' # HOD
        PERFORMANCE = 'PERFORMANCE', 'Performance' # HOD
        STRUCTURAL = 'STRUCTURAL', 'Structural' # HOD
        SECURITY = 'SECURITY', 'Security' # SysAdmin
        SYSTEM_HEALTH = 'SYSTEM_HEALTH', 'System Health' # SysAdmin
        INTEGRITY = 'INTEGRITY', 'Integrity' # Coordinator
        STUDENT_RISK = 'STUDENT_RISK', 'Student Risk' # Coordinator
        OPERATIONAL = 'OPERATIONAL', 'Operational' # Coordinator
        REMINDER = 'REMINDER', 'Reminder' # Lecturer
        TIMETABLE = 'TIMETABLE', 'Timetable' # Lecturer/Student
        GENERAL = 'GENERAL', 'General' # Student

    class Severity(models.TextChoices):
        INFO = 'INFO', 'Information'
        WARNING = 'WARNING', 'Warning'
        CRITICAL = 'CRITICAL', 'Critical'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alerts')
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    type = models.CharField(max_length=50) # Expanded from choices for flexibility
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} for {self.user.username}"


class SessionAuditLog(models.Model):
    session = models.ForeignKey('scheduling.LectureSession', on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=100)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        performer = self.performed_by.username if self.performed_by else "System"
        return f"{self.action} by {performer} on {self.timestamp.date()}"
