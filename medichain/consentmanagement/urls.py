from django.urls import path
from .views import create_consent

urlpatterns = [
    path('request/', create_consent),
]