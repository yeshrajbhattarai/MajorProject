# patient/tests.py
#
# Run with:  py manage.py test patient.tests -v 2

import uuid
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from hospitals.models import Hospital, HospitalUser, Patient
from hospitals.token_utils import get_tokens_for_payload


def patient_token(patient_id, **extra):
    """Generate a patient JWT token for testing."""
    return get_tokens_for_payload({
        'user_type': 'patient',
        'patient_id': str(patient_id),
        'patient_name': 'Test Patient',
    })['access']


class BasePatientTestCase(TransactionTestCase):
    """Base class for patient tests."""
    databases = '__all__'

    def setUp(self):
        self.hospital = Hospital.objects.create(
            hospital_name='Test Hospital',
            email='hospital@test.com',
            license_number='LIC123456',
            email_verified=True,
        )
        self.patient = Patient.objects.create(
            full_name='Test Patient',
            email='patient@test.com',
            phone='9876543210',
            address='',
            gender='',
            registered_by_self=True,
        )
        
        self.client = APIClient()
        token = patient_token(self.patient.id)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')


class PatientCompleteProfileTests(BasePatientTestCase):
    """Test PatientCompleteProfileAPI."""
    databases = '__all__'

    def test_complete_profile_success(self):
        """Test completing patient profile with valid data."""
        res = self.client.post('/api/v1/patient/complete-profile/', {
            'phone': '9876543210',
            'address': '123 Patient St',
            'gender': 'Male',
        }, format='json')
        
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertIn('patient', res.data)
        self.assertEqual(res.data['patient']['phone'], '9876543210')
        self.assertEqual(res.data['patient']['address'], '123 Patient St')
        self.assertEqual(res.data['patient']['gender'], 'Male')

    def test_complete_profile_partial_data(self):
        """Test completing profile with only some fields."""
        res = self.client.post('/api/v1/patient/complete-profile/', {
            'phone': '9999999999',
        }, format='json')
        
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])

    def test_complete_profile_empty_data(self):
        """Test completing profile with empty data."""
        res = self.client.post('/api/v1/patient/complete-profile/', {
            'phone': '',
            'address': '',
            'gender': '',
        }, format='json')
        
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])

    def test_complete_profile_invalid_gender(self):
        """Test that invalid gender choice is rejected."""
        res = self.client.post('/api/v1/patient/complete-profile/', {
            'phone': '9876543210',
            'address': '123 Patient St',
            'gender': 'InvalidGender',
        }, format='json')
        
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.data['success'])
