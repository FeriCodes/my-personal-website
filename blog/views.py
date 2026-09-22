from django.shortcuts import render
from django.tasks import Task
from .models import Task


def home(request):
    return render(request, "blog/home.html")


def routines_view(request):
    tasks = Task.objects.all()
    return render(request, 'blog/routines.html', {'tasks': tasks})
