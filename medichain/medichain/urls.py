
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('',           include('hospitals.urls')),
    path('api/v1/',    include('hospitals.api_urls')),        
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  
    path('admin/',     admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)