

from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.consent_request,name="consent_request")
]
