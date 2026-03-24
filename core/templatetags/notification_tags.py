from django import template
from core.models import Alert

register = template.Library()

@register.simple_tag
def get_unread_alerts_count(user):
    if getattr(user, 'is_authenticated', False):
        return Alert.objects.filter(user=user, is_read=False).count()
    return 0
