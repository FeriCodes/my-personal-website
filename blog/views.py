from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Task, TaskDailyLog
from django.utils import timezone
from datetime import date, timedelta
import calendar
from django.views.decorators.http import require_POST


def home(request):
    return render(request, 'blog/home.html')


def process_task_logic(task):
    now = timezone.now()
    today = now.date()
    current_month = now.strftime("%Y-%m")

    # 1. Reset freezes monthly
    if task.last_freeze_reset != current_month:
        task.freezes_left = 3
        task.last_freeze_reset = current_month
        task.save()

    # 2. Check missed days and update streak/freezes
    if task.last_updated:
        last_date = task.last_updated.date()
        days_passed = (today - last_date).days

        if days_passed == 1:
            if task.status != 'pending':
                task.status = 'pending'
                task.save()
        elif days_passed > 1:
            days_missed = days_passed - 1
            if task.freezes_left >= days_missed:
                task.freezes_left -= days_missed
                task.last_updated = now - timedelta(days=1)
                task.status = 'pending'
                task.save()
            else:
                task.streak = 0
                task.freezes_left = 0
                task.status = 'pending'
                task.save()


def routines_view(request):
    tasks = Task.objects.all()
    # Process logic for all tasks when loading the routines page
    for task in tasks:
        process_task_logic(task)

    context = {'tasks': tasks}
    return render(request, 'blog/routines.html', context)


def update_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if request.method == 'POST':
        # 1. First, check time logic
        process_task_logic(task)

        # 2. Define current time for this function
        now = timezone.now()
        today = now.date()

        # 3. Prevent clicking again on the same day
        if task.last_updated and task.last_updated.date() == today:
            return JsonResponse({'status': 'info', 'message': 'Already completed today'})

        # 4. Perform the update
        task.streak += 1
        if task.streak > task.longest_streak:
            task.longest_streak = task.streak

        task.last_updated = now
        task.status = 'done'
        task.save()

        # 5. Record daily log for contribution calendar
        TaskDailyLog.objects.update_or_create(task=task, date=today, defaults={'status': 'done'})

        return JsonResponse({'status': 'success', 'new_streak': task.streak, 'message': 'Task completed for today!'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


def task_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    today = timezone.localdate()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    # Navigation logic
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # Fetch daily logs for the selected month
    logs = task.daily_logs.filter(date__year=year, date__month=month)
    log_map = {log.date.day: log.status for log in logs}

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)

    calendar_weeks = []
    for week in month_days:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append({'day': '', 'status': 'empty', 'is_today': False})
            else:
                current_day_date = date(year, month, day)
                is_today = current_day_date == today
                day_status = log_map.get(day, 'none')
                week_data.append(
                    {
                        'day': day,
                        'status': day_status,
                        'is_today': is_today,
                        'date_str': current_day_date.strftime("%Y-%m-%d"),
                    }
                )
        calendar_weeks.append(week_data)

    context = {
        'task': task,
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'calendar_weeks': calendar_weeks,
        'today': today,
    }
    return render(request, 'blog/task_detail.html', context)


@login_required
@require_POST
def add_task(request):
    task_name = request.POST.get('task_name', '').strip()
    if task_name:
        Task.objects.create(
            name=task_name,
            streak=0,
            longest_streak=0,
            status='pending',
            freezes_left=3,
            last_freeze_reset=timezone.localdate().strftime('%Y-%m'),
        )
    return redirect('routines')


@login_required
@require_POST
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    task.delete()
    return redirect('routines')
