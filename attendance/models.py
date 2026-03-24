from django.db import models
from django.conf import settings
from scheduling.models import LectureSession
from django.core.exceptions import ValidationError
from django.utils import timezone

class AttendanceRecord(models.Model):
    session = models.ForeignKey(LectureSession, on_delete=models.CASCADE, related_name='attendance_records')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_present = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('session', 'student')

    def clean(self):
        # 1. Check if student is actually a student
        if self.student.role != 'STUDENT':
            raise ValidationError({'student': "The user must have the STUDENT role."})
        
        # 2. Prevent marking for future sessions
        if self.session.date > timezone.now().date():
            raise ValidationError("You cannot mark attendance for a future session.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.student.username} - {status} for {self.session}"
