import pytest
from academic.models import Department, Program, CourseUnit

@pytest.mark.django_db
def test_create_department():
    dept = Department.objects.create(name="Computing & Technology", code="CT")
    assert dept.name == "Computing & Technology"
    assert dept.code == "CT"
    assert str(dept) == "Computing & Technology (CT)"

@pytest.mark.django_db
def test_create_program(db):
    dept = Department.objects.create(name="Computing", code="CT")
    prog = Program.objects.create(name="Bachelor of Science in IT", code="BSIT", department=dept)
    assert prog.department == dept
    assert str(prog) == "Bachelor of Science in IT (BSIT)"

@pytest.mark.django_db
def test_create_course_unit(db):
    dept = Department.objects.create(name="Computing", code="CT")
    prog = Program.objects.create(name="BSIT", code="BSIT", department=dept)
    course = CourseUnit.objects.create(name="Database Design", code="DDA")
    course.programs.add(prog)
    assert course.programs.count() == 1
    assert course.programs.first() == prog
    # Check default category
    assert course.course_category == CourseUnit.CourseCategory.CORE

@pytest.mark.django_db
def test_course_unit_categories(db):
    course_core = CourseUnit.objects.create(name="Core Course", code="CORE001", course_category=CourseUnit.CourseCategory.CORE)
    course_elective = CourseUnit.objects.create(name="Elective Course", code="ELEC001", course_category=CourseUnit.CourseCategory.ELECTIVE)
    course_foundational = CourseUnit.objects.create(name="Foundational Course", code="FND001", course_category=CourseUnit.CourseCategory.FOUNDATIONAL)
    
    assert course_core.course_category == 'CORE'
    assert course_elective.course_category == 'ELECTIVE'
    assert course_foundational.course_category == 'FOUNDATIONAL'
    assert course_core.get_course_category_display() == 'Core'
