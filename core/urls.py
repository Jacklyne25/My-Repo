from django.urls import path
from .views import NotificationsListView, MarkAlertReadView, MarkAllAlertsReadView, CreateAnnouncementView

app_name = 'core'

urlpatterns = [
    path('notifications/', NotificationsListView.as_view(), name='notifications'),
    path('notifications/create/', CreateAnnouncementView.as_view(), name='create_announcement'),
    path('notifications/mark-read/<int:alert_id>/', MarkAlertReadView.as_view(), name='mark_alert_read'),
    path('notifications/mark-all-read/', MarkAllAlertsReadView.as_view(), name='mark_all_read'),
]
