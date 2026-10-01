from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path('routines/', views.routines_view, name='routines'),
    path('routines/update/<int:task_id>/', views.update_task, name='update_task'),
    path('routines/<int:task_id>/', views.task_detail, name='task_detail'),
]
