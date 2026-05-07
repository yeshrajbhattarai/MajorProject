from django.urls import path
from .views import predict_ckd

urlpatterns = [
    path('predict/ckd/', predict_ckd, name='predict_ckd'),
]