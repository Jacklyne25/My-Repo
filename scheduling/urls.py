from django.urls import path
from .views import (
    SchedulingDashboardView,
    SetParametersView,
    AutoScheduleView,
    ConflictReviewView,
    ManualScheduleView,
    TimetableGridView,
    TimetableDeleteView,
    TimetableListView,
    TimetableDeleteTimetableView,
    TimetableConflictCheckView,
    PublishTimetableView,
    TimetableUpdateView,
    RoomListView,
    RoomCreateView,
    RoomUpdateView,
    RoomDeleteView,
)

app_name = 'scheduling'

urlpatterns = [
    path('', SchedulingDashboardView.as_view(), name='dashboard'),
    path('parameters/', SetParametersView.as_view(), name='set_parameters'),
    path('auto/', AutoScheduleView.as_view(), name='auto_schedule'),
    path('conflicts/', ConflictReviewView.as_view(), name='conflict_review'),
    path('manual/', ManualScheduleView.as_view(), name='manual_schedule'),
    # Timetable Management
    path('timetables/', TimetableListView.as_view(), name='timetable_list'),
    path('timetable/', TimetableGridView.as_view(), name='timetable_grid'),
    path('timetable/<int:pk>/', TimetableGridView.as_view(), name='timetable_grid_pk'),
    path('timetable/<int:pk>/delete/', TimetableDeleteTimetableView.as_view(), name='delete_timetable'),
    # Entry-level actions
    path('entry/<int:pk>/delete/', TimetableDeleteView.as_view(), name='delete_entry'),
    path('entry/<int:pk>/update/', TimetableUpdateView.as_view(), name='update_entry'),
    path('publish/', PublishTimetableView.as_view(), name='publish_timetable'),
    path('conflict-check/', TimetableConflictCheckView.as_view(), name='conflict_check'),
    path('rooms/', RoomListView.as_view(), name='room_list'),
    path('rooms/create/', RoomCreateView.as_view(), name='create_room'),
    path('rooms/<int:pk>/edit/', RoomUpdateView.as_view(), name='edit_room'),
    path('rooms/<int:pk>/delete/', RoomDeleteView.as_view(), name='delete_room'),
]
