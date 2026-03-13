from django.test import TestCase
from rest_framework.test import APIClient
from .models import ConsentRequest
from .serializers import ConsentCreateSerializer, PatientDecisionSerializer, HospitalDecisionSerializer
from hospitals.models import Hospital
import uuid


# ── HELPER ────────────────────────────────────────────────────────────────────
# Creates a basic consent request so we don't repeat this in every test
def make_consent(patient_id="P001", requesting="Apollo", requested_to="Fortis", record_id=None):
    return ConsentRequest.objects.create(
        patient_id=patient_id,
        requesting_hospital=requesting,
        requested_to_hospital=requested_to,
        record_id=record_id
    )

# Creates a real Hospital in the test database and returns it
def make_hospital(name="Apollo", email="apollo@test.com", contact="9876543210"):
    return Hospital.objects.create(
        hospital_name=name,
        email=email,
        password_hash="fakehash",
        contact_number=contact
    )


# ── MODEL TESTS ───────────────────────────────────────────────────────────────
class ConsentRequestModelTests(TestCase):

    # Test 1 - when a consent is created, all choices start as PENDING
    def test_consent_starts_in_pending_state(self):
        consent = make_consent()
        self.assertEqual(consent.request_status, 'PENDING')
        self.assertEqual(consent.patient_choice, 'PENDING')
        self.assertEqual(consent.hospital_choice, 'PENDING')

    # Test 2 - final status becomes APPROVED only when both sides approve
    def test_status_approved_when_both_approve(self):
        consent = make_consent()
        consent.patient_choice = 'APPROVED'
        consent.hospital_choice = 'APPROVED'
        consent.save()
        self.assertEqual(consent.request_status, 'APPROVED')

    # Test 3 - final status is REJECTED if patient rejects, even if hospital approves
    def test_status_rejected_when_patient_rejects(self):
        consent = make_consent()
        consent.patient_choice = 'REJECTED'
        consent.hospital_choice = 'APPROVED'
        consent.save()
        self.assertEqual(consent.request_status, 'REJECTED')

    # Test 4 - final status is REJECTED if hospital rejects, even if patient approves
    def test_status_rejected_when_hospital_rejects(self):
        consent = make_consent()
        consent.patient_choice = 'APPROVED'
        consent.hospital_choice = 'REJECTED'
        consent.save()
        self.assertEqual(consent.request_status, 'REJECTED')

    # Test 5 - status stays PENDING if only patient has approved, hospital has not responded yet
    def test_status_pending_when_only_patient_approves(self):
        consent = make_consent()
        consent.patient_choice = 'APPROVED'
        consent.save()
        self.assertEqual(consent.request_status, 'PENDING')

    # Test 6 - status stays PENDING if only hospital has approved, patient has not responded yet
    def test_status_pending_when_only_hospital_approves(self):
        consent = make_consent()
        consent.hospital_choice = 'APPROVED'
        consent.save()
        self.assertEqual(consent.request_status, 'PENDING')

    # Test 7 - consent_id must be a valid UUID, not a plain integer or string
    def test_consent_id_is_uuid(self):
        consent = make_consent()
        self.assertIsInstance(consent.consent_id, uuid.UUID)

    # Test 8 - the string representation of a consent should follow the expected format
    def test_consent_str_representation(self):
        consent = make_consent()
        expected = "P001 | Apollo → Fortis | PENDING"
        self.assertEqual(str(consent), expected)

    # Test 9 - record_id is optional, a consent should be created fine without it
    def test_record_id_is_optional(self):
        consent = make_consent(record_id=None)
        self.assertIsNone(consent.record_id)

    # Test 10 - same patient cannot have two consents between the exact same pair of hospitals
    def test_unique_constraint_same_patient_hospitals(self):
        from django.db import IntegrityError
        make_consent(patient_id="P001", requesting="Apollo", requested_to="Fortis")
        with self.assertRaises(IntegrityError):
            make_consent(patient_id="P001", requesting="Apollo", requested_to="Fortis")

    # Test 11 - same patient can have consents with different hospital combinations
    def test_same_patient_different_hospitals_allowed(self):
        c1 = make_consent(patient_id="P001", requesting="Apollo", requested_to="Fortis")
        c2 = make_consent(patient_id="P001", requesting="Apollo", requested_to="AIIMS")
        self.assertNotEqual(c1.consent_id, c2.consent_id)

    # Test 12 - every hospital should get a unique api_key automatically when created
    def test_hospital_api_key_auto_generated(self):
        hospital = make_hospital()
        self.assertIsNotNone(hospital.api_key)


# ── SERIALIZER TESTS ──────────────────────────────────────────────────────────
class ConsentSerializerTests(TestCase):

    # Test 13 - serializer should pass when both hospitals exist and are different
    def test_create_serializer_valid_data(self):
        make_hospital(name="Apollo", email="apollo@test.com", contact="9876543210")
        make_hospital(name="Fortis", email="fortis@test.com", contact="9876543211")
        data = {
            "patient_id": "P001",
            "requesting_hospital": "Apollo",
            "requested_to_hospital": "Fortis"
        }
        serializer = ConsentCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    # Test 14 - serializer should reject if requesting and requested_to hospital are the same
    def test_create_serializer_same_hospital_rejected(self):
        make_hospital(name="Apollo", email="apollo@test.com", contact="9876543210")
        data = {
            "patient_id": "P001",
            "requesting_hospital": "Apollo",
            "requested_to_hospital": "Apollo"
        }
        serializer = ConsentCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    # Test 15 - serializer should fail if patient_id is missing from the request
    def test_create_serializer_missing_patient_id(self):
        make_hospital(name="Apollo", email="apollo@test.com", contact="9876543210")
        make_hospital(name="Fortis", email="fortis@test.com", contact="9876543211")
        data = {
            "requesting_hospital": "Apollo",
            "requested_to_hospital": "Fortis"
        }
        serializer = ConsentCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("patient_id", serializer.errors)

    # Test 16 - serializer should accept APPROVED as a valid patient choice
    def test_patient_decision_valid_approved(self):
        consent = make_consent()
        serializer = PatientDecisionSerializer(consent, data={"patient_choice": "APPROVED"}, partial=True)
        self.assertTrue(serializer.is_valid())

    # Test 17 - serializer should accept REJECTED as a valid patient choice
    def test_patient_decision_valid_rejected(self):
        consent = make_consent()
        serializer = PatientDecisionSerializer(consent, data={"patient_choice": "REJECTED"}, partial=True)
        self.assertTrue(serializer.is_valid())

    # Test 18 - serializer should reject any value other than APPROVED or REJECTED
    def test_patient_decision_invalid_value(self):
        consent = make_consent()
        serializer = PatientDecisionSerializer(consent, data={"patient_choice": "MAYBE"}, partial=True)
        self.assertFalse(serializer.is_valid())

    # Test 19 - hospital decision serializer should accept APPROVED
    def test_hospital_decision_valid(self):
        consent = make_consent()
        serializer = HospitalDecisionSerializer(consent, data={"hospital_choice": "APPROVED"}, partial=True)
        self.assertTrue(serializer.is_valid())

    # Test 20 - hospital decision serializer should reject values other than APPROVED or REJECTED
    def test_hospital_decision_invalid_value(self):
        consent = make_consent()
        serializer = HospitalDecisionSerializer(consent, data={"hospital_choice": "YES"}, partial=True)
        self.assertFalse(serializer.is_valid())


# ── VIEW / API TESTS ──────────────────────────────────────────────────────────
class ConsentViewTests(TestCase):

    def setUp(self):
        # APIClient works like a fake browser that can send HTTP requests to our APIs
        self.client = APIClient()

    # Test 21 - valid POST with correct token and existing hospitals should return 201
    def test_create_consent_valid(self):
        apollo = make_hospital(name="Apollo", email="apollo@test.com", contact="9876543210")
        make_hospital(name="Fortis", email="fortis@test.com", contact="9876543211")
        response = self.client.post('/api/consent/request/', {
            "patient_id": "P001",
            "requested_to_hospital": "Fortis",
            "record_id": ""
        }, HTTP_AUTHORIZATION=f"Bearer {apollo.api_key}")
        self.assertEqual(response.status_code, 201)

    # Test 22 - POST with missing required fields should return 400 even with valid token
    def test_create_consent_missing_fields(self):
        apollo = make_hospital(name="Apollo", email="apollo2@test.com", contact="9876543212")
        response = self.client.post('/api/consent/request/', {
            "patient_id": ""
        }, HTTP_AUTHORIZATION=f"Bearer {apollo.api_key}")
        self.assertEqual(response.status_code, 400)

    # Test 23 - GET to view all consents should return 200 and a list
    def test_view_all_consents(self):
        make_consent()
        response = self.client.get('/api/consent/view/')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    # Test 24 - patient approving a pending consent should return 200
    def test_patient_decision_approve(self):
        consent = make_consent()
        url = f'/api/consent/{consent.consent_id}/patient-decision/'
        response = self.client.patch(url, {"patient_choice": "APPROVED"}, format='json')
        self.assertEqual(response.status_code, 200)

    # Test 25 - patient trying to respond again after already responding should return 400
    def test_patient_decision_already_responded(self):
        consent = make_consent()
        consent.patient_choice = 'APPROVED'
        consent.save()
        url = f'/api/consent/{consent.consent_id}/patient-decision/'
        response = self.client.patch(url, {"patient_choice": "REJECTED"}, format='json')
        self.assertEqual(response.status_code, 400)

    # Test 26 - owner hospital approving with valid token should return 200
    def test_hospital_decision_approve(self):
        fortis = make_hospital(name="Fortis", email="fortis@test.com", contact="9876543213")
        consent = make_consent(requested_to="Fortis")
        url = f'/api/consent/{consent.consent_id}/hospital-decision/'
        response = self.client.patch(
            url,
            {"hospital_choice": "APPROVED"},
            format='json',
            HTTP_AUTHORIZATION=f"Bearer {fortis.api_key}"
        )
        self.assertEqual(response.status_code, 200)

    # Test 27 - deleting a PENDING consent should return 200
    def test_delete_pending_consent(self):
        consent = make_consent()
        url = f'/api/consent/{consent.consent_id}/delete/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200)

    # Test 28 - deleting an APPROVED consent should be blocked and return 400
    def test_delete_approved_consent_blocked(self):
        consent = make_consent()
        consent.patient_choice = 'APPROVED'
        consent.hospital_choice = 'APPROVED'
        consent.save()
        url = f'/api/consent/{consent.consent_id}/delete/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 400)