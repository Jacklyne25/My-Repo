from django import forms
from .models import User, LecturerProfile
from django.core.exceptions import ValidationError

class AccountActivationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label="Registration No / Staff ID",
        widget=forms.TextInput(attrs={'placeholder': 'Enter your institutional ID'})
    )


class DepartmentUserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'role', 'phone_number', 'registration_no', 'access_no', 'coordinator_id', 'course_group', 'enrollment_date']
    
    enrollment_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    
    # Lecturer Specific Fields (Extra)
    employment_type = forms.ChoiceField(choices=LecturerProfile.EmploymentType.choices, required=False)
    min_weekly_load = forms.IntegerField(required=False, min_value=0)
    max_weekly_load = forms.IntegerField(required=False, min_value=0)
    specialization = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'e.g. Data Science'}))    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate lecturer profile fields if they exist
        if self.instance and self.instance.pk and hasattr(self.instance, 'lecturer_profile'):
            profile = self.instance.lecturer_profile
            self.fields['employment_type'].initial = profile.employment_type
            self.fields['min_weekly_load'].initial = profile.min_weekly_load
            self.fields['max_weekly_load'].initial = profile.max_weekly_load
            self.fields['specialization'].initial = profile.specialization
        # Limit role choices for HOD
        allowed_roles = [
            User.Role.COORDINATOR,
            User.Role.LECTURER,
            User.Role.STUDENT,
        ]
        self.fields['role'].choices = [
            (role.value, role.label) for role in User.Role 
            if role.value in allowed_roles
        ]
        
        # Add styling
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class UserCreateForm(DepartmentUserEditForm):
    username = forms.CharField(
        max_length=150,
        label="Institutional ID (Reg No / Staff ID)",
        widget=forms.TextInput(attrs={'placeholder': 'e.g. S21/BCS/001 or STF/101'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'phone_number', 'registration_no', 'access_no', 'coordinator_id', 'course_group', 'enrollment_date']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with this Institutional ID already exists.")
        return username
