import calendar
import json
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Task, TaskDailyLog


def home(request):
    return render(request, 'blog/home.html')


def process_task_logic(task):
    today = timezone.localdate()
    current_month = today.strftime("%Y-%m")

    # 1. Reset freezes monthly
    if task.last_freeze_reset != current_month:
        task.freezes_left = 3
        task.last_freeze_reset = current_month
        task.save()

    if not task.last_updated:
        return

    last_date = timezone.localtime(task.last_updated).date()
    days_passed = (today - last_date).days

    if days_passed <= 0:
        return

    if days_passed == 1:
        if task.status != 'pending':
            task.status = 'pending'
            task.save()
        return

    # 2. Process missed days and apply freezes if available
    for i in range(1, days_passed):
        missed_date = last_date + timedelta(days=i)
        if task.freezes_left > 0 and task.streak > 0:
            task.freezes_left -= 1
            log_status = 'frozen'
        else:
            task.streak = 0
            log_status = 'missed'
        TaskDailyLog.objects.update_or_create(task=task, date=missed_date, defaults={'status': log_status})

    # Set last_updated to yesterday to prevent reprocessing missed days
    task.last_updated = timezone.now() - timedelta(days=1)
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

        # 2. Define current time for this function using localdate
        now = timezone.now()
        today = timezone.localdate()

        # 3. Prevent clicking again on the same day
        if task.last_updated and timezone.localtime(task.last_updated).date() == today and task.status == 'done':
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
    process_task_logic(task)
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
                week_data.append({'day': '', 'status': 'empty', 'is_today': False, 'is_future': False})
            else:
                current_day_date = date(year, month, day)
                is_today = current_day_date == today
                is_future = current_day_date > today
                day_status = log_map.get(day, 'none')
                week_data.append(
                    {
                        'day': day,
                        'status': day_status,
                        'is_today': is_today,
                        'is_future': is_future,
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
def toggle_day_log(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    try:
        data = json.loads(request.body)
        date_str = data.get('date')
        target_date = date.fromisoformat(date_str)
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid date format'}, status=400)

    today = timezone.localdate()
    if target_date > today:
        return JsonResponse({'status': 'error', 'message': 'Cannot mark future dates!'}, status=400)

    existing_log = TaskDailyLog.objects.filter(task=task, date=target_date).first()
    old_status = existing_log.status if existing_log else 'none'

    if old_status == 'done':
        return JsonResponse({'status': 'info', 'message': 'This day is already marked as Done!'})

    # 1. Refund freeze if the day was previously frozen
    if old_status == 'frozen':
        task.freezes_left += 1

    # 2. Update or create daily log as 'done'
    TaskDailyLog.objects.update_or_create(task=task, date=target_date, defaults={'status': 'done'})

    # 3. Increment streak and update longest streak if needed
    task.streak += 1
    if task.streak > task.longest_streak:
        task.longest_streak = task.streak

    # 4. Update task status if the selected date is today
    if target_date == today:
        task.status = 'done'
        task.last_updated = timezone.now()

    task.save()

    return JsonResponse(
        {
            'status': 'success',
            'new_status': 'done',
            'new_streak': task.streak,
            'longest_streak': task.longest_streak,
            'freezes_left': task.freezes_left,
            'is_today': target_date == today,
            'message': f'Marked {date_str} as Done!',
        }
    )


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
            last_freeze_reset=timezone.localdate().strftime("%Y-%m"),
        )
    return redirect('routines')


@login_required
@require_POST
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    task.delete()
    return redirect('routines')
