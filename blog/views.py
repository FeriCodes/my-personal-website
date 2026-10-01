from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Task, TaskDailyLog
from django.utils import timezone
from datetime import timedelta


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
    # Get all logs for this task ordered by date
    logs = task.daily_logs.order_by('-date')

    context = {
        'task': task,
        'logs': logs,
    }
    return render(request, 'blog/task_detail.html', context)
