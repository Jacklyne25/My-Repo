import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from datetime import time, datetime
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy

from users.models import User
from academic.models import CourseUnit, Program, Department, CourseGroup
from scheduling.models import TimetableEntry, Room, SchedulingRun, SchedulingParameters
from scheduling.engine import run_auto_schedule, check_manual_conflict
from core.services import AlertService


class HODOrSchedulerMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role in ('HOD', 'SYSTEM_ADMIN')

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied
        return super().handle_no_permission()


def get_timetable_grid_data(params, group_id=None):
    """
    Helper function to build the grid data for the timetable view.
    Returns: (grid, days_list)
    """
    days = params.days_list
    timeslots = params.get_timeslots()
    
    entries = TimetableEntry.objects.filter(scheduling_params=params).select_related('course_unit', 'lecturer', 'room', 'course_group')
    
    if group_id:
        entries = entries.filter(course_group_id=group_id)
        
    grid = []
    for start, end in timeslots:
        row = {
            'time': f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}",
            'slots': []
        }
        for day in days:
            # For department view, we might have multiple concurrent sessions in the same slot (different groups/rooms)
            slot_entries = entries.filter(day_of_week=day, start_time=start)
            row['slots'].append({
                'day': day, 
                'entries': list(slot_entries),
                # For manual form interaction, we still need a flag if ANY entry exists
                'has_entry': slot_entries.exists()
            })
        grid.append(row)
        
    return grid, days

class SchedulingDashboardView(LoginRequiredMixin, HODOrSchedulerMixin, View):
    """Step 1-3 Landing: Upload Data, Define Parameters, Choose Mode."""
    template_name = 'scheduling/dashboard.html'

    def get(self, request):
        dept = request.user.department
        
        params = SchedulingParameters.objects.filter(department=dept, is_active=True).first()
        
        # Check counts for Step 1
        course_count = CourseUnit.objects.filter(programs__department=dept, is_active=True).distinct().count()
        room_count = Room.objects.count()

        # Check counts for Step 3
        groups_with_units = CourseGroup.objects.filter(program__department=dept, course_units__isnull=False, is_active=True).distinct().count()
        total_groups = CourseGroup.objects.filter(program__department=dept, is_active=True).count()
        
        return render(request, self.template_name, {
            'params': params,
            'course_count': course_count,
            'room_count': room_count,
            'groups_with_units': groups_with_units,
            'total_groups': total_groups,
            'day_choices': [('MON', 'MON'), ('TUE', 'TUE'), ('WED', 'WED'), ('THU', 'THU'), ('FRI', 'FRI')]
        })


class SetParametersView(LoginRequiredMixin, HODOrSchedulerMixin, View):
    """Step 2: Define Scheduling Parameters."""
    def post(self, request):
        dept = request.user.department
        study_time = request.POST.get('study_time', 'DAY')
        cohort = request.POST.get('cohort', 'EASTER')
        year = request.POST.get('year', '2026/2027')
        days = request.POST.getlist('days')
        start = request.POST.get('start_time', '08:00')
        end = request.POST.get('end_time', '17:00')
        duration = int(request.POST.get('duration', 2))

        # Deactivate old params
        SchedulingParameters.objects.filter(department=dept, is_active=True).update(is_active=False)

        SchedulingParameters.objects.create(
            department=dept,
            study_time=study_time,
            cohort=cohort,
            academic_year=year,
            available_days=','.join(days),
            day_start_time=start,
            day_end_time=end,
            slot_duration_hours=duration,
            is_active=True
        )
        messages.success(request, "Scheduling parameters defined successfully.")
        return redirect('scheduling:dashboard')


class AutoScheduleView(LoginRequiredMixin, HODOrSchedulerMixin, View):
    """Step 4: Auto generation."""
    def post(self, request):
        dept = request.user.department
        
        # Wipe existing auto entries for this dept/params to have a clean slate if requested?
        # User might want to additive. Let's keep existing for now.
        
        run = SchedulingRun.objects.create(
            department=dept,
            created_by=request.user,
            status=SchedulingRun.Status.PENDING,
            mode=SchedulingRun.Mode.AUTO,
        )

        result = run_auto_schedule(dept, created_by=request.user)

        run.status = SchedulingRun.Status.COMPLETED
        run.notes = f"Scheduled: {len(result['scheduled'])}, Skipped: {len(result['skipped'])}"
        run.save()

        return redirect('scheduling:conflict_review')


class ConflictReviewView(LoginRequiredMixin, HODOrSchedulerMixin, View):
    """Step 5: Conflict review."""
    template_name = 'scheduling/conflict_review.html'

    def get(self, request):
        dept = request.user.department
        
        
        # Unscheduled course units
        
        active_groups = CourseGroup.objects.filter(program__department=dept, is_active=True)
        all_units = CourseUnit.objects.filter(course_groups__in=active_groups, is_active=True).distinct()
        scheduled_unit_ids = TimetableEntry.objects.filter(program__department=dept).values_list('course_unit_id', flat=True)
        
        unscheduled = all_units.exclude(id__in=scheduled_unit_ids)
        
        total = all_units.count()
        success_count = total - unscheduled.count()
        perc = (success_count / total * 100) if total > 0 else 0

        return render(request, self.template_name, {
            'unscheduled': unscheduled,
            'total': total,
            'success_count': success_count,
            'percentage': round(perc, 1),
        })


class ManualScheduleView(LoginRequiredMixin, HODOrSchedulerMixin, View):
    """Step 3b & 6: Create Timetable Manually / Adjust conflicts."""
    template_name = 'scheduling/manual_form.html'

    def _get_context(self, request):
        dept = request.user.department
        from academic.models import CourseGroup
        params = SchedulingParameters.objects.filter(department=dept, is_active=True).first()
        
        # Course Units tied to active class groups
        active_groups = CourseGroup.objects.filter(program__department=dept, is_active=True)
        course_units = CourseUnit.objects.filter(course_groups__in=active_groups, is_active=True).distinct()
        
        group_id = request.GET.get('group')
        grid_data, days = get_timetable_grid_data(params, group_id=group_id) if params else ([], [])
        
        context = {
            'course_units': course_units,
            'course_groups': active_groups.distinct(),
            'selected_group_id': group_id,
            'lecturers': User.objects.filter(role=User.Role.LECTURER, department=dept, is_active=True),
            'rooms': Room.objects.all().order_by('name'),
            'days_options': [('MON', 'Monday'), ('TUE', 'Tuesday'), ('WED', 'Wednesday'), ('THU', 'Thursday'), ('FRI', 'Friday')],
            'params': params,
            'time_slots': params.get_timeslots() if params else [],
            'grid': grid_data,
            'days': days
        }
        return context

    def get(self, request):
        return render(request, self.template_name, self._get_context(request))

    def post(self, request):
        dept = request.user.department
        try:
            course_unit = get_object_or_404(CourseUnit, pk=request.POST.get('course_unit'))
            from academic.models import CourseGroup
            course_group = get_object_or_404(CourseGroup, pk=request.POST.get('course_group'))
            lecturer = get_object_or_404(User, pk=request.POST.get('lecturer'))
            
            teaching_mode = request.POST.get('teaching_mode', 'PHYSICAL')
            room = None
            if teaching_mode == 'PHYSICAL':
                room = get_object_or_404(Room, pk=request.POST.get('room'))
                
            day = request.POST.get('day')
            slot = request.POST.get('slot') # "HH:MM-HH:MM"
            
            start_str, end_str = slot.split('-')
            start_time = time.fromisoformat(start_str)
            end_time = time.fromisoformat(end_str)

            conflicts = check_manual_conflict(
                course_unit.pk, lecturer.pk, room.pk if room else None, day, start_time, end_time,
                course_group_id=course_group.pk
            )
            if conflicts:
                for c in conflicts:
                    messages.warning(request, f"Conflict: {c['message']}")
                return render(request, self.template_name, self._get_context(request))

            params = SchedulingParameters.objects.filter(department=dept, is_active=True).first()
            TimetableEntry.objects.create(
                course_unit=course_unit, course_group=course_group,
                lecturer=lecturer, program=course_group.program,
                room=room, teaching_mode=teaching_mode, scheduling_params=params,
                day_of_week=day, start_time=start_time, end_time=end_time
            )
            messages.success(request, f"Scheduled {course_unit.code} manually ({teaching_mode}).")
            return redirect('scheduling:conflict_review')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return render(request, self.template_name, self._get_context(request))


class TimetableDeleteView(LoginRequiredMixin, HODOrSchedulerMixin, View):
    def post(self, request, pk):
        entry = get_object_or_404(TimetableEntry, pk=pk)
        if entry.program.department != request.user.department:
            raise PermissionDenied
        entry.delete()
        messages.success(request, "Entry removed.")
        return redirect(request.META.get('HTTP_REFERER', 'scheduling:dashboard'))

class TimetableListView(LoginRequiredMixin, HODOrSchedulerMixin, ListView):
    model = SchedulingParameters
    template_name = 'scheduling/timetable_list.html'
    context_object_name = 'timetables'

    def get_queryset(self):
        return SchedulingParameters.objects.filter(department=self.request.user.department).order_by('-created_at')

class TimetableGridView(LoginRequiredMixin, HODOrSchedulerMixin, View):
    """Step 7: Visual Timetable Output (Grid view)."""
    template_name = 'scheduling/timetable_grid.html'

    def get(self, request, pk=None):
        dept = request.user.department
        if pk:
            params = get_object_or_404(SchedulingParameters, pk=pk, department=dept)
        else:
            params = SchedulingParameters.objects.filter(department=dept, is_active=True).first()
            
        if not params:
            messages.info(request, "Please define scheduling parameters first.")
            return redirect('scheduling:dashboard')

        from academic.models import CourseGroup
        group_id = request.GET.get('group')
        grid, days = get_timetable_grid_data(params, group_id=group_id)

        # Timetable Compliance Metric (2-sessions-per-week rule)
        groups = CourseGroup.objects.filter(program__department=dept, is_active=True)
        total_unit_group_pairs = 0
        compliant_pairs = 0
        
        for group in groups:
            for unit in group.course_units.filter(is_active=True):
                total_unit_group_pairs += 1
                session_count = TimetableEntry.objects.filter(
                    course_unit=unit,
                    course_group=group,
                    scheduling_params=params
                ).count()
                if session_count >= 2:
                    compliant_pairs += 1
        
        timetable_compliance = round((compliant_pairs / total_unit_group_pairs * 100), 1) if total_unit_group_pairs > 0 else 100

        return render(request, self.template_name, {
            'grid': grid,
            'days': days,
            'params': params,
            'timetable_compliance': timetable_compliance,
            'is_historical': pk is not None and not params.is_active,
            'course_groups': groups,
            'selected_group_id': group_id
        })

class TimetableDeleteTimetableView(LoginRequiredMixin, HODOrSchedulerMixin, View):
    def post(self, request, pk):
        params = get_object_or_404(SchedulingParameters, pk=pk)
        if params.department != request.user.department:
            raise PermissionDenied
        
        params.delete() # Entries deleted via cascade
        messages.success(request, "Timetable and all its entries have been deleted.")
        return redirect('scheduling:timetable_list')


class TimetableConflictCheckView(LoginRequiredMixin, View):
    def post(self, request):
        data = json.loads(request.body)
        conflicts = check_manual_conflict(
            data.get('course_unit_id'), data.get('lecturer_id'), data.get('room_id'),
            data.get('day'), time.fromisoformat(data.get('start_time')), 
            time.fromisoformat(data.get('end_time')),
            course_group_id=data.get('course_group_id')
        )
        return JsonResponse({'conflicts': conflicts})


class PublishTimetableView(LoginRequiredMixin, HODOrSchedulerMixin, View):
    """Publish the active timetable and notify lecturers/students."""
    def post(self, request):
        dept = request.user.department
        params = SchedulingParameters.objects.filter(department=dept, is_active=True).first()
        
        if not params:
            messages.error(request, "No active scheduling parameters found.")
            return redirect('scheduling:dashboard')
        
        # Pre-publishing Rule Validation (2-sessions-per-week)
        from academic.models import CourseGroup
        groups = CourseGroup.objects.filter(program__department=dept, is_active=True)
        compliance_errors = []
        
        for group in groups:
            for unit in group.course_units.filter(is_active=True):
                session_count = TimetableEntry.objects.filter(
                    course_unit=unit,
                    course_group=group,
                    scheduling_params=params
                ).count()
                if session_count < 2:
                    compliance_errors.append(f"{unit.code} for {group.name} (Has {session_count}/2)")

        if compliance_errors:
            messages.warning(request, f"Timetable published with {len(compliance_errors)} rule violations (missing sessions). Please review the Monitoring Dashboard.")
            # We still allow publishing but with a loud warning. 
            # Alternatively, we could block it, but flexibility is often needed in early stages.
        
        if not params.is_published:
            params.is_published = True
            params.save()
            
            # Send notification
            AlertService.notify_timetable_published(dept)
            messages.success(request, "Timetable published successfully. Notifications sent.")
        else:
            messages.info(request, "Timetable is already published.")
            
        return redirect('scheduling:timetable_grid')


class TimetableUpdateView(LoginRequiredMixin, HODOrSchedulerMixin, View):
    """Reschedule an existing entry and notify students."""
    template_name = 'scheduling/manual_form.html'

    def get(self, request, pk):
        entry = get_object_or_404(TimetableEntry, pk=pk)
        if entry.program.department != request.user.department:
            raise PermissionDenied
            
        dept = request.user.department
        params = SchedulingParameters.objects.filter(department=dept, is_active=True).first()
        
        context = {
            'entry': entry,
            'course_units': CourseUnit.objects.filter(programs__department=dept, is_active=True).distinct(),
            'lecturers': User.objects.filter(role=User.Role.LECTURER, department=dept, is_active=True),
            'rooms': Room.objects.all().order_by('name'),
            'days_options': [('MON', 'Monday'), ('TUE', 'Tuesday'), ('WED', 'Wednesday'), ('THU', 'Thursday'), ('FRI', 'Friday')],
            'params': params,
            'time_slots': params.get_timeslots() if params else []
        }
        if params:
            grid, grid_days = get_timetable_grid_data(params)
            context['grid'] = grid
            context['days'] = grid_days
        return render(request, self.template_name, context)

    def post(self, request, pk):
        entry = get_object_or_404(TimetableEntry, pk=pk)
        if entry.program.department != request.user.department:
            raise PermissionDenied
            
        old_day = entry.get_day_of_week_display()
        old_start = entry.start_time.strftime('%H:%M')
        
        try:
            day = request.POST.get('day')
            slot = request.POST.get('slot')
            start_str, end_str = slot.split('-')
            start_time = time.fromisoformat(start_str)
            end_time = time.fromisoformat(end_str)
            room = get_object_or_404(Room, pk=request.POST.get('room'))
            lecturer = get_object_or_404(User, pk=request.POST.get('lecturer'))

            conflicts = check_manual_conflict(
                entry.course_unit.pk, lecturer.pk, room.pk, day, start_time, end_time, exclude_pk=entry.pk
            )
            
            if conflicts:
                for c in conflicts:
                    messages.warning(request, f"Conflict: {c['message']}")
                return redirect('scheduling:update_entry', pk=pk)

            entry.day_of_week = day
            entry.start_time = start_time
            entry.end_time = end_time
            entry.room = room
            entry.lecturer = lecturer
            entry.save()
            
            # Send notification
            AlertService.notify_lecture_rescheduled(entry, old_day, old_start)
            
            messages.success(request, f"Rescheduled {entry.course_unit.code} successfully.")
            return redirect('scheduling:timetable_grid')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('scheduling:update_entry', pk=pk)
class RoomListView(LoginRequiredMixin, HODOrSchedulerMixin, ListView):
    model = Room
    template_name = 'scheduling/room_list.html'
    context_object_name = 'rooms'

    def get_queryset(self):
        return Room.objects.all().order_by('name')

class RoomCreateView(LoginRequiredMixin, HODOrSchedulerMixin, CreateView):
    model = Room
    template_name = 'scheduling/room_form.html'
    fields = ['name', 'capacity']
    success_url = reverse_lazy('scheduling:room_list')

    def form_valid(self, form):
        messages.success(self.request, f"Room {form.instance.name} added successfully.")
        return super().form_valid(form)

class RoomUpdateView(LoginRequiredMixin, HODOrSchedulerMixin, UpdateView):
    model = Room
    template_name = 'scheduling/room_form.html'
    fields = ['name', 'capacity']
    success_url = reverse_lazy('scheduling:room_list')

    def form_valid(self, form):
        messages.success(self.request, f"Room {form.instance.name} updated successfully.")
        return super().form_valid(form)

class RoomDeleteView(LoginRequiredMixin, HODOrSchedulerMixin, DeleteView):
    model = Room
    success_url = reverse_lazy('scheduling:room_list')
    
    def post(self, request, *args, **kwargs):
        room = self.get_object()
        messages.success(request, f"Room {room.name} deleted successfully.")
        return super().post(request, *args, **kwargs)
