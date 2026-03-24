from django.urls import path
from .views import (
    ImportDataView, DownloadTemplateView, DepartmentTimetableView,
    FacultyAdminDashboardView, FacultyManagementView, DepartmentManagementView, ProgramManagementView,
    ProgramCreateView, ProgramUpdateView, ProgramDeleteView,
    DepartmentCourseListView, AssignLecturerView, CourseUnitCreateView, CourseUnitUpdateView, CourseUnitDeleteView, CourseGroupListView, CourseGroupDeleteView,
    CourseGroupCreateView, CourseGroupUpdateView, CourseGroupUnitAllocationView
)

app_name = 'academic'

urlpatterns = [
    path('dashboard/faculty/', FacultyAdminDashboardView.as_view(), name='faculty_dashboard'),
    path('faculties/', FacultyManagementView.as_view(), name='faculty_management'),
    path('departments/', DepartmentManagementView.as_view(), name='department_management'),
    path('programs/', ProgramManagementView.as_view(), name='program_management'),
    path('programs/add/', ProgramCreateView.as_view(), name='add_program'),
    path('programs/<int:pk>/edit/', ProgramUpdateView.as_view(), name='edit_program'),
    path('programs/<int:pk>/delete/', ProgramDeleteView.as_view(), name='delete_program'),
    
    path('courses/', DepartmentCourseListView.as_view(), name='hod_course_list'),
    path('courses/add/', CourseUnitCreateView.as_view(), name='add_course'),
    path('courses/<int:pk>/edit/', CourseUnitUpdateView.as_view(), name='edit_course'),
    path('courses/<int:pk>/delete/', CourseUnitDeleteView.as_view(), name='delete_course'),
    path('courses/<int:pk>/assign-lecturer/', AssignLecturerView.as_view(), name='assign_lecturer'),
    
    path('import/', ImportDataView.as_view(), name='import_data'),
    path('import/template/<str:type>/', DownloadTemplateView.as_view(), name='download_template'),
    path('timetable/', DepartmentTimetableView.as_view(), name='department_timetable'),
    path('course-groups/', CourseGroupListView.as_view(), name='course_group_list'),
    path('course-groups/add/', CourseGroupCreateView.as_view(), name='add_course_group'),
    path('course-groups/<int:pk>/edit/', CourseGroupUpdateView.as_view(), name='edit_course_group'),
    path('course-groups/<int:pk>/delete/', CourseGroupDeleteView.as_view(), name='delete_course_group'),
    path('course-groups/<int:pk>/allocate-units/', CourseGroupUnitAllocationView.as_view(), name='allocate_units'),
]
