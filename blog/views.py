from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Task


def home(request):
    return render(request, "blog/home.html")


def routines_view(request):
    tasks = Task.objects.all()
    return render(request, 'blog/routines.html', {'tasks': tasks})


def update_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == 'POST':
        task.streak += 1

        if task.streak > task.longest_streak:
            task.longest_streak = task.streak

        task.status = 'done'
        task.save()

        return JsonResponse({'status': 'success', 'new_streak': task.streak})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
