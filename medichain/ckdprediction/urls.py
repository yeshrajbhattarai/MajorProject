from django.urls import path
from .views import predict_ckd
 
app_name = 'ckdprediction'
 
urlpatterns = [
    path('predict/ckd/', predict_ckd, name='predict_ckd'),
]
 
"""
URL Patterns:
 
POST /api/ml/predict/ckd/
    Request:
    {
        "patient_id": "<uuid>",
        "record_id": "<uuid>"
    }
    
    Response:
    {
        "patient_id": "<uuid>",
        "patient_name": "Priya Sharma",
        "record_id": "<uuid>",
        "prediction": "CKD" | "Not CKD",
        "prediction_code": 0 | 1,
        "confidence": 87.5,
        "ckd_probability": 87.5,
        "not_ckd_probability": 12.5,
        "risk_level": "High" | "Moderate" | "Low-Moderate" | "Low",
        "suggested_action": "Immediate nephrology referral...",
        "imputed_fields": ["field1", "field2"],
        "predicted_by": "<staff_id>",
        "predicted_at": "2024-01-15T10:30:00Z"
    }
 
Note: This endpoint requires IsDoctor permission.
"""