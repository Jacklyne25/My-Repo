from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from .services import BulkImportService
import pandas as pd
import io

from users.mixins import RoleRequiredMixin, FacultyAdminRequiredMixin
from .models import Faculty, Department, Program, CourseUnit, CourseGroup
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from scheduling.models import TimetableEntry
from django import forms

from django.core.exceptions import PermissionDenied

class HODRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        # Explicitly restrict to HOD and ensure not a technical admin
        return self.request.user.is_authenticated and self.request.user.role == 'HOD'

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()

class FacultyAdminDashboardView(FacultyAdminRequiredMixin, TemplateView):
    template_name = 'academic/faculty_admin_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_faculties'] = Faculty.objects.count()
        context['total_departments'] = Department.objects.count()
        context['total_programs'] = Program.objects.count()
        return context

class FacultyManagementView(FacultyAdminRequiredMixin, ListView):
    model = Faculty
    template_name = 'academic/faculty_management.html'
    context_object_name = 'faculties'

class DepartmentManagementView(FacultyAdminRequiredMixin, ListView):
    model = Department
    template_name = 'academic/department_management.html'
    context_object_name = 'departments'

    def get_queryset(self):
        # In a real app, this might be filtered by the admin's assigned faculty if applicable
        return Department.objects.all().select_related('faculty')

class ProgramManagementView(LoginRequiredMixin, ListView):
    model = Program
    template_name = 'academic/program_management.html'
    context_object_name = 'programs'

    def get_queryset(self):
        if self.request.user.role == 'HOD':
            return Program.objects.filter(department=self.request.user.department)
        return Program.objects.all()

class ProgramCreateView(LoginRequiredMixin, HODRequiredMixin, CreateView):
    model = Program
    template_name = 'academic/program_form.html'
    fields = ['name', 'code', 'min_years', 'max_years']
    success_url = reverse_lazy('academic:program_management')

    def form_valid(self, form):
        form.instance.department = self.request.user.department
        messages.success(self.request, f"Program '{form.instance.name}' added successfully.")
        return super().form_valid(form)

class ProgramUpdateView(LoginRequiredMixin, HODRequiredMixin, UpdateView):
    model = Program
    template_name = 'academic/program_form.html'
    fields = ['name', 'code', 'min_years', 'max_years']
    success_url = reverse_lazy('academic:program_management')

    def get_queryset(self):
        return Program.objects.filter(department=self.request.user.department)

    def form_valid(self, form):
        messages.success(self.request, f"Program '{form.instance.name}' updated successfully.")
        return super().form_valid(form)

class ProgramDeleteView(LoginRequiredMixin, HODRequiredMixin, DeleteView):
    model = Program
    success_url = reverse_lazy('academic:program_management')

    def get_queryset(self):
        return Program.objects.filter(department=self.request.user.department)

    def delete(self, request, *args, **kwargs):
        program = self.get_object()
        messages.success(request, f"Program '{program.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)

class DepartmentCourseListView(LoginRequiredMixin, HODRequiredMixin, ListView):
    model = CourseUnit
    template_name = 'academic/hod_course_list.html'
    context_object_name = 'courses'

    def get_queryset(self):
        # Filter courses by programs belonging to the HOD's department
        return CourseUnit.objects.filter(programs__department=self.request.user.department).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from users.models import User
        context['lecturers'] = User.objects.filter(
            department=self.request.user.department,
            role=User.Role.LECTURER
        ).order_by('first_name', 'last_name')
        return context

class AssignLecturerView(LoginRequiredMixin, HODRequiredMixin, View):
    def post(self, request, pk):
        course = get_object_or_404(CourseUnit.objects.filter(programs__department=request.user.department).distinct(), pk=pk)
        lecturer_id = request.POST.get('lecturer_id')
        from users.models import User
        lecturer = get_object_or_404(User, pk=lecturer_id, role=User.Role.LECTURER, department=request.user.department)
        course.lecturer = lecturer
        course.save()
        messages.success(request, f"Assigned {lecturer.get_full_name() or lecturer.username} to {course.name}.")
        return redirect('academic:hod_course_list')

class DownloadTemplateView(LoginRequiredMixin, HODRequiredMixin, View):
    def get(self, request, type):
        # Define headers and sample rows
        data = []
        if type == 'students':
            headers = ['Registration No', 'Access No', 'Name', 'Course', 'Year', 'Semester', 'Email', 'Contact']
            data = [['REG/001', 'AC123', 'John Doe', 'BSIT', '1', '1', 'john@example.com', '0771234567']]
        elif type == 'lecturers':
            headers = ['Staff ID', 'Full Name', 'Email', 'Phone', 'Department', 'Academic Rank', 'Employment Type', 'Status', 'Specialization']
            data = [['STF001', 'Dr. Smith', 'smith@univ.ac.ug', '0770000000', 'Computing', 'Lecturer', 'FULL_TIME', 'Active', 'Networking']]
        elif type == 'coordinators':
            headers = ['Coordinator ID', 'Registration No', 'Access No', 'Name', 'Course', 'Year', 'Semester', 'Email', 'Contact']
            data = [['', 'REG/001', 'AC123', 'Jane Doe', 'BSIT', '3', '2', 'jane.doe@univ.ac.ug', '0770000001']]
        elif type == 'timetable':
            headers = ['Department', 'Programme', 'Day', 'Time', 'Course', 'Course Unit', 'Teaching Staff', 'Venue']
            data = [['Computing', 'Day', 'MON', '09:00-11:00', 'BSIT', 'CMP101', 'prof_smith', 'Lab 1']]
        elif type == 'course_units':
            headers = ['Name', 'Code', 'Program Codes', 'Course Type', 'Course Category', 'Required Contact Hours']
            data = [['Introduction to Programming', 'CMP101', 'BSIT,BSCS', 'THEORY', 'CORE', '45']]
        elif type == 'rooms':
            headers = ['Name', 'Capacity']
            data = [['Name', 'Capacity']]
            data = [['Lab 1', '60']]
        elif type == 'course_groups':
            headers = ['Name', 'Program Code']
            data = [['BSIT Year 1 Group A', 'BSIT']]
        elif type == 'programs':
            headers = ['Name', 'Code']
            data = [['Bachelor of Science in Information Technology', 'BSIT']]
            data = [['Year 1 CS', 'BSCS']]
        else:
            return HttpResponse("Invalid template type", status=400)

        # Create DataFrame and save to Excel
        df = pd.DataFrame(data, columns=headers)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Template')
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{type}_template.xlsx"'
        return response

class ImportDataView(LoginRequiredMixin, HODRequiredMixin, View):
    template_name = 'academic/import_data.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        type = request.POST.get('import_type')
        file = request.FILES.get('file')
        
        if not file:
            messages.error(request, "Please select a file.")
            return redirect('academic:import_data')

        if not any(file.name.lower().endswith(ext) for ext in ['.csv', '.xlsx', '.xls']):
            messages.error(request, "Please upload a CSV or Excel file.")
            return redirect('academic:import_data')

        if type == 'students':
            results = BulkImportService.import_students(file, request.user.department)
        elif type == 'lecturers':
            results = BulkImportService.import_lecturers(file, request.user.department)
        elif type == 'coordinators':
            results = BulkImportService.import_coordinators(file, request.user.department)
        elif type == 'timetable':
            results = BulkImportService.import_timetable(file, request.user.department)
        elif type == 'course_units':
            results = BulkImportService.import_course_units(file, request.user.department)
        elif type == 'rooms':
            results = BulkImportService.import_rooms(file)
        elif type == 'course_groups':
            results = BulkImportService.import_course_groups(file, request.user.department)
        elif type == 'programs':
            results = BulkImportService.import_programs(file, request.user.department)
        else:
            messages.error(request, "Invalid import type.")
            return redirect('academic:import_data')

        # Process Results
        if results['errors']:
            messages.warning(request, f"Import Completed with Issues. Success: {results['success']}, Failed: {results['failed']}")
            for error in results['errors'][:10]: # Limit display
                messages.error(request, error)
        else:
            messages.success(request, f"Import Successful! Processed {results['success']} records.")

        return redirect('academic:import_data')


class DepartmentTimetableView(LoginRequiredMixin, HODRequiredMixin, ListView):
    model = TimetableEntry
    template_name = 'academic/department_timetable.html'
    context_object_name = 'timetable_entries'

    def get_queryset(self):
        # Filter timetable entries by programs belonging to the HOD's department
        return TimetableEntry.objects.filter(program__department=self.request.user.department).order_by('day_of_week', 'start_time')

class CourseUnitForm(forms.ModelForm):
    class Meta:
        model = CourseUnit
        fields = ['name', 'code', 'programs', 'course_type', 'course_category', 'required_contact_hours']
        widgets = {
            'programs': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        department = kwargs.pop('department', None)
        super().__init__(*args, **kwargs)
        if department:
            self.fields['programs'].queryset = Program.objects.filter(department=department)

class CourseUnitCreateView(LoginRequiredMixin, HODRequiredMixin, CreateView):
    model = CourseUnit
    form_class = CourseUnitForm
    template_name = 'academic/course_unit_form.html'
    success_url = reverse_lazy('academic:hod_course_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['department'] = self.request.user.department
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f"Course unit {form.instance.code} added successfully.")
        return super().form_valid(form)

class CourseUnitUpdateView(LoginRequiredMixin, HODRequiredMixin, UpdateView):
    model = CourseUnit
    form_class = CourseUnitForm
    template_name = 'academic/course_unit_form.html'
    success_url = reverse_lazy('academic:hod_course_list')
    
    def get_queryset(self):
        # Allow editing any course unit that belongs to ANY program in the HOD's department
        return CourseUnit.objects.filter(programs__department=self.request.user.department).distinct()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['department'] = self.request.user.department
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f"Course unit {form.instance.code} updated successfully.")
        return super().form_valid(form)

class CourseUnitDeleteView(LoginRequiredMixin, HODRequiredMixin, DeleteView):
    model = CourseUnit
    success_url = reverse_lazy('academic:hod_course_list')

    def get_queryset(self):
        return CourseUnit.objects.filter(programs__department=self.request.user.department).distinct()

    def delete(self, request, *args, **kwargs):
        course = self.get_object()
        # Safety check: are there timetable entries?
        if TimetableEntry.objects.filter(course_unit=course).exists():
            messages.error(request, f"Cannot delete '{course.code}' because it is already scheduled in a timetable.")
            return redirect('academic:hod_course_list')
            
        messages.success(request, f"Course unit '{course.code}' deleted successfully.")
        return super().delete(request, *args, **kwargs)
class CourseGroupListView(LoginRequiredMixin, HODRequiredMixin, ListView):
    model = CourseGroup
    template_name = 'academic/course_group_list.html'
    context_object_name = 'course_groups'

    def get_queryset(self):
        from django.db.models import Count
        return CourseGroup.objects.filter(
            program__department=self.request.user.department
        ).annotate(student_count=Count('users'))

class CourseGroupCreateView(LoginRequiredMixin, HODRequiredMixin, CreateView):
    model = CourseGroup
    template_name = 'academic/course_group_form.html'
    fields = ['name', 'program', 'year', 'semester', 'is_active']
    success_url = reverse_lazy('academic:course_group_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['program'].queryset = Program.objects.filter(department=self.request.user.department)
        return form

    def form_valid(self, form):
        messages.success(self.request, f"Course group '{form.instance.name}' created successfully.")
        return super().form_valid(form)

class CourseGroupUpdateView(LoginRequiredMixin, HODRequiredMixin, UpdateView):
    model = CourseGroup
    template_name = 'academic/course_group_form.html'
    fields = ['name', 'program', 'year', 'semester', 'is_active']
    success_url = reverse_lazy('academic:course_group_list')

    def get_queryset(self):
        return CourseGroup.objects.filter(program__department=self.request.user.department)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['program'].queryset = Program.objects.filter(department=self.request.user.department)
        return form

    def form_valid(self, form):
        old_name = self.get_object().name
        response = super().form_valid(form)
        
        # If group name changed, update all coordinator IDs for students in this group
        if old_name != form.instance.name:
            from users.models import User
            coordinators = User.objects.filter(course_group=form.instance, role=User.Role.COORDINATOR)
            for coord in coordinators:
                coord.coordinator_id = "" # Clear so save() regenerates it
                coord.save()
                
        messages.success(self.request, f"Course group '{form.instance.name}' updated successfully.")
        return response

class CourseGroupDeleteView(LoginRequiredMixin, HODRequiredMixin, DeleteView):
    model = CourseGroup
    success_url = reverse_lazy('academic:course_group_list')
    
    def get_queryset(self):
        # Ensure HOD can only delete groups in their own department
        return CourseGroup.objects.filter(program__department=self.request.user.department)

    def delete(self, request, *args, **kwargs):
        group = self.get_object()
        # Check if group has students
        from users.models import User
        if User.objects.filter(course_group=group).exists():
            messages.error(request, f"Cannot delete group '{group.name}' because it still has students assigned to it. Please move or delete the students first.")
            return redirect('academic:course_group_list')
            
        messages.success(request, f"Course group '{group.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)

class CourseGroupUnitAllocationView(LoginRequiredMixin, HODRequiredMixin, UpdateView):
    model = CourseGroup
    template_name = 'academic/course_group_unit_allocation.html'
    fields = ['course_units']
    
    def get_queryset(self):
        # Only allow HODs to manage groups in their own department
        return CourseGroup.objects.filter(program__department=self.request.user.department)

    def get_form(self, form_class=None):
        from django import forms
        form = super().get_form(form_class)
        # Filter units to those linked to programs in the HOD's department
        # We use department_id for maximum robustness
        dept_id = self.request.user.department_id
        if dept_id:
            qs = CourseUnit.objects.filter(
                programs__department_id=dept_id,
                is_active=True
            ).distinct().order_by('code')
            form.fields['course_units'].queryset = qs
            self.total_units_count = qs.count()
        else:
            form.fields['course_units'].queryset = CourseUnit.objects.none()
            self.total_units_count = 0
            
        form.fields['course_units'].widget = forms.CheckboxSelectMultiple()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dept_id = self.request.user.department_id
        if dept_id:
            qs = CourseUnit.objects.filter(
                programs__department_id=dept_id,
                is_active=True
            ).distinct().order_by('code')
            context['available_units_list'] = qs
            context['total_units_count'] = qs.count()
        else:
            context['available_units_list'] = CourseUnit.objects.none()
            context['total_units_count'] = 0
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Course units for '{form.instance.name}' updated successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('academic:course_group_list')
