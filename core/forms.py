from django import forms
from academic.models import CourseUnit, Program

class HODAnnouncementForm(forms.Form):
    TARGET_CHOICES = [
        ('ALL', 'All Department Members'),
        ('LECTURERS', 'All Lecturers'),
        ('STUDENTS', 'All Students'),
        ('COORDINATORS', 'All Coordinators')
    ]
    target_group = forms.ChoiceField(choices=TARGET_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}), required=True)

class CoordinatorAnnouncementForm(forms.Form):
    TARGET_CHOICES = [
        ('MANAGED_GROUPS', 'My Assigned Class Group(s)'),
        ('PROGRAM', 'Specific Academic Program')
    ]
    target_type = forms.ChoiceField(
        choices=TARGET_CHOICES, 
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='MANAGED_GROUPS'
    )
    target_program = forms.ModelChoiceField(
        queryset=Program.objects.none(), 
        empty_label="Select Program",
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        help_text="Only required if targeting a specific program"
    )
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}), required=True)
    
    def clean(self):
        cleaned_data = super().clean()
        target_type = cleaned_data.get('target_type')
        target_program = cleaned_data.get('target_program')
        
        if target_type == 'PROGRAM' and not target_program:
            self.add_error('target_program', "Please select a program when targeting a specific academic program.")
        return cleaned_data

    def __init__(self, *args, **kwargs):
        department = kwargs.pop('department', None)
        super().__init__(*args, **kwargs)
        if department:
            self.fields['target_program'].queryset = Program.objects.filter(department=department)

class LecturerAnnouncementForm(forms.Form):
    target_course_unit = forms.ModelChoiceField(
        queryset=CourseUnit.objects.none(),
        empty_label="Select Course Unit",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}), required=True)

    def __init__(self, *args, **kwargs):
        lecturer = kwargs.pop('lecturer', None)
        super().__init__(*args, **kwargs)
        if lecturer:
            # Find all courses this lecturer is scheduled to teach
            from scheduling.models import TimetableEntry
            course_ids = TimetableEntry.objects.filter(lecturer=lecturer).values_list('course_unit_id', flat=True).distinct()
            self.fields['target_course_unit'].queryset = CourseUnit.objects.filter(id__in=course_ids)
