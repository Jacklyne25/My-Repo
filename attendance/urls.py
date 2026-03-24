from django.urls import path
from .views import (
    SessionListView, CaptureAttendanceView, SubmitValidationView, 
    ValidateAttendanceView, CourseAttendanceSummaryView, GenerateReportView,
    WeeklyAttendanceView, UploadSignedSheetView, LecturerReviewWeekView,
    WeekCourseDetailView, StartAttendanceView, RescheduleSessionView,
    MarkMissedSessionsView, ConfirmSessionView, CancelSessionView
)

app_name = 'attendance'

urlpatterns = [
    path('sessions/', SessionListView.as_view(), name='session_list'),
    path('sessions/<int:pk>/capture/', CaptureAttendanceView.as_view(), name='capture_attendance'),
    path('sessions/<int:pk>/submit/', SubmitValidationView.as_view(), name='submit_validation'),
    path('sessions/<int:pk>/validate/', ValidateAttendanceView.as_view(), name='validate_attendance'),
    path('course-summary/<int:pk>/', CourseAttendanceSummaryView.as_view(), name='course_summary'),
    path('weekly/', WeeklyAttendanceView.as_view(), name='weekly_dashboard'),
    path('weekly/<str:week_str>/<int:course_id>/', WeekCourseDetailView.as_view(), name='week_detail'),
    path('sessions/<int:pk>/upload-sheet/', UploadSignedSheetView.as_view(), name='upload_sheet'),
    path('start-session/<int:entry_id>/', StartAttendanceView.as_view(), name='start_attendance'),
    path('sessions/<int:pk>/reschedule/', RescheduleSessionView.as_view(), name='reschedule_session'),
    path('mark-missed-sessions/', MarkMissedSessionsView.as_view(), name='mark_missed_sessions'),
    path('generate-report/', GenerateReportView.as_view(), name='generate_report'),
]
