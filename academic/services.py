import csv
import io
import pandas as pd
from users.models import User, LecturerProfile
from academic.models import Department, Program, CourseUnit, CourseGroup
from scheduling.models import Room, TimetableEntry
from scheduling.utils import generate_sessions_for_range
from sysadmin.models import GlobalSettings
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction

class BulkImportService:
    @staticmethod
    def _get_data_from_file(file_obj):
        """
        Extracts data from CSV or Excel file and returns a list of dictionaries with lowercase keys.
        """
        filename = file_obj.name.lower()
        if filename.endswith('.csv'):
            decoded_file = file_obj.read().decode('utf-8-sig')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            data = []
            for row in reader:
                data.append({k.strip().lower(): v.strip() if isinstance(v, str) else v for k, v in row.items() if k})
            return data
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_obj)
            # Normalize headers to lowercase
            df.columns = [str(c).strip().lower() for c in df.columns]
            # Convert to list of dicts and strip strings
            data = df.to_dict(orient='records')
            normalized_data = []
            for row in data:
                normalized_data.append({k: str(v).strip() if pd.notna(v) else "" for k, v in row.items()})
            return normalized_data
        else:
            raise ValueError("Unsupported file format. Please upload CSV or Excel.")

    @staticmethod
    def import_lecturers(file_obj, department):
        """
        Imports teaching staff from CSV.
        Columns: Staff ID, Full Name, Email, Phone, Department, Academic Rank, Employment Type, Status, Specialization, Max Weekly Load
        """
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            data = BulkImportService._get_data_from_file(file_obj)
            
            if not data:
                results['errors'].append("The file is empty.")
                return results

            # Map the academic rank strings to choices
            rank_map = {
                'tutorial assistant': LecturerProfile.AcademicRank.TUTORIAL_ASSISTANT,
                'teaching assistant': LecturerProfile.AcademicRank.TUTORIAL_ASSISTANT,
                'assistant lecturer': LecturerProfile.AcademicRank.ASSISTANT_LECTURER,
                'lecturer': LecturerProfile.AcademicRank.LECTURER,
                'senior lecturer': LecturerProfile.AcademicRank.SENIOR_LECTURER,
            }

            # Map "Staff ID" -> username for consistency or specific column
            # Checks
            required = ['staff id', 'email', 'full name']
            first_row = data[0]
            if not all(col in first_row for col in required):
                results['errors'].append("Missing required columns: Staff ID, Email, Full Name")
                return results

            with transaction.atomic():
                for i, row in enumerate(data):
                    row_num = i + 2
                    
                    staff_id = row.get('staff id', '').strip()
                    email = row.get('email', '').strip()
                    full_name = row.get('full name', '').strip()
                    phone = row.get('phone', '').strip()
                    csv_dept_name = row.get('department', '').strip()
                    
                    rank_str = row.get('academic rank', '').strip().lower()
                    academic_rank = rank_map.get(rank_str, LecturerProfile.AcademicRank.LECTURER)
                    
                    employment_type = row.get('employment type', 'FULL_TIME').upper().replace(' ', '_')
                    specialization = row.get('specialization', '').strip()
                    
                    if not staff_id or not email:
                         results['failed'] += 1
                         results['errors'].append(f"Row {row_num}: Missing Staff ID or Email")
                         continue

                    # Name Split
                    first_name = ""
                    last_name = ""
                    if full_name:
                        parts = full_name.split(' ', 1)
                        first_name = parts[0]
                        if len(parts) > 1:
                            last_name = parts[1]

                    existing_user = User.objects.filter(username=staff_id).first()
                    
                    try:
                        if existing_user:
                            # Update existing user
                            existing_user.email = email
                            existing_user.first_name = first_name
                            existing_user.last_name = last_name
                            existing_user.phone_number = phone
                            existing_user.save()
                            user = existing_user
                        else:
                            # Create new user
                            user = User.objects.create_user(
                                username=staff_id,
                                email=email,
                                password=None,
                                first_name=first_name,
                                last_name=last_name,
                                role=User.Role.LECTURER,
                                department=department,
                                phone_number=phone,
                                is_active=False,
                                account_status=User.AccountStatus.NOT_ACTIVATED
                            )
                        
                        # Fix Employment Type Enum
                        if employment_type not in LecturerProfile.EmploymentType.values:
                            if 'PART' in employment_type: employment_type = 'PART_TIME'
                            elif 'CONTRACT' in employment_type: employment_type = 'CONTRACT'
                            else: employment_type = 'FULL_TIME'

                        profile, _ = LecturerProfile.objects.update_or_create(
                            user=user,
                            defaults={
                                'academic_rank': academic_rank,
                                'employment_type': employment_type,
                                'specialization': specialization,
                            }
                        )
                        results['success'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"File error: {str(e)}")
            
        return results


    @staticmethod
    def import_coordinators(file_obj, department):
        """
        Imports coordinators from CSV.
        Columns: Staff ID, Full Name, Email, Phone
        """
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            data = BulkImportService._get_data_from_file(file_obj)
            
            if not data:
                results['errors'].append("The file is empty.")
                return results

            required = ['staff id', 'email', 'full name']
            if not all(col in data[0] for col in required):
                results['errors'].append("Missing required columns: Staff ID, Email, Full Name")
                return results

            with transaction.atomic():
                for i, row in enumerate(data):
                    row_num = i + 2
                    
                    coordinator_id = row.get('coordinator id', '').strip()
                    reg_no = row.get('registration no', '').strip()
                    access_no = row.get('access no', '').strip()
                    email = row.get('email', '').strip()
                    full_name = row.get('name', '').strip()
                    phone = row.get('contact', '').strip()
                    
                    if not reg_no or not email:
                         results['failed'] += 1
                         results['errors'].append(f"Row {row_num}: Missing Registration No or Email")
                         continue

                    if User.objects.filter(username=reg_no).exists():
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: User {reg_no} already exists")
                        continue

                    # Name Split
                    first_name = ""
                    last_name = ""
                    if full_name:
                        parts = full_name.split(' ', 1)
                        first_name = parts[0]
                        if len(parts) > 1:
                            last_name = parts[1]

                    program_code = row.get('course', '').strip()
                    year = row.get('year', '').strip()
                    semester = row.get('semester', '').strip()
                    course_group = None
                    program = None
                    
                    if program_code:
                        program = Program.objects.filter(code__iexact=program_code).first()
                    
                    if program_code and year and semester:
                        group_name = f"{program_code} {year}:{semester}"
                        course_group = CourseGroup.objects.filter(name=group_name).first()

                    try:
                        User.objects.create_user(
                            username=reg_no,
                            email=email,
                            password=None,
                            first_name=first_name,
                            last_name=last_name,
                            role=User.Role.COORDINATOR,
                            department=department,
                            phone_number=phone,
                            registration_no=reg_no,
                            access_no=access_no,
                            coordinator_id=coordinator_id,
                            course_group=course_group,
                            program=program,
                            is_active=False,
                            account_status=User.AccountStatus.NOT_ACTIVATED
                        )
                        results['success'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"File error: {str(e)}")
            
        return results

    @staticmethod
    def import_students(file_obj, department):
        """
        Imports students from CSV (User-defined Schema).
        Columns: Registration No, Access No, Name, Course, Year, Semester, Email, Contact
        Mapping:
            - Registration No -> username
            - Name -> first_name, last_name
            - Email -> email
            - Others -> Ignored (Metadata)
        """
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            data = BulkImportService._get_data_from_file(file_obj)
            
            if not data:
                results['errors'].append("The file is empty.")
                return results
            
            # Map user columns to internal keys
            # user: "registration no", "name", "email"
            # required check:
            if 'registration no' not in data[0] or 'email' not in data[0]:
                results['errors'].append("File must contain 'Registration No' and 'Email' columns.")
                return results

            with transaction.atomic():
                for i, row in enumerate(data):
                    row_num = i + 2
                    
                    reg_no = row.get('registration no', '').strip()
                    access_no = row.get('access no', '').strip()
                    email = row.get('email', '').strip()
                    full_name = row.get('name', '').strip()
                    phone = row.get('contact', '').strip()
                    
                    # Name Split
                    first_name = ""
                    last_name = ""
                    if full_name:
                        parts = full_name.split(' ', 1)
                        first_name = parts[0]
                        if len(parts) > 1:
                            last_name = parts[1]
                    
                    if not reg_no or not email:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: Registration No or Email missing")
                        continue

                    if User.objects.filter(username=reg_no).exists():
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: Student {reg_no} already exists")
                        continue

                    program_code = row.get('course', '').strip()
                    year = row.get('year', '').strip()
                    semester = row.get('semester', '').strip()
                    course_group = None
                    program = None
                    
                    if program_code:
                        program = Program.objects.filter(code__iexact=program_code).first()
                    
                    if program_code and year and semester:
                        group_name = f"{program_code} {year}:{semester}"
                        course_group = CourseGroup.objects.filter(name=group_name).first()

                    try:
                        User.objects.create_user(
                            username=reg_no,
                            email=email,
                            password=None, # No initial password
                            first_name=first_name,
                            last_name=last_name,
                            role=User.Role.STUDENT,
                            department=department,
                            registration_no=reg_no,
                            access_no=access_no,
                            phone_number=phone,
                            course_group=course_group,
                            program=program,
                            is_active=False,
                            account_status=User.AccountStatus.NOT_ACTIVATED
                        )
                        results['success'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")
                        
        except Exception as e:
            results['errors'].append(f"File error: {str(e)}")
            
        return results

    @staticmethod
    def import_course_units(file_obj, department):
        """
        Imports Course Units from CSV.
        Columns: Name, Code, Program Codes (comma separated)
        """
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            data = BulkImportService._get_data_from_file(file_obj)
            
            if not data:
                results['errors'].append("The file is empty.")
                return results

            required = ['name', 'code', 'program codes']
            if not all(col in data[0] for col in required):
                results['errors'].append("Missing required columns: Name, Code, Program Codes")
                return results

            with transaction.atomic():
                for i, row in enumerate(data):
                    row_num = i + 2
                    
                    name = row.get('name', '').strip()
                    code = row.get('code', '').strip()
                    program_codes_str = row.get('program codes', '').strip()
                    
                    if not name or not code or not program_codes_str:
                         results['failed'] += 1
                         results['errors'].append(f"Row {row_num}: Missing Name, Code, or Program Codes")
                         continue

                    # Parse programs
                    # Support both comma and semicolon
                    program_sep = ';' if ';' in program_codes_str else ','
                    program_codes = [p.strip() for p in program_codes_str.split(program_sep)]
                    
                    found_programs = []
                    for p_code in program_codes:
                        if not p_code: continue
                        
                        prog = Program.objects.filter(code__iexact=p_code).first()
                        if not prog:
                            results['errors'].append(f"Row {row_num}: Program '{p_code}' does not exist in the system.")
                        elif prog.department != department:
                            results['errors'].append(f"Row {row_num}: Program '{p_code}' exists but belongs to '{prog.department.name}' (Your department is '{department.name}')")
                        else:
                            found_programs.append(prog)
                    
                    if not found_programs:
                         results['failed'] += 1
                         if not any(f"Row {row_num}" in e for e in results['errors']):
                             results['errors'].append(f"Row {row_num}: No valid programs found for this course unit.")
                         continue

                    # Update missing_programs check UI but we already did per-program above

                    course_type = row.get('course type', 'THEORY').upper()
                    if course_type not in CourseUnit.CourseType.values:
                        course_type = 'THEORY'
                        
                    course_category = row.get('course category', 'CORE').upper()
                    if course_category not in CourseUnit.CourseCategory.values:
                        course_category = 'CORE'

                    required_hours_str = row.get('required contact hours', '').strip()
                    if not required_hours_str:
                        # Default based on type
                        required_hours = 60 if course_type == 'PRACTICAL' else 45
                    else:
                        required_hours = int(required_hours_str) if required_hours_str.isdigit() else 45

                    try:
                        course_unit, created = CourseUnit.objects.update_or_create(
                            code=code,
                            defaults={
                                'name': name,
                                'course_type': course_type,
                                'course_category': course_category,
                                'required_contact_hours': required_hours
                            }
                        )
                        course_unit.programs.add(*found_programs)
                        results['success'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"File error: {str(e)}")
            
        return results

    @staticmethod
    def import_rooms(file_obj):
        """
        Imports Rooms from CSV.
        Columns: Name, Capacity
        """
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            data = BulkImportService._get_data_from_file(file_obj)
            
            if not data:
                results['errors'].append("The file is empty.")
                return results

            required = ['name', 'capacity']
            if not all(col in data[0] for col in required):
                results['errors'].append("Missing required columns: Name, Capacity")
                return results

            with transaction.atomic():
                for i, row in enumerate(data):
                    row_num = i + 2
                    
                    name = row.get('name', '').strip()
                    capacity_str = row.get('capacity', '').strip()
                    
                    if not name or not capacity_str:
                         results['failed'] += 1
                         results['errors'].append(f"Row {row_num}: Missing Name or Capacity")
                         continue

                    try:
                        capacity = int(capacity_str)
                    except ValueError:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: Invalid capacity value '{capacity_str}'")
                        continue

                    try:
                        Room.objects.update_or_create(
                            name=name,
                            defaults={'capacity': capacity}
                        )
                        results['success'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"File error: {str(e)}")
            
        return results

    @staticmethod
    def import_course_groups(file_obj, department):
        """
        Imports Course Groups from CSV.
        Columns: Name, Program Code
        """
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            data = BulkImportService._get_data_from_file(file_obj)
            
            if not data:
                results['errors'].append("The file is empty.")
                return results

            required = ['name', 'program code']
            if not all(col in data[0] for col in required):
                results['errors'].append("Missing required columns: Name, Program Code")
                return results

            with transaction.atomic():
                for i, row in enumerate(data):
                    row_num = i + 2
                    
                    name = row.get('name', '').strip()
                    program_code = row.get('program code', '').strip()
                    
                    if not name or not program_code:
                         results['failed'] += 1
                         results['errors'].append(f"Row {row_num}: Missing Name or Program Code")
                         continue

                    try:
                        program = Program.objects.get(code=program_code, department=department)
                    except Program.DoesNotExist:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: Program '{program_code}' not found in this department")
                        continue

                    try:
                        CourseGroup.objects.update_or_create(
                            name=name, program=program
                        )
                        results['success'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"File error: {str(e)}")
            
        return results

    @staticmethod
    def import_programs(file_obj, department):
        """
        Imports Programs from CSV/Excel.
        Columns: Name, Code
        """
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            data = BulkImportService._get_data_from_file(file_obj)
            
            if not data:
                results['errors'].append("The file is empty.")
                return results
 
            required = ['name', 'code']
            if not all(col in data[0] for col in required):
                results['errors'].append("Missing required columns: Name, Code")
                return results
 
            with transaction.atomic():
                for i, row in enumerate(data):
                    row_num = i + 2
                    
                    name = row.get('name', '').strip()
                    code = row.get('code', '').strip()
                    
                    if not name or not code:
                         results['failed'] += 1
                         results['errors'].append(f"Row {row_num}: Missing Name or Code")
                         continue
 
                    try:
                        # Check if code exists globally or just in dept? Code is unique in Model.
                        Program.objects.update_or_create(
                            code=code,
                            defaults={'name': name, 'department': department}
                        )
                        results['success'] += 1
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")
 
        except Exception as e:
            results['errors'].append(f"File error: {str(e)}")
            
        return results

    @staticmethod
    def import_timetable(file_obj, department):
        """
        Imports timetable from CSV (User-defined Schema).
        Columns: Department, Programme, Day, Time, Course, Course Unit, Lecturer, Venue
        Mapping:
            - Course -> Program Code
            - Course Unit -> CourseUnit Code
            - Lecturer -> Lecturer Username
            - Venue -> Room Name
            - Time -> Split "HH:MM-HH:MM"
        """
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        settings = GlobalSettings.objects.first()
        if not settings or not settings.semester_start or not settings.semester_end:
            results['errors'].append("Global Settings (Semester Dates) not configured.")
            return results

        try:
            data = BulkImportService._get_data_from_file(file_obj)
            
            if not data:
                results['errors'].append("The file is empty.")
                return results

            required = ['day', 'time', 'course', 'course unit', 'lecturer', 'venue']
            missing = [col for col in required if col not in data[0]]
            if missing:
                results['errors'].append(f"Missing columns: {', '.join(missing)}")
                return results

            for i, row in enumerate(data):
                row_num = i + 2
                
                try:
                    # Parse Time "09:00-11:00"
                    time_raw = row['time'].strip()
                    if '-' in time_raw:
                        start_str, end_str = time_raw.split('-')
                    else:
                        raise ValidationError("Time format must be HH:MM-HH:MM")
                        
                    # Fetch Objects
                    # Course -> Program Code
                    prog_code = row['course'].strip()
                    program = Program.objects.get(code=prog_code, department=department)

                    # Course Unit -> Code
                    unit_code = row['course unit'].strip()
                    # Filtering by program can be ambiguous if shared, but usually code is unique
                    course = CourseUnit.objects.get(code=unit_code) 
                    
                    # Venue -> Room Name
                    room_name = row['venue'].strip()
                    room = Room.objects.get(name=room_name)
                    
                    # Lecturer -> Username
                    lecturer_name = row['lecturer'].strip()
                    lecturer = User.objects.get(username=lecturer_name, role=User.Role.LECTURER)

                    entry = TimetableEntry(
                        course_unit=course,
                        lecturer=lecturer,
                        program=program,
                        room=room,
                        day_of_week=row['day'].strip().upper()[:3],
                        start_time=start_str.strip(),
                        end_time=end_str.strip()
                    )
                    
                    entry.full_clean()
                    entry.save()
                    
                    generate_sessions_for_range(
                        TimetableEntry.objects.filter(pk=entry.pk), 
                        settings.semester_start, 
                        settings.semester_end
                    )
                    
                    results['success'] += 1
                    
                except ObjectDoesNotExist as e:
                    results['failed'] += 1
                    results['errors'].append(f"Row {row_num}: Object not found ({str(e)})")
                except ValidationError as e:
                    results['failed'] += 1
                    results['errors'].append(f"Row {row_num}: Validation Error ({str(e)})")
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"Row {row_num}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"File error: {str(e)}")
            
        return results

    @staticmethod
    def import_elective_enrollments(file_obj, department):
        """
        Imports student-elective registrations from CSV/Excel.
        Columns: Registration No, Course Code, Academic Year, Semester
        """
        from academic.models import ElectiveEnrollment
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            data = BulkImportService._get_data_from_file(file_obj)
            if not data:
                results['errors'].append("The file is empty.")
                return results

            required = ['registration no', 'course code', 'academic year', 'semester']
            if not all(col in data[0] for col in required):
                results['errors'].append(f"Missing required columns: {', '.join(required)}")
                return results

            with transaction.atomic():
                for i, row in enumerate(data):
                    row_num = i + 2
                    reg_no = row.get('registration no', '').strip()
                    course_code = row.get('course code', '').strip()
                    acad_year = row.get('academic year', '').strip()
                    sem_str = row.get('semester', '').strip()

                    if not all([reg_no, course_code, acad_year, sem_str]):
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: Missing required data")
                        continue

                    try:
                        student = User.objects.get(registration_no=reg_no, role=User.Role.STUDENT)
                        course_unit = CourseUnit.objects.get(code=course_code, course_category=CourseUnit.CourseCategory.ELECTIVE)
                        semester = int(sem_str)

                        # Check if course belongs to HOD's department (via programs)
                        if not course_unit.programs.filter(department=department).exists():
                            results['failed'] += 1
                            results['errors'].append(f"Row {row_num}: Course {course_code} does not belong to your department.")
                            continue

                        ElectiveEnrollment.objects.update_or_create(
                            student=student,
                            course_unit=course_unit,
                            academic_year=acad_year,
                            semester=semester
                        )
                        results['success'] += 1
                    except User.DoesNotExist:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: Student with Reg No {reg_no} not found.")
                    except CourseUnit.DoesNotExist:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: Elective course {course_code} not found.")
                    except ValueError:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: Invalid semester value.")
                    except Exception as e:
                        results['failed'] += 1
                        results['errors'].append(f"Row {row_num}: {str(e)}")

        except Exception as e:
            results['errors'].append(f"File error: {str(e)}")
            
        return results
