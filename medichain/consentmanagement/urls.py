from django.urls import path
from .views import (
    create_consent,
    view_consent,
    sent_requests,
    received_requests,
    consent_detail,
    patient_decision,
    hospital_decision,
    fetch_record,
    hospital_directory,
    patient_search,
    verify_hash,
)

urlpatterns = [
    # Create a new consent request
    path('request/', create_consent),

    # Dev-only: view all consents without auth — remove before production
    path('view/', view_consent),  #! dev only

    # Filtered lists — auth required, hospital identity from JWT
    path('sent/',     sent_requests,    name='sent_requests'),
    path('received/', received_requests, name='received_requests'),

    # Single consent — GET for detail, DELETE to withdraw (merged view)
    path('<uuid:consent_id>/',                   consent_detail,    name='consent_detail'),
    # Legacy/delete path used by tests and some clients — maps to same view that handles DELETE
    path('<uuid:consent_id>/delete/',            consent_detail,    name='consent_delete'),
    path('<uuid:consent_id>/patient-decision/',  patient_decision,  name='patient_decision'),
    path('<uuid:consent_id>/hospital-decision/', hospital_decision, name='hospital_decision'),
    
    path('<uuid:consent_id>/verify-hash/', verify_hash, name='verify_hash'),
    path('<uuid:consent_id>/fetch-record/',      fetch_record,      name='fetch_record'),

    # Hospital picker — used by frontend NewConsentModal
    path('hospitals/', hospital_directory, name='hospital_directory'),

    # Patient phone search — used by frontend PatientPickerModal
    path('patients/search/', patient_search, name='patient_search'),
]