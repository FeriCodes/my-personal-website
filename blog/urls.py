from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path('routines/', views.routines_view, name='routines'),
]
