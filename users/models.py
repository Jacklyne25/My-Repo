from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        SYSTEM_ADMIN = 'SYSTEM_ADMIN', 'System Administrator'
        FACULTY_ADMIN = 'FACULTY_ADMIN', 'Faculty Admin'
        HOD = 'HOD', 'Academic Administrator'
        COORDINATOR = 'COORDINATOR', 'Coordinator'
        LECTURER = 'LECTURER', 'Teaching Staff'
        ADMIN_ASSISTANT = 'ADMIN_ASSISTANT', 'Administrative Assistant'
        STUDENT = 'STUDENT', 'Student'

    class AccountStatus(models.TextChoices):
        NOT_ACTIVATED = 'NOT_ACTIVATED', 'Not Activated'
        ACTIVE = 'ACTIVE', 'Active'
        DEACTIVATED = 'DEACTIVATED', 'Deactivated'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT
    )
    
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.NOT_ACTIVATED
    )
    
    department = models.ForeignKey(
        'academic.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="The department this user belongs to"
    )
    program = models.ForeignKey(
        'academic.Program',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        help_text="The program this student is enrolled in (for Students only)"
    )
    course_group = models.ForeignKey(
        'academic.CourseGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="The specific class/group this student or coordinator is assigned to"
    )
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    registration_no = models.CharField(max_length=50, blank=True, null=True, unique=True)
    access_no = models.CharField(max_length=50, blank=True, null=True, unique=True)
    coordinator_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    enrollment_date = models.DateField(null=True, blank=True, help_text="Derived from registration number (e.g. J26 -> Jan 2026)")
    requires_password_reset = models.BooleanField(default=False)

    def is_sysadmin(self):
        return self.role == self.Role.SYSTEM_ADMIN

    def is_faculty_admin(self):
        return self.role == self.Role.FACULTY_ADMIN

    def is_hod(self):
        return self.role == self.Role.HOD

    def is_coordinator(self):
        return self.role == self.Role.COORDINATOR

    def is_lecturer(self):
        return self.role == self.Role.LECTURER

    def is_student(self):
        return self.role == self.Role.STUDENT

    def is_admin_assistant(self):
        return self.role == self.Role.ADMIN_ASSISTANT

    def is_over_time_limit(self):
        """Checks if a student has exceeded their program's maximum allowed years."""
        if not self.is_student() or not self.program or not self.enrollment_date:
            return False
            
        from django.utils import timezone
        diff = timezone.now().date() - self.enrollment_date
        years = diff.days / 365.25
        return years > self.program.max_years

    def get_coordinator(self):
        """Returns the coordinator for this student, with fallback from DIT to BSIT."""
        if not self.is_student() or not self.course_group:
            return None
            
        # 1. Try to find an active coordinator in the student's own course group
        coordinator = User.objects.filter(
            role=User.Role.COORDINATOR,
            course_group=self.course_group,
            account_status=User.AccountStatus.ACTIVE
        ).first()
        
        if coordinator:
            return coordinator
            
        # 2. Fallback: If DIT, look for BSIT coordinator of same Year and Semester
        if self.program and self.program.code == 'DIT':
            from academic.models import CourseGroup as AcademicCourseGroup
            # Find corresponding BSIT group in same department
            bsit_group = AcademicCourseGroup.objects.filter(
                program__code='BSIT',
                year=self.course_group.year,
                semester=self.course_group.semester,
                program__department=self.program.department
            ).first()
            
            if bsit_group:
                return User.objects.filter(
                    role=User.Role.COORDINATOR,
                    course_group=bsit_group,
                    account_status=User.AccountStatus.ACTIVE
                ).first()
                
        return None

    def get_managed_course_groups(self):
        """Returns the list of course groups this user is responsible for as a coordinator."""
        if not self.is_coordinator() or not self.course_group:
            return []
            
        managed_groups = [self.course_group]
        
        # If this is a BSIT coordinator, also manage DIT groups of same Year/Sem that have no coordinator
        if self.course_group.program.code == 'BSIT':
            from academic.models import CourseGroup as AcademicCourseGroup
            
            # Find corresponding DIT groups in same department
            dit_groups = AcademicCourseGroup.objects.filter(
                program__code='DIT',
                year=self.course_group.year,
                semester=self.course_group.semester,
                program__department=self.course_group.program.department
            )
            
            for dg in dit_groups:
                # Check if group has its own active coordinator
                has_own_coord = User.objects.filter(
                    role=User.Role.COORDINATOR,
                    course_group=dg,
                    account_status=User.AccountStatus.ACTIVE
                ).exists()
                
                if not has_own_coord:
                    managed_groups.append(dg)
                    
        return managed_groups

    def save(self, *args, **kwargs):
        # Auto-generate enrollment_date if registration_no is set
        if self.registration_no:
            import re
            from datetime import date
            match = re.match(r'^([JMS])(\d{2})/', self.registration_no)
            if match:
                cohort, year_suffix = match.groups()
                year = 2000 + int(year_suffix)
                month = 1 # J
                if cohort == 'M': month = 5
                elif cohort == 'S': month = 9
                self.enrollment_date = date(year, month, 1)

        # Auto-generate coordinator_id if role is COORDINATOR and course_group is assigned
        if self.role == self.Role.COORDINATOR and self.course_group:
            if not self.coordinator_id or self.coordinator_id.strip() == "":
                # Use the group name, removing spaces for the requested "CDBSIT3:2" style
                group_name = self.course_group.name.replace(" ", "")
                self.coordinator_id = f"CD{group_name}"
        super().save(*args, **kwargs)

class LecturerProfile(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = 'FULL_TIME', 'Full Time'
        PART_TIME = 'PART_TIME', 'Part Time'
        CONTRACT = 'CONTRACT', 'Contract'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        ON_LEAVE = 'ON_LEAVE', 'On Leave'
        RESIGNED = 'RESIGNED', 'Resigned'
        TERMINATED = 'TERMINATED', 'Terminated'

    class AcademicRank(models.TextChoices):
        TUTORIAL_ASSISTANT = 'TA', 'Tutorial Assistant/Teaching Assistant'
        ASSISTANT_LECTURER = 'AL', 'Assistant Lecturer'
        LECTURER = 'L', 'Lecturer'
        SENIOR_LECTURER = 'SL', 'Senior Lecturer'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='lecturer_profile')
    academic_rank = models.CharField(
        max_length=50, 
        choices=AcademicRank.choices, 
        default=AcademicRank.LECTURER,
        help_text="The specific rank of the teaching staff"
    )
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    specialization = models.CharField(max_length=100, blank=True)
    min_weekly_load = models.PositiveIntegerField(default=16, help_text="Minimum teaching hours per week")
    max_weekly_load = models.PositiveIntegerField(default=20, help_text="Maximum teaching hours per week")

    def __str__(self):
        return f"{self.user.username} Profile"
