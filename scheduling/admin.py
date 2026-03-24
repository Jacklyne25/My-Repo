from django.contrib import admin
from .models import Room, TimetableEntry, LectureSession

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity')

@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ('course_unit', 'lecturer', 'program', 'room', 'day_of_week', 'start_time', 'end_time')
    list_filter = ('day_of_week', 'room', 'program')
    search_fields = ('course_unit__code', 'course_unit__name', 'lecturer__username')

@admin.register(LectureSession)
class LectureSessionAdmin(admin.ModelAdmin):
    list_display = ('timetable_entry', 'date', 'status')
    list_filter = ('status', 'date')
