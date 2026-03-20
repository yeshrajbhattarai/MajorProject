from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('hospitals.urls')),
    path("admin/", admin.site.urls),
    path("api/consent/", include('consentmanagement.urls')),
    path("api/logs/", include('auditlog.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)