from django.urls import path
from . import views

urlpatterns = [
    path('', views.hospital_register, name='hospital_register'),
    path('login/', views.hospital_login, name='hospital_login'),
]
