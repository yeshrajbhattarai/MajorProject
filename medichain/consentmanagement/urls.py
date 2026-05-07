from django.conf import settings
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
    path('request/', create_consent),
    path('sent/',     sent_requests,    name='sent_requests'),
    path('received/', received_requests, name='received_requests'),
    path('<uuid:consent_id>/',                   consent_detail,    name='consent_detail'),
    path('<uuid:consent_id>/delete/',            consent_detail,    name='consent_delete'),
    path('<uuid:consent_id>/patient-decision/',  patient_decision,  name='patient_decision'),
    path('<uuid:consent_id>/hospital-decision/', hospital_decision, name='hospital_decision'),
    path('<uuid:consent_id>/verify-hash/',       verify_hash,       name='verify_hash'),
    path('<uuid:consent_id>/fetch-record/',      fetch_record,      name='fetch_record'),
    path('hospitals/', hospital_directory, name='hospital_directory'),
    path('patients/search/', patient_search, name='patient_search'),
]

if settings.DEBUG:
    urlpatterns += [path('view/', view_consent)]