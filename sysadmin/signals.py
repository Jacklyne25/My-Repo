from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from .models import AuditLog

@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    AuditLog.objects.create(
        actor=user,
        action="USER_LOGIN",
        metadata={'ip': ip}
    )

@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    username = credentials.get('username')
    
    # Log audit
    AuditLog.objects.create(
        action="LOGIN_FAILED",
        metadata={'ip': ip, 'username_attempt': username}
    )
    
    # Trigger Security Alert
    from core.services import AlertService
    AlertService.notify_security_breach(
        ip_address=ip,
        details=f"Failed login attempt for username '{username}'"
    )
