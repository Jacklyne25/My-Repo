from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

class GlobalSettings(models.Model):
    attendance_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=75.00, help_text="Minimum attendance percentage before alert")
    semester_start = models.DateField(null=True, blank=True)
    semester_end = models.DateField(null=True, blank=True)
    password_policy_regex = models.CharField(max_length=255, default=r'^.{8,}$', help_text="Regex for password validation")
    
    def save(self, *args, **kwargs):
        if not self.pk and GlobalSettings.objects.exists():
            raise ValidationError("There can be only one GlobalSettings instance")
        return super(GlobalSettings, self).save(*args, **kwargs)

    def __str__(self):
        return "Global Settings"

class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=255)
    
    # Generic relation to target object
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=255, null=True, blank=True)
    target = GenericForeignKey('content_type', 'object_id')
    
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.actor} - {self.action} at {self.timestamp}"
