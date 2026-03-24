"""
Greedy Scheduling Engine for DSAMS.

Workflow:
1. Load all active course units (for department's programs)
2. Load all lecturers assigned to the department
3. Load all rooms
4. Define timeslots (Based on SchedulingParameters)
5. For each course unit:
   a. Determine required number of sessions per week (weekly_hours / slot_duration)
   b. Find an available lecturer (assigned to course unit first, then any dept lecturer)
   c. For each timeslot (ordered by soft constraint preference - mid-day first):
      - Find a room with enough capacity
      - Check no lecturer conflict
      - Check no room conflict
   d. Assign TimetableEntry if slot found; log unscheduled if not
6. Return result summary: scheduled, skipped, errors
"""

from datetime import time, datetime, timedelta
from django.db import transaction
from scheduling.models import TimetableEntry, Room, SchedulingParameters
from academic.models import CourseUnit
from users.models import User
from django.db.models import Case, When, Value, IntegerField


def _is_lecturer_free(lecturer, day, start, end, exclude_pk=None, allow_shared_course_unit=None):
    """Return True if the lecturer has no overlapping TimetableEntry, allowing for shared sessions."""
    qs = TimetableEntry.objects.filter(
        lecturer=lecturer,
        day_of_week=day,
        start_time__lt=end,
        end_time__gt=start,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if allow_shared_course_unit:
        qs = qs.exclude(course_unit=allow_shared_course_unit)
    return not qs.exists()


def _is_room_free(room, day, start, end, exclude_pk=None, allow_shared_course_unit=None, allow_shared_lecturer=None):
    """Return True if the room has no overlapping TimetableEntry, allowing for shared sessions."""
    if room is None:
        return True
    qs = TimetableEntry.objects.filter(
        room=room,
        day_of_week=day,
        start_time__lt=end,
        end_time__gt=start,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if allow_shared_course_unit and allow_shared_lecturer:
        qs = qs.exclude(course_unit=allow_shared_course_unit, lecturer=allow_shared_lecturer)
    return not qs.exists()


def _lecturer_day_load(lecturer, day):
    """Return the number of sessions a lecturer already has on a given day."""
    return TimetableEntry.objects.filter(lecturer=lecturer, day_of_week=day).count()


def run_auto_schedule(department, created_by=None):
    """
    Run the greedy scheduler for a department based on active parameters.
    """
    result = {'scheduled': [], 'skipped': [], 'errors': []}

    # Load active parameters
    params = SchedulingParameters.objects.filter(department=department, is_active=True).first()
    if not params:
        result['errors'].append("No active scheduling parameters found. Please define parameters first.")
        return result

    # 1. Load course units belonging to programs in this department
    course_units = CourseUnit.objects.filter(
        programs__department=department,
        is_active=True
    ).distinct()

    if not course_units.exists():
        result['errors'].append("No active course units found for this department.")
        return result

    # 2. Load lecturers
    # First, get active lecturers in this department
    dept_lecturer_qs = User.objects.filter(role=User.Role.LECTURER, department=department, is_active=True)
    dept_lecturers = list(dept_lecturer_qs)
    
    # Second, identify any lecturers specifically assigned to the units we are scheduling.
    # We MUST include them (even if inactive or from another department) to avoid KeyErrors
    # during workload limit checks.
    assigned_lecturer_ids = [u.lecturer_id for u in course_units if u.lecturer_id]
    if assigned_lecturer_ids:
        # Get all assigned lecturers who aren't already in our list
        current_ids = [l.id for l in dept_lecturers]
        extra_lecturers = User.objects.filter(
            pk__in=assigned_lecturer_ids, 
            role=User.Role.LECTURER
        ).exclude(pk__in=current_ids)
        dept_lecturers.extend(list(extra_lecturers))

    if not dept_lecturers:
        result['errors'].append("No active lecturers found for this department.")
        return result

    # 3. Load all rooms
    rooms = list(Room.objects.all().order_by('capacity'))
    if not rooms:
        result['errors'].append("No rooms configured. Please import rooms first.")
        return result

    # 4. Define dynamic timeslots
    days = params.days_list
    raw_slots = params.get_timeslots()
    
    import random
    
    # Soft constraint: prefer mid-day slots
    # Simple heuristic: sort by distance from middle of the day
    mid_index = len(raw_slots) // 2
    preferred_slot_indices = sorted(range(len(raw_slots)), key=lambda i: abs(i - mid_index))
    
    # Physical lectures: Prefer end of week (reverse chronological)
    DAYS_ORDER = {'MON': 1, 'TUE': 2, 'WED': 3, 'THU': 4, 'FRI': 5, 'SAT': 6, 'SUN': 7}
    physical_days = sorted(days, key=lambda d: DAYS_ORDER.get(d, 0), reverse=True)
    physical_timeslots = [
        (day, raw_slots[si][0], raw_slots[si][1])
        for si in preferred_slot_indices
        for day in physical_days
    ]
    
    # Online lectures: Scatter randomly throughout the week
    online_timeslots = [
        (day, raw_slots[si][0], raw_slots[si][1])
        for si in preferred_slot_indices
        for day in days
    ]
    random.shuffle(online_timeslots)
    # Track per-lecturer weekly session counts and limits
    lecturer_hours = {lec.pk: 0 for lec in dept_lecturers}
    # Pre-calculate hour limit (e.g. 20h / 2h per slot = 10 slots)
    lecturer_slot_limits = {}
    for lec in dept_lecturers:
        try:
            profile = lec.lecturer_profile
            # max_weekly_load is in hours, convert to slots
            lecturer_slot_limits[lec.pk] = profile.max_weekly_load // params.slot_duration_hours
        except:
            # Fallback if profile missing
            lecturer_slot_limits[lec.pk] = 20 // params.slot_duration_hours
    
    # Track per-room weekly session counts for load balancing
    room_weekly_sessions = {r.pk: 0 for r in rooms}

    from academic.models import CourseGroup
    course_groups = CourseGroup.objects.filter(program__department=department, is_active=True)

    if not course_groups.exists():
        result['errors'].append("No course groups found for this department.")
        return result

    # 5. Granular Unit-Group pair scheduling
    # We iterate over every required combination, prioritizing Foundational units across the dept.
    all_pairs = []
    for group in course_groups:
        for unit in group.course_units.filter(is_active=True):
            all_pairs.append((unit, group))
            
    # Sort pairs: Foundational first, then by unit code to encourage clustering
    all_pairs.sort(key=lambda p: (0 if p[0].course_category == 'FOUNDATIONAL' else 1, p[0].code))

    with transaction.atomic():
        for course_unit, current_group in all_pairs:
            # 1. Identify missing modes and already used days for this group
            entries = TimetableEntry.objects.filter(
                course_unit=course_unit,
                course_group=current_group
            )
            existing_modes = list(entries.values_list('teaching_mode', flat=True))
            used_days = list(entries.values_list('day_of_week', flat=True))
            
            missing_modes = []
            if 'PHYSICAL' not in existing_modes: missing_modes.append('PHYSICAL')
            if 'ONLINE' not in existing_modes: missing_modes.append('ONLINE')
            
            if not missing_modes:
                continue
                
            # 2. Try to join existing sessions for the missing modes (Respecting same-day prevention)
            existing_entries = TimetableEntry.objects.filter(
                course_unit=course_unit,
                scheduling_params=params
            ).select_related('lecturer', 'room').distinct()
            
            # Identify unique slots
            existing_slots = []
            seen_slots = set()
            for e in existing_entries:
                slot_key = (e.day_of_week, e.start_time, e.end_time)
                if slot_key not in seen_slots:
                    existing_slots.append(e)
                    seen_slots.add(slot_key)
            
            for existing_entry in existing_slots:
                if existing_entry.teaching_mode not in missing_modes:
                    continue
                
                # Rule: Two sessions of the same unit cannot be on the same day
                if existing_entry.day_of_week in used_days:
                    continue
                
                # Can our group join?
                group_clash = TimetableEntry.objects.filter(
                    course_group=current_group,
                    day_of_week=existing_entry.day_of_week,
                    start_time__lt=existing_entry.end_time,
                    end_time__gt=existing_entry.start_time,
                ).exists()
                
                if not group_clash:
                    # Check room capacity (if physical)
                    total_students = 0
                    if existing_entry.teaching_mode == 'PHYSICAL':
                        other_group_ids = TimetableEntry.objects.filter(
                            day_of_week=existing_entry.day_of_week,
                            start_time=existing_entry.start_time,
                            room=existing_entry.room
                        ).values_list('course_group_id', flat=True)
                        combined_ids = set(list(other_group_ids) + [current_group.pk])
                        total_students = sum(User.objects.filter(role='STUDENT', course_group__pk=gid).count() for gid in combined_ids)
                    
                    if not existing_entry.room or existing_entry.room.capacity >= total_students:
                        TimetableEntry.objects.create(
                            course_unit=course_unit,
                            lecturer=existing_entry.lecturer,
                            program=current_group.program,
                            course_group=current_group,
                            room=existing_entry.room,
                            teaching_mode=existing_entry.teaching_mode,
                            scheduling_params=params,
                            day_of_week=existing_entry.day_of_week,
                            start_time=existing_entry.start_time,
                            end_time=existing_entry.end_time,
                        )
                        missing_modes.remove(existing_entry.teaching_mode)
                        used_days.append(existing_entry.day_of_week)

            if not missing_modes:
                continue

            # 3. Schedule new sessions for remaining missing modes (Respecting same-day prevention)
            if course_unit.lecturer:
                candidate_lecturers = [course_unit.lecturer]
            else:
                is_foundational = (course_unit.course_category == 'FOUNDATIONAL')
                if is_foundational:
                    filtered_pool = [l for l in dept_lecturers if l.username.startswith('TH')]
                else:
                    filtered_pool = [l for l in dept_lecturers if not l.username.startswith('TH')]
                candidate_lecturers = sorted(filtered_pool, key=lambda x: lecturer_hours[x.pk])

            for teaching_mode in missing_modes:
                timeslots = online_timeslots if teaching_mode == 'ONLINE' else physical_timeslots
                assigned = False

                for lecturer in candidate_lecturers:
                    if assigned: break
                    if lecturer_hours[lecturer.pk] >= lecturer_slot_limits.get(lecturer.pk, 10): continue

                    for day, start, end in timeslots:
                        # Rule: Two sessions of the same unit cannot be on the same day
                        if day in used_days:
                            continue
                            
                        limit = 8 // params.slot_duration_hours
                        if _lecturer_day_load(lecturer, day) >= limit: continue
                        if not _is_lecturer_free(lecturer, day, start, end): continue

                        # Is current_group free?
                        group_clash = TimetableEntry.objects.filter(
                            course_group=current_group,
                            day_of_week=day,
                            start_time__lt=end,
                            end_time__gt=start,
                        ).exists()
                        
                        if group_clash: continue
                            
                        if teaching_mode == 'ONLINE':
                            try:
                                entry = TimetableEntry.objects.create(
                                    course_unit=course_unit,
                                    lecturer=lecturer,
                                    program=current_group.program,
                                    course_group=current_group,
                                    room=None,
                                    teaching_mode='ONLINE',
                                    scheduling_params=params,
                                    day_of_week=day,
                                    start_time=start,
                                    end_time=end,
                                )
                                result['scheduled'].append(entry)
                                lecturer_hours[lecturer.pk] += 1
                                assigned = True
                                used_days.append(day)
                                break 
                            except Exception as e:
                                result['errors'].append(f"{course_unit.code} (Online) for {current_group.name}: {str(e)}")
                                break
                        else:
                            # Physical
                            total_students = current_group.users.filter(role='STUDENT').count()
                            valid_rooms = sorted([r for r in rooms if r.capacity >= total_students], key=lambda r: (r.capacity, room_weekly_sessions[r.pk]))

                            if not valid_rooms: valid_rooms = list(rooms)
                                
                            for room in valid_rooms:
                                if not _is_room_free(room, day, start, end): continue
                                try:
                                    entry = TimetableEntry.objects.create(
                                        course_unit=course_unit,
                                        lecturer=lecturer,
                                        program=current_group.program,
                                        course_group=current_group,
                                        room=room,
                                        teaching_mode='PHYSICAL',
                                        scheduling_params=params,
                                        day_of_week=day,
                                        start_time=start,
                                        end_time=end,
                                    )
                                    result['scheduled'].append(entry)
                                    lecturer_hours[lecturer.pk] += 1
                                    room_weekly_sessions[room.pk] += 1
                                    assigned = True
                                    break 
                                except Exception as e:
                                    result['errors'].append(f"{course_unit.code} (Physical) for {current_group.name}: {str(e)}")
                                    break
    
                        if assigned: break

                if not assigned:
                    result['skipped'].append({
                        'course_unit': course_unit,
                        'group': current_group.name,
                        'reason': 'No available conflict-free slot found'
                    })

    return result


def check_manual_conflict(course_unit_id, lecturer_id, room_id, day, start_time, end_time, course_group_id=None, exclude_pk=None):
    """
    Check if a proposed TimetableEntry would conflict with existing ones.
    """
    conflicts = []
    
    # 0. Theology vs Foundational Unit check (New Constraint)
    cu = CourseUnit.objects.get(pk=course_unit_id)
    lec = User.objects.get(pk=lecturer_id)
    is_foundational = (cu.course_category == 'FOUNDATIONAL')
    is_theology_staff = lec.username.startswith('TH')

    if is_foundational and not is_theology_staff:
        conflicts.append({
            'type': 'specialization',
            'message': f"Category Error: Foundational units ('{cu.code}') must be taught by Theology campus staff (TH prefix)."
        })
    elif not is_foundational and is_theology_staff:
        conflicts.append({
            'type': 'specialization',
            'message': f"Category Error: Theology campus staff ('{lec.username}') are ONLY restricted to teaching Foundational units."
        })
    if not _is_lecturer_free(lecturer_id, day, start_time, end_time, exclude_pk, allow_shared_course_unit=course_unit_id):
        conflict_entry = TimetableEntry.objects.filter(
            lecturer_id=lecturer_id,
            day_of_week=day,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if exclude_pk:
            conflict_entry = conflict_entry.exclude(pk=exclude_pk)
        conflict_entry = conflict_entry.exclude(course_unit_id=course_unit_id).first()
        
        if conflict_entry:
            conflicts.append({
                'type': 'lecturer',
                'message': f"Lecturer is already scheduled for {conflict_entry.course_unit.code} at {conflict_entry.start_time.strftime('%H:%M')} on {day}."
            })

    # Room conflict
    if room_id and not _is_room_free(room_id, day, start_time, end_time, exclude_pk, allow_shared_course_unit=course_unit_id, allow_shared_lecturer=lecturer_id):
        conflict_entry = TimetableEntry.objects.filter(
            room_id=room_id,
            day_of_week=day,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if exclude_pk:
            conflict_entry = conflict_entry.exclude(pk=exclude_pk)
        conflict_entry = conflict_entry.exclude(course_unit_id=course_unit_id, lecturer_id=lecturer_id).first()

        if conflict_entry:
            conflicts.append({
                'type': 'room',
                'message': f"Room is already booked for {conflict_entry.course_unit.code} at {conflict_entry.start_time.strftime('%H:%M')} on {day}."
            })

    # Group conflict (Students)
    if course_group_id:
        group_conflict = TimetableEntry.objects.filter(
            course_group_id=course_group_id,
            day_of_week=day,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if exclude_pk:
            group_conflict = group_conflict.exclude(pk=exclude_pk)
        
        if group_conflict.exists():
            conflict_entry = group_conflict.first()
            conflicts.append({
                'type': 'group',
                'message': f"Class Group already has {conflict_entry.course_unit.code} scheduled at this time."
            })

    # Course clash (Duplicate session for same unit/group/time?)
    qs = TimetableEntry.objects.filter(
        course_unit_id=course_unit_id,
        course_group_id=course_group_id, # Added to distinguish
        day_of_week=day,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        conflicts.append({
            'type': 'course',
            'message': f"This course unit is already assigned an overlapping slot for this group on {day}."
        })

    return conflicts
