import uuid

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from hospitals.models import Hospital

from .models import AuditLog
from .utils import log_action


def make_hospital(name, email):
	return Hospital.objects.create(
		hospital_name=name,
		email=email,
		password_hash='hash',
		contact_number=str(uuid.uuid4().int)[:10],
		account_status='active',
	)


def make_token(hospital, user_type='hospital_admin', staff_role=None):
	refresh = RefreshToken()
	refresh['user_type'] = user_type
	refresh['hospital_id'] = str(hospital.id)
	refresh['hospital_name'] = hospital.hospital_name
	refresh['account_status'] = hospital.account_status
	refresh['staff_id'] = None
	refresh['staff_role'] = staff_role
	return str(refresh.access_token)


class AuditLogTests(TestCase):

	def setUp(self):
		self.client = APIClient()
		self.hospital_a = make_hospital('Apollo', 'apollo@test.com')
		self.hospital_b = make_hospital('Fortis', 'fortis@test.com')

	def test_log_action_sets_severity_and_scope(self):
		log_action(
			'CONSENT_CREATED',
			'Apollo',
			consent_id='11111111-1111-1111-1111-111111111111',
			scope_hospitals=['Apollo', 'Fortis'],
		)

		log = AuditLog.objects.latest('timestamp')
		self.assertEqual(log.action, 'CONSENT_CREATED')
		self.assertEqual(log.severity, 'INFO')
		self.assertEqual(log.scope_hospitals, ['Apollo', 'Fortis'])

	def test_view_logs_requires_hospital_admin(self):
		token = make_token(self.hospital_a, user_type='staff', staff_role='doctor')
		response = self.client.get('/api/logs/', HTTP_AUTHORIZATION=f'Bearer {token}')
		self.assertIn(response.status_code, [401, 403])

	def test_view_logs_returns_scoped_records(self):
		log_action(
			'CONSENT_CREATED',
			'doctor:abc',
			consent_id='11111111-1111-1111-1111-111111111111',
			scope_hospitals=['Apollo', 'Fortis'],
		)
		log_action(
			'CKD_PREDICTION_SUCCESS',
			'doctor:def',
			consent_id='22222222-2222-2222-2222-222222222222',
			scope_hospitals=['Fortis'],
		)

		token = make_token(self.hospital_a)
		response = self.client.get('/api/logs/', HTTP_AUTHORIZATION=f'Bearer {token}')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]['action'], 'CONSENT_CREATED')
		self.assertEqual(response.data[0]['scope_hospitals'], ['Apollo', 'Fortis'])

	def test_view_logs_filters_by_action_and_consent(self):
		consent_id = '33333333-3333-3333-3333-333333333333'
		log_action(
			'RECORD_ACCESS_DENIED',
			'Apollo',
			consent_id=consent_id,
			scope_hospitals=['Apollo', 'Fortis'],
		)
		log_action(
			'RECORD_ACCESS_SUCCESS',
			'Apollo',
			consent_id='44444444-4444-4444-4444-444444444444',
			scope_hospitals=['Apollo', 'Fortis'],
		)

		token = make_token(self.hospital_a)
		response = self.client.get(
			f'/api/logs/?action=RECORD_ACCESS_DENIED&consent_id={consent_id}',
			HTTP_AUTHORIZATION=f'Bearer {token}',
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]['action'], 'RECORD_ACCESS_DENIED')

	def test_view_logs_rejects_invalid_consent_id(self):
		token = make_token(self.hospital_a)
		response = self.client.get(
			'/api/logs/?consent_id=not-a-uuid',
			HTTP_AUTHORIZATION=f'Bearer {token}',
		)
		self.assertEqual(response.status_code, 400)
