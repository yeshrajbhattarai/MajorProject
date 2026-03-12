from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from .models import ConsentRequest, HospitalIdentity
from .serializers import ConsentCreateSerializer, PatientDecisionSerializer, HospitalDecisionSerializer
import uuid


# ============================================================
# HELPER - creates a basic consent request for reuse in tests
# ============================================================
def make_consent(patient_id="P001", requesting="Apollo", requested_to="Fortis", record_id=None):
    return ConsentRequest.objects.create(
        patient_id=patient_id,
        requesting_hospital=requesting,
        requested_to_hospital=requested_to,
        record_id=record_id
    )


# ============================================================
# 1. MODEL TESTS (12 tests)
# ============================================================
class ConsentRequestModelTests(TestCase):

    # Test 1
    def test_consent_starts_in_pending_state(self):
        """When a consent is created, all statuses should be PENDING by default"""
        consent = make_consent()
        self.assertEqual(consent.request_status, 'PENDING')
        self.assertEqual(consent.patient_choice, 'PENDING')
        self.assertEqual(consent.hospital_choice, 'PENDING')

    # Test 2
    def test_status_approved_when_both_approve(self):
        """Final status should become APPROVED only when both patient and hospital approve"""
        consent = make_consent()
        consent.patient_choice = 'APPROVED'
        consent.hospital_choice = 'APPROVED'
        consent.save()
        self.assertEqual(consent.request_status, 'APPROVED')

    # Test 3
    def test_status_rejected_when_patient_rejects(self):
        """Final status should be REJECTED if patient rejects, regardless of hospital decision"""
        consent = make_consent()
        consent.patient_choice = 'REJECTED'
        consent.hospital_choice = 'APPROVED'
        consent.save()
        self.assertEqual(consent.request_status, 'REJECTED')

    # Test 4
    def test_status_rejected_when_hospital_rejects(self):
        """Final status should be REJECTED if hospital rejects, regardless of patient decision"""
        consent = make_consent()
        consent.patient_choice = 'APPROVED'
        consent.hospital_choice = 'REJECTED'
        consent.save()
        self.assertEqual(consent.request_status, 'REJECTED')

    # Test 5
    def test_status_pending_when_only_patient_approves(self):
        """Final status should stay PENDING if only patient has approved"""
        consent = make_consent()
        consent.patient_choice = 'APPROVED'
        consent.save()
        self.assertEqual(consent.request_status, 'PENDING')

    # Test 6
    def test_status_pending_when_only_hospital_approves(self):
        """Final status should stay PENDING if only hospital has approved"""
        consent = make_consent()
        consent.hospital_choice = 'APPROVED'
        consent.save()
        self.assertEqual(consent.request_status, 'PENDING')

    # Test 7
    def test_consent_id_is_uuid(self):
        """consent_id should be auto-generated as a valid UUID"""
        consent = make_consent()
        self.assertIsInstance(consent.consent_id, uuid.UUID)

    # Test 8
    def test_consent_str_representation(self):
        """__str__ should return the expected string format"""
        consent = make_consent()
        expected = "P001 | Apollo → Fortis | PENDING"
        self.assertEqual(str(consent), expected)

    # Test 9
    def test_record_id_is_optional(self):
        """Creating a consent without record_id should work fine"""
        consent = make_consent(record_id=None)
        self.assertIsNone(consent.record_id)

    # Test 10
    def test_unique_constraint_same_patient_hospitals(self):
        """Creating duplicate consent for same patient + same hospitals should raise error"""
        from django.db import IntegrityError
        make_consent(patient_id="P001", requesting="Apollo", requested_to="Fortis")
        with self.assertRaises(IntegrityError):
            make_consent(patient_id="P001", requesting="Apollo", requested_to="Fortis")

    # Test 11
    def test_same_patient_different_hospitals_allowed(self):
        """Same patient can have consents between different hospital pairs"""
        c1 = make_consent(patient_id="P001", requesting="Apollo", requested_to="Fortis")
        c2 = make_consent(patient_id="P001", requesting="Apollo", requested_to="AIIMS")
        self.assertNotEqual(c1.consent_id, c2.consent_id)

    # Test 12
    def test_hospital_identity_token_auto_generated(self):
        """HospitalIdentity should auto-generate an api_token if not provided"""
        hospital = HospitalIdentity.objects.create(name="TestHospital")
        self.assertIsNotNone(hospital.api_token)
        self.assertEqual(len(hospital.api_token), 64)  # secrets.token_hex(32) = 64 chars


# ============================================================
# 2. SERIALIZER TESTS (8 tests)
# ============================================================
class ConsentSerializerTests(TestCase):

    # Test 13
    def test_create_serializer_valid_data(self):
        """ConsentCreateSerializer should be valid with correct data"""
        data = {
            "patient_id": "P001",
            "requesting_hospital": "Apollo",
            "requested_to_hospital": "Fortis"
        }
        serializer = ConsentCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    # Test 14
    def test_create_serializer_same_hospital_rejected(self):
        """ConsentCreateSerializer should reject if requesting and requested_to are the same hospital"""
        data = {
            "patient_id": "P001",
            "requesting_hospital": "Apollo",
            "requested_to_hospital": "Apollo"
        }
        serializer = ConsentCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    # Test 15
    def test_create_serializer_missing_patient_id(self):
        """ConsentCreateSerializer should fail if patient_id is missing"""
        data = {
            "requesting_hospital": "Apollo",
            "requested_to_hospital": "Fortis"
        }
        serializer = ConsentCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("patient_id", serializer.errors)

    # Test 16
    def test_patient_decision_valid_approved(self):
        """PatientDecisionSerializer should accept APPROVED"""
        consent = make_consent()
        serializer = PatientDecisionSerializer(consent, data={"patient_choice": "APPROVED"}, partial=True)
        self.assertTrue(serializer.is_valid())

    # Test 17
    def test_patient_decision_valid_rejected(self):
        """PatientDecisionSerializer should accept REJECTED"""
        consent = make_consent()
        serializer = PatientDecisionSerializer(consent, data={"patient_choice": "REJECTED"}, partial=True)
        self.assertTrue(serializer.is_valid())

    # Test 18
    def test_patient_decision_invalid_value(self):
        """PatientDecisionSerializer should reject any value other than APPROVED or REJECTED"""
        consent = make_consent()
        serializer = PatientDecisionSerializer(consent, data={"patient_choice": "MAYBE"}, partial=True)
        self.assertFalse(serializer.is_valid())

    # Test 19
    def test_hospital_decision_valid(self):
        """HospitalDecisionSerializer should accept APPROVED"""
        consent = make_consent()
        serializer = HospitalDecisionSerializer(consent, data={"hospital_choice": "APPROVED"}, partial=True)
        self.assertTrue(serializer.is_valid())

    # Test 20
    def test_hospital_decision_invalid_value(self):
        """HospitalDecisionSerializer should reject invalid values"""
        consent = make_consent()
        serializer = HospitalDecisionSerializer(consent, data={"hospital_choice": "YES"}, partial=True)
        self.assertFalse(serializer.is_valid())


# ============================================================
# 3. VIEW / API TESTS (8 tests)
# ============================================================
class ConsentViewTests(TestCase):

    def setUp(self):
        # APIClient is like a fake browser that sends requests to our APIs
        self.client = APIClient()

    # Test 21
    def test_create_consent_valid(self):
        """POST to create_consent with valid data should return 201"""
        data = {
            "patient_id": "P001",
            "requesting_hospital": "Apollo",
            "requested_to_hospital": "Fortis"
        }
        response = self.client.post('/api/consent/request/', data, format='json')
        self.assertEqual(response.status_code, 201)

    # Test 22
    def test_create_consent_missing_fields(self):
        """POST with missing fields should return 400"""
        data = {"patient_id": "P001"}
        response = self.client.post('/api/consent/request/', data, format='json')
        self.assertEqual(response.status_code, 400)

    # Test 23
    def test_view_all_consents(self):
        """GET to view_consent should return 200 and a list"""
        make_consent()
        response = self.client.get('/api/consent/view/')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    # Test 24
    def test_patient_decision_approve(self):
        """PATCH patient-decision with APPROVED should return 200"""
        consent = make_consent()
        url = f'/api/consent/{consent.consent_id}/patient-decision/'
        response = self.client.patch(url, {"patient_choice": "APPROVED"}, format='json')
        self.assertEqual(response.status_code, 200)

    # Test 25
    def test_patient_decision_already_responded(self):
        """PATCH patient-decision after patient already responded should return 400"""
        consent = make_consent()
        consent.patient_choice = 'APPROVED'
        consent.save()
        url = f'/api/consent/{consent.consent_id}/patient-decision/'
        response = self.client.patch(url, {"patient_choice": "REJECTED"}, format='json')
        self.assertEqual(response.status_code, 400)

    # Test 26
    def test_hospital_decision_approve(self):
        """PATCH hospital-decision with APPROVED should return 200"""
        consent = make_consent()
        url = f'/api/consent/{consent.consent_id}/hospital-decision/'
        response = self.client.patch(url, {"hospital_choice": "APPROVED"}, format='json')
        self.assertEqual(response.status_code, 200)

    # Test 27
    def test_delete_pending_consent(self):
        """DELETE a PENDING consent should return 200"""
        consent = make_consent()
        url = f'/api/consent/{consent.consent_id}/delete/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200)

    # Test 28
    def test_delete_approved_consent_blocked(self):
        """DELETE an APPROVED consent should return 400 - cannot delete finalized consent"""
        consent = make_consent()
        consent.patient_choice = 'APPROVED'
        consent.hospital_choice = 'APPROVED'
        consent.save()
        url = f'/api/consent/{consent.consent_id}/delete/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 400)