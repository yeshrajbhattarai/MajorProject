from django.urls import path
from .views import create_consent, view_consent, sent_requests, consent_detail, received_requests, patient_decision, hospital_decision,delete_consent,fetch_record

urlpatterns = [
    path('request/', create_consent),
    path('view/', view_consent),
    
    # Filtered View:
    path('sent/', sent_requests, name='sent_requests'),
    path('received/', received_requests, name='received_requests'),
    
    # single consent
    path('<uuid:consent_id>/', consent_detail, name='consent_detail'),
    path('<uuid:consent_id>/patient-decision/', patient_decision, name='patient_decision'),
    path('<uuid:consent_id>/hospital-decision/', hospital_decision, name='hospital_decision'),
    path('<uuid:consent_id>/delete/', delete_consent, name='delete_consent'),
    path('<uuid:consent_id>/fetch-record/', fetch_record, name='fetch_record'),
    
]