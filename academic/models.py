from django.db import models

class Faculty(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Department(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='departments', null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Program(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='programs')
    min_years = models.PositiveIntegerField(default=3, help_text="Minimum allowed duration in years")
    max_years = models.PositiveIntegerField(default=5, help_text="Maximum allowed duration in years")

    def __str__(self):
        return f"{self.name} ({self.code})"

class CourseUnit(models.Model):
    class CourseType(models.TextChoices):
        THEORY = 'THEORY', 'Theoretical'
        PRACTICAL = 'PRACTICAL', 'Practical'

    class CourseCategory(models.TextChoices):
        CORE = 'CORE', 'Core'
        ELECTIVE = 'ELECTIVE', 'Elective'
        FOUNDATIONAL = 'FOUNDATIONAL', 'Foundational'

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    programs = models.ManyToManyField(Program, related_name='course_units')
    course_type = models.CharField(
        max_length=20,
        choices=CourseType.choices,
        default=CourseType.THEORY
    )
    course_category = models.CharField(
        max_length=20,
        choices=CourseCategory.choices,
        default=CourseCategory.CORE
    )
    required_contact_hours = models.PositiveIntegerField(
        default=45,
        help_text="Minimum contact hours required (e.g., 45 for Theory, 60 for Practical)"
    )
    lecturer = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses_taught',
        limit_choices_to={'role': 'LECTURER'}
    )
    assistant_coordinator = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coordinated_units',
        limit_choices_to={'role': 'COORDINATOR'},
        help_text="Course Unit Coordinator (Assistant Coordinator) for attendance management."
    )
    is_active = models.BooleanField(default=True)
    weekly_hours = models.PositiveIntegerField(
        default=4,
        help_text="Number of teaching hours per week (Standard: 2 sessions * 2 hours = 4)"
    )

    def save(self, *args, **kwargs):
        # Set default required hours based on type if not explicitly set
        if not self.pk and self.required_contact_hours == 45:
            if self.course_type == self.CourseType.PRACTICAL:
                self.required_contact_hours = 60
        super().save(*args, **kwargs)

    @property
    def completed_contact_hours(self):
        """Calculates total hours from CONDUCTED (and APPROVED/AUTO_CONFIRMED for legacy support) lecture sessions."""
        from scheduling.models import LectureSession
        from django.db.models import Sum
        # Sessions use actual_duration as per system rules
        total_hours = LectureSession.objects.filter(
            timetable_entry__course_unit=self,
            status__in=[LectureSession.Status.CONDUCTED, LectureSession.Status.APPROVED, LectureSession.Status.AUTO_CONFIRMED]
        ).aggregate(total=Sum('actual_duration'))['total'] or 0
        return total_hours

    def __str__(self):
        return f"{self.name} ({self.code})"



class CourseGroup(models.Model):
    name = models.CharField(max_length=100)
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='course_groups')
    year = models.PositiveIntegerField(default=1, choices=[(i, f"Year {i}") for i in range(1, 6)])
    semester = models.PositiveIntegerField(default=1, choices=[(1, "Semester 1"), (2, "Semester 2")])
    is_active = models.BooleanField(default=True, help_text="Is this group active for the current scheduling session?")
    course_units = models.ManyToManyField(CourseUnit, related_name='course_groups', blank=True)

    class Meta:
        unique_together = ('name', 'program')

    def __str__(self):
        return f"{self.name} - {self.program.code}"

class ElectiveEnrollment(models.Model):
    """
    Tracks which students are enrolled in which specific elective course unit.
    Used for elective-specific attendance and accurate room capacity calculation.
    """
    student = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='elective_enrollments', limit_choices_to={'role': 'STUDENT'})
    course_unit = models.ForeignKey(CourseUnit, on_delete=models.CASCADE, related_name='enrollments', limit_choices_to={'course_category': 'ELECTIVE'})
    academic_year = models.CharField(max_length=20, help_text="e.g. 2023/2024")
    semester = models.PositiveIntegerField(choices=[(1, "1"), (2, "2")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course_unit', 'academic_year', 'semester')
        verbose_name_plural = "Elective Enrollments"

    def __str__(self):
        return f"{self.student.registration_no or self.student.username} - {self.course_unit.code}"
