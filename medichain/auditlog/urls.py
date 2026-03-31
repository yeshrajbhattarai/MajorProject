from django.urls import path
from . import views

urlpatterns = [
    path('', views.view_logs, name='view_logs'),
]