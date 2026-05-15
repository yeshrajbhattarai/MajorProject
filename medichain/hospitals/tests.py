# hospitals/tests/test_api_views.py
#
# Run with:  py manage.py test hospitals.tests.test_api_views -v 2
#
# Coverage:
#   Auth          — register, verify-otp, resend-otp, login, logout
#   Admin profile — dashboard, profile, update-name/license/address/password
#   Admin staff   — doctors, nurses, technicians (list + detail + toggle)
#   Admin patient — list, add, detail
#   Doctor        — dashboard, profile, update-personal/password,
#                   patients list/add/detail, assign-nurse/tech, remove-assignment,
#                   send-to-lab
#   Technician    — dashboard, profile, update-personal/password,
#                   lab-queue, lab-request-detail, create-record, records-list
#   Records       — detail, history
#   Labs          — list, detail, assign/remove technician

import uuid
from unittest.mock import patch, MagicMock
from django.test import TransactionTestCase, Client
from django.contrib.auth.hashers import make_password
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from hospitals.models import Hospital, HospitalUser, Patient, Lab, NurseQueueItem, MedicalRecordMeta
if False:
    """

    def test_technician_edit_record_success(self):
        from hospitals.models import Lab, LabAssignment, LabRequest, MedicalRecordMeta

        doctor = self.make_doctor()
        patient = self.make_patient()
        lab = Lab.objects.create(
            hospital=self.hospital,
            lab_type='biochemistry',
            name='Bio Lab',
            custom_field_schema=[
                {
                    'label': 'Test Value',
                    'key': 'test_value',
                    'type': 'number',
                    'required': False,
                    'fill_by': 'technician',
                }
            ],
        )
        LabAssignment.objects.create(lab=lab, technician=self.tech)
        lab_request = LabRequest.objects.create(
            patient=patient,
            lab=lab,
            requested_by=doctor,
            status=LabRequest.STATUS_PENDING,
            chest_pain_type='typical',
            diagnosis='Diagnosis',
            treatment_plan='Treatment',
        )
        
        # Create a record first
        record = MedicalRecordMeta.objects.create(
            lab_request=lab_request,
            recorded_by=self.tech,
            version=1,
            custom_field_values={'test_value': 100},
        )
        
        # Edit it
        res = self.tech_client.patch(f'/api/v1/staff/technician/records/{record.record_id}/edit/', {
            'age': 32,
            'gender': 'Female',
            'custom_field_values': {'test_value': 120},
            'change_reason': 'Corrected value',
        }, format='json')
        
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertIn('record_id', res.data)

    def test_doctor_reassess_record_with_send_to_queue(self):
        from hospitals.models import Lab, LabAssignment, LabRequest, MedicalRecordMeta

        patient = self.make_patient()
        doctor = self.make_doctor()
        lab = Lab.objects.create(
            hospital=self.hospital,
            lab_type='biochemistry',
            name='Bio Lab',
        )
        LabAssignment.objects.create(lab=lab, technician=self.tech)
        lab_request = LabRequest.objects.create(
            patient=patient,
            lab=lab,
            requested_by=doctor,
            status=LabRequest.STATUS_PENDING,
            chest_pain_type='typical',
            diagnosis='Diagnosis',
            treatment_plan='Treatment',
        )
        
        # Create a record
        record = MedicalRecordMeta.objects.create(
            lab_request=lab_request,
            recorded_by=self.tech,
            version=1,
            custom_field_values={},
        )
        
        # Reassess with send_to_queue (default)
        doc_client = APIClient()
        doc_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {doctor_token(doctor.id, self.hospital.id)}'
        )
        res = doc_client.post(f'/api/v1/staff/doctor/records/{record.record_id}/reassess/', {
            'chest_pain_type': 'atypical',
            'diagnosis': 'New diagnosis',
            'treatment_plan': 'New treatment',
            'reason': 'Reviewed patient',
            'reassess_action': 'send_to_queue',
        }, format='json')
        
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertIn('Request moved back to technician queue', res.data['message'])

    def test_doctor_reassess_record_with_update_only(self):
        from hospitals.models import Lab, LabAssignment, LabRequest, MedicalRecordMeta

        patient = self.make_patient()
        doctor = self.make_doctor()
        lab = Lab.objects.create(
            hospital=self.hospital,
            lab_type='biochemistry',
            name='Bio Lab',
        )
        LabAssignment.objects.create(lab=lab, technician=self.tech)
        lab_request = LabRequest.objects.create(
            patient=patient,
            lab=lab,
            requested_by=doctor,
            status=LabRequest.STATUS_PENDING,
            chest_pain_type='typical',
            diagnosis='Diagnosis',
            treatment_plan='Treatment',
        )
        
        # Create a record
        record = MedicalRecordMeta.objects.create(
            lab_request=lab_request,
            recorded_by=self.tech,
            version=1,
            custom_field_values={},
        )
        
        # Reassess with update_only
        doc_client = APIClient()
        doc_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {doctor_token(doctor.id, self.hospital.id)}'
        )
        res = doc_client.post(f'/api/v1/staff/doctor/records/{record.record_id}/reassess/', {
            'chest_pain_type': 'atypical',
            'diagnosis': 'New diagnosis',
            'treatment_plan': 'New treatment',
            'reason': 'Reviewed patient',
            'reassess_action': 'update_only',
        }, format='json')
        
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertIn('Request status was not changed', res.data['message'])
    """

# ─── Token factory helpers ────────────────────────────────────────────────────

def make_jwt(payload: dict) -> str:
    """Mint a real JWT that MediChainJWTAuthentication will accept."""
    refresh = RefreshToken()
    for k, v in payload.items():
        refresh[k] = v
        refresh.access_token[k] = v
    return str(refresh.access_token)


def admin_token(hospital_id, hospital_name='Test Hospital', account_status='active'):
    return make_jwt({
        'user_type':      'hospital_admin',
        'hospital_id':    str(hospital_id),
        'hospital_name':  hospital_name,
        'account_status': account_status,
    })


def doctor_token(staff_id, hospital_id):
    return make_jwt({
        'user_type':  'staff',
        'staff_role': 'doctor',
        'staff_id':   str(staff_id),
        'hospital_id': str(hospital_id),
    })


def technician_token(staff_id, hospital_id):
    return make_jwt({
        'user_type':  'staff',
        'staff_role': 'technician',
        'staff_id':   str(staff_id),
        'hospital_id': str(hospital_id),
    })


def nurse_token(staff_id, hospital_id):
    return make_jwt({
        'user_type':  'staff',
        'staff_role': 'nurse',
        'staff_id':   str(staff_id),
        'hospital_id': str(hospital_id),
    })
# ─── Base ─────────────────────────────────────────────────────────────────────

class BaseTestCase(TransactionTestCase):
    """Creates a verified, active hospital + admin client once per class."""

    databases = '__all__'

    def setUp(self):
        self.client = APIClient()

        self.hospital = Hospital.objects.create(
            hospital_name   = 'Test Hospital',
            email           = 'admin@test.com',
            contact_number  = '9876543210',
            password_hash   = make_password('password123'),
            email_verified  = True,
            account_status  = 'active',
            name_locked     = False,
            license_locked  = False,
        )
        self.admin_client = APIClient()
        self.admin_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {admin_token(self.hospital.id, self.hospital.hospital_name)}'
        )

    def make_doctor(self, suffix='01'):
        return HospitalUser.objects.create(
            hospital      = self.hospital,
            full_name     = f'Dr Test {suffix}',
            email         = f'doctor{suffix}@test.com',
            phone         = f'987654{suffix}10',
            employee_id   = f'DOC{suffix}',
            role          = 'doctor',
            specialization= 'Cardiology',
            password_hash = make_password('pass1234'),
            status        = 'active',
        )

    def make_nurse(self, suffix='01'):
        return HospitalUser.objects.create(
            hospital      = self.hospital,
            full_name     = f'Nurse Test {suffix}',
            email         = f'nurse{suffix}@test.com',
            phone         = f'876543{suffix}10',
            employee_id   = f'NRS{suffix}',
            role          = 'nurse',
            password_hash = make_password('pass1234'),
            status        = 'active',
        )

    def make_technician(self, suffix='01'):
        return HospitalUser.objects.create(
            hospital      = self.hospital,
            full_name     = f'Tech Test {suffix}',
            email         = f'tech{suffix}@test.com',
            phone         = f'765432{suffix}10',
            employee_id   = f'TECH{suffix}',
            role          = 'technician',
            password_hash = make_password('pass1234'),
            status        = 'active',
        )

    def make_patient(self, suffix='01'):
        import hashlib
        from hospitals.encryption import encrypt
        gov_id   = f'123456789{suffix}'
        gov_hash = hashlib.sha256(f'aadhar{gov_id}'.encode()).hexdigest()
        return Patient.objects.create(
            gov_id_type   = 'aadhar',
            gov_id_number = encrypt(gov_id),
            gov_id_hash   = gov_hash,
            full_name     = f'Patient Test {suffix}',
            phone         = f'654321{suffix}10',
            registered_by = self.hospital,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════════════════

class AuthTests(BaseTestCase):

    # ── register ──────────────────────────────────────────────────────────────

    def test_register_success(self):
        with patch('hospitals.services.send_verification_otp'), \
             patch('hospitals.services.create_hospital_database'):
            res = self.client.post('/api/v1/register/', {
                'hospital_name':    'New Hospital',
                'email':            'new@hospital.com',
                'contact_number':   '9123456780',
                'password':         'newpass123',
                'confirm_password': 'newpass123',
            }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data['success'])
        self.assertIn('hospital_id', res.data)

    def test_register_duplicate_email(self):
        with patch('hospitals.services.send_verification_otp'), \
             patch('hospitals.services.create_hospital_database'):
            res = self.client.post('/api/v1/register/', {
                'hospital_name':    'Dup Hospital',
                'email':            'admin@test.com',   # already exists
                'contact_number':   '9000000001',
                'password':         'pass12345',
                'confirm_password': 'pass12345',
            }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_register_password_mismatch(self):
        with patch('hospitals.services.send_verification_otp'), \
             patch('hospitals.services.create_hospital_database'):
            res = self.client.post('/api/v1/register/', {
                'hospital_name':    'Hospital X',
                'email':            'x@x.com',
                'contact_number':   '9000000002',
                'password':         'pass12345',
                'confirm_password': 'different!',
            }, format='json')
        self.assertEqual(res.status_code, 400)

    # ── verify-otp ────────────────────────────────────────────────────────────

    def test_verify_otp_missing_fields(self):
        res = self.client.post('/api/v1/verify-otp/', {}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_verify_otp_wrong_otp(self):
        from django.utils import timezone
        self.hospital.email_verified        = False
        self.hospital.email_verify_otp      = '123456'
        self.hospital.email_verify_otp_expiry = timezone.now() + timezone.timedelta(minutes=5)
        self.hospital.save()
        res = self.client.post('/api/v1/verify-otp/', {
            'hospital_id': str(self.hospital.id),
            'otp': '999999',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_verify_otp_correct(self):
        from django.utils import timezone
        self.hospital.email_verified        = False
        self.hospital.email_verify_otp      = '654321'
        self.hospital.email_verify_otp_expiry = timezone.now() + timezone.timedelta(minutes=5)
        self.hospital.save()
        res = self.client.post('/api/v1/verify-otp/', {
            'hospital_id': str(self.hospital.id),
            'otp': '654321',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])


class AgeFieldTests(BaseTestCase):
    def test_hospitaluser_age_property(self):
        import datetime
        user = self.make_doctor('99')
        user.date_of_birth = datetime.date(1990, 6, 1)  # 1 June 1990
        user.save()
        with patch('django.utils.timezone.localdate', return_value=datetime.date(2026, 5, 15)):
            # birthday not yet in 2026 -> 35
            self.assertEqual(user.age, 35)

    def test_patient_age_in_serializer(self):
        import datetime
        from hospitals.serializers import PatientSerializer

        patient = self.make_patient('77')
        patient.date_of_birth = datetime.date(2000, 5, 15)
        patient.save()
        with patch('django.utils.timezone.localdate', return_value=datetime.date(2026, 5, 15)):
            data = PatientSerializer(patient).data
            # exact birthday -> 26
            self.assertEqual(data.get('age'), 26)

    # ── login ─────────────────────────────────────────────────────────────────

    def test_login_admin_success(self):
        res = self.client.post('/api/v1/login/', {
            'email':    'admin@test.com',
            'password': 'password123',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['role'], 'hospital_admin')
        self.assertIn('access', res.data['tokens'])
        self.assertIn('refresh', res.data['tokens'])

    def test_login_wrong_password(self):
        res = self.client.post('/api/v1/login/', {
            'email':    'admin@test.com',
            'password': 'wrongpass',
        }, format='json')
        self.assertEqual(res.status_code, 401)

    def test_login_unknown_email(self):
        res = self.client.post('/api/v1/login/', {
            'email':    'nobody@test.com',
            'password': 'pass',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_login_unverified_hospital(self):
        self.hospital.email_verified = False
        self.hospital.save()
        res = self.client.post('/api/v1/login/', {
            'email':    'admin@test.com',
            'password': 'password123',
        }, format='json')
        self.assertEqual(res.status_code, 403)
        self.hospital.email_verified = True
        self.hospital.save()

    def test_login_doctor_success(self):
        doc = self.make_doctor()
        res = self.client.post('/api/v1/login/', {
            'email':    doc.email,
            'password': 'pass1234',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['role'], 'doctor')

    # ── logout ────────────────────────────────────────────────────────────────

    def test_logout_missing_token(self):
        res = self.admin_client.post('/api/v1/logout/', {}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_logout_invalid_token(self):
        res = self.admin_client.post('/api/v1/logout/', {'refresh': 'notatoken'}, format='json')
        self.assertEqual(res.status_code, 400)


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — DASHBOARD & PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

class AdminDashboardProfileTests(BaseTestCase):

    def test_dashboard_returns_counts(self):
        self.make_doctor(); self.make_nurse()
        res = self.admin_client.get('/api/v1/dashboard/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('total_doctors', res.data)
        self.assertIn('total_nurses', res.data)
        self.assertEqual(res.data['total_doctors'], 1)
        self.assertEqual(res.data['total_nurses'], 1)

    def test_dashboard_unauthenticated(self):
        res = self.client.get('/api/v1/dashboard/')
        self.assertEqual(res.status_code, 401)

    def test_profile_returns_hospital_data(self):
        res = self.admin_client.get('/api/v1/profile/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['email'], 'admin@test.com')

    def test_update_address(self):
        res = self.admin_client.patch('/api/v1/profile/update-address/', {
            'address': '123 Main St',
            'city':    'Kolkata',
            'state':   'West Bengal',
            'country': 'India',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.hospital.refresh_from_db()
        self.assertEqual(self.hospital.city, 'Kolkata')

    def test_update_name_locks(self):
        res = self.admin_client.patch('/api/v1/profile/update-name/', {
            'hospital_name': 'Renamed Hospital',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.hospital.refresh_from_db()
        self.assertTrue(self.hospital.name_locked)

    def test_update_name_already_locked(self):
        self.hospital.name_locked = True
        self.hospital.save()
        res = self.admin_client.patch('/api/v1/profile/update-name/', {
            'hospital_name': 'Try again',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_update_license_locks(self):
        with patch('hospitals.services.check_and_activate_without_session'):
            res = self.admin_client.patch('/api/v1/profile/update-license/', {
                'license_number': 'LIC-2024-001',
            }, format='json')
        self.assertEqual(res.status_code, 200)
        self.hospital.refresh_from_db()
        self.assertTrue(self.hospital.license_locked)

    def test_update_password_wrong_current(self):
        res = self.admin_client.patch('/api/v1/profile/update-password/', {
            'current_password':    'wrongpass',
            'new_password':        'newpass123',
            'confirm_new_password':'newpass123',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_update_password_success(self):
        res = self.admin_client.patch('/api/v1/profile/update-password/', {
            'current_password':    'password123',
            'new_password':        'newpass123',
            'confirm_new_password':'newpass123',
        }, format='json')
        self.assertEqual(res.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — DOCTORS
# ═══════════════════════════════════════════════════════════════════════════════

class AdminDoctorTests(BaseTestCase):

    def test_list_doctors_empty(self):
        res = self.admin_client.get('/api/v1/staff/doctors/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 0)

    def test_add_doctor_success(self):
        with patch('hospitals.services.send_doctor_credentials'):
            res = self.admin_client.post('/api/v1/staff/doctors/', {
                'full_name':      'Dr New',
                'email':          'drnew@test.com',
                'phone':          '9111111111',
                'employee_id':    'DOCNEW',
                'specialization': 'Neurology',
            }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertTrue(HospitalUser.objects.filter(email='drnew@test.com').exists())

    def test_add_doctor_duplicate_email(self):
        self.make_doctor()
        with patch('hospitals.services.send_doctor_credentials'):
            res = self.admin_client.post('/api/v1/staff/doctors/', {
                'full_name':      'Dr Dup',
                'email':          'doctor01@test.com',
                'phone':          '9222222222',
                'employee_id':    'DUP01',
                'specialization': 'Cardiology',
            }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_get_doctor_detail(self):
        doc = self.make_doctor()
        res = self.admin_client.get(f'/api/v1/staff/doctors/{doc.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['email'], doc.email)

    def test_get_doctor_not_found(self):
        res = self.admin_client.get(f'/api/v1/staff/doctors/{uuid.uuid4()}/')
        self.assertEqual(res.status_code, 404)

    def test_toggle_doctor_status(self):
        doc = self.make_doctor()
        self.assertEqual(doc.status, 'active')
        res = self.admin_client.post(f'/api/v1/staff/doctors/{doc.id}/')
        self.assertEqual(res.status_code, 200)
        doc.refresh_from_db()
        self.assertEqual(doc.status, 'inactive')
        # toggle back
        self.admin_client.post(f'/api/v1/staff/doctors/{doc.id}/')
        doc.refresh_from_db()
        self.assertEqual(doc.status, 'active')

    def test_list_doctors_with_data(self):
        self.make_doctor('A'); self.make_doctor('B')
        res = self.admin_client.get('/api/v1/staff/doctors/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — NURSES
# ═══════════════════════════════════════════════════════════════════════════════

class AdminNurseTests(BaseTestCase):


    def test_add_nurse_success(self):
        with patch('hospitals.services.send_nurse_credentials'):
            res = self.admin_client.post('/api/v1/staff/nurses/', {
                'full_name':   'Nurse A',
                'email':       'nursea@test.com',
                'phone':       '9333333333',
                'employee_id': 'NRSA',
            }, format='json')
        self.assertEqual(res.status_code, 201)

    def test_list_nurses(self):
        self.make_nurse()
        res = self.admin_client.get('/api/v1/staff/nurses/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_toggle_nurse(self):
        nurse = self.make_nurse()
        res = self.admin_client.post(f'/api/v1/staff/nurses/{nurse.id}/')
        self.assertEqual(res.status_code, 200)
        nurse.refresh_from_db()
        self.assertEqual(nurse.status, 'inactive')

    def test_nurse_not_found(self):
        res = self.admin_client.get(f'/api/v1/staff/nurses/{uuid.uuid4()}/')
        self.assertEqual(res.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — TECHNICIANS
# ═══════════════════════════════════════════════════════════════════════════════

class AdminTechnicianTests(BaseTestCase):

    def test_add_technician_success(self):
        with patch('hospitals.services.send_technician_credentials'):
            res = self.admin_client.post('/api/v1/staff/technicians/', {
                'full_name':   'Tech A',
                'email':       'techa@test.com',
                'phone':       '9444444444',
                'employee_id': 'TECHA',
            }, format='json')
        self.assertEqual(res.status_code, 201)

    def test_list_technicians(self):
        self.make_technician()
        res = self.admin_client.get('/api/v1/staff/technicians/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_toggle_technician(self):
        tech = self.make_technician()
        res = self.admin_client.post(f'/api/v1/staff/technicians/{tech.id}/')
        self.assertEqual(res.status_code, 200)
        tech.refresh_from_db()
        self.assertEqual(tech.status, 'inactive')


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — PATIENTS
# ═══════════════════════════════════════════════════════════════════════════════

class AdminPatientTests(BaseTestCase):

    def test_add_patient_success(self):
        res = self.admin_client.post('/api/v1/staff/patients/', {
            'gov_id_type':   'aadhar',
            'gov_id_number': '123456789012',
            'full_name':     'Ravi Kumar',
            'email':         'ravi.kumar@test.com',
            'phone':         '9555555555',
            'gender':        'Male',
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['patient']['full_name'], 'Ravi Kumar')

    def test_add_patient_duplicate_gov_id(self):
        self.make_patient()
        res = self.admin_client.post('/api/v1/staff/patients/', {
            'gov_id_type':   'aadhar',
            'gov_id_number': '12345678901',  # same as make_patient suffix 01
            'full_name':     'Duplicate',
            'email':         'duplicate.patient@test.com',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_list_patients(self):
        self.make_patient('A'); self.make_patient('B')
        res = self.admin_client.get('/api/v1/staff/patients/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_patient_detail_has_masked_id(self):
        p = self.make_patient()
        res = self.admin_client.get(f'/api/v1/staff/patients/{p.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('gov_id_masked', res.data)

    def test_patient_not_found(self):
        res = self.admin_client.get(f'/api/v1/staff/patients/{uuid.uuid4()}/')
        self.assertEqual(res.status_code, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR — DASHBOARD & PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

class DoctorDashboardProfileTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.doctor = self.make_doctor()
        self.doc_client = APIClient()
        self.doc_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {doctor_token(self.doctor.id, self.hospital.id)}'
        )

    def test_doctor_dashboard(self):
        res = self.doc_client.get('/api/v1/staff/doctor/dashboard/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('total_patients', res.data)

    def test_doctor_dashboard_blocked_for_admin(self):
        res = self.admin_client.get('/api/v1/staff/doctor/dashboard/')
        self.assertEqual(res.status_code, 403)

    def test_doctor_profile(self):
        res = self.doc_client.get('/api/v1/staff/doctor/profile/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['email'], self.doctor.email)

    def test_doctor_update_personal(self):
        res = self.doc_client.patch('/api/v1/staff/doctor/profile/update-personal/', {
            'date_of_birth':    '1990-01-01',
            'gender':           'Male',
            'years_experience': '5',
            'license_number':   'LIC123',
            'home_address':     '123 St',
            'bio':              'Experienced cardiologist',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.bio, 'Experienced cardiologist')

    def test_doctor_update_password_wrong_current(self):
        res = self.doc_client.patch('/api/v1/staff/doctor/profile/update-password/', {
            'current_password':    'wrong',
            'new_password':        'newpass1',
            'confirm_new_password':'newpass1',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_doctor_update_password_success(self):
        res = self.doc_client.patch('/api/v1/staff/doctor/profile/update-password/', {
            'current_password':    'pass1234',
            'new_password':        'newpass1',
            'confirm_new_password':'newpass1',
        }, format='json')
        self.assertEqual(res.status_code, 200)


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR — PATIENTS
# ═══════════════════════════════════════════════════════════════════════════════

class DoctorPatientTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.doctor = self.make_doctor()
        self.doc_client = APIClient()
        self.doc_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {doctor_token(self.doctor.id, self.hospital.id)}'
        )

    def test_list_patients(self):
        self.make_patient()
        res = self.doc_client.get('/api/v1/staff/doctor/patients/')
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.data, list)

    def test_add_patient_as_doctor(self):
        res = self.doc_client.post('/api/v1/staff/doctor/patients/add/', {
            'gov_id_type':   'aadhar',
            'gov_id_number': '999888777666',
            'full_name':     'New Patient',
            'email':         'new.patient@test.com',
            'phone':         '9666666666',
        }, format='json')
        self.assertEqual(res.status_code, 201)

    def test_patient_detail_returns_assignments(self):
        p = self.make_patient()
        res = self.doc_client.get(f'/api/v1/staff/doctor/patients/{p.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('assigned_nurses', res.data)
        self.assertIn('gov_id_masked', res.data)

    def test_patient_detail_not_found(self):
        res = self.doc_client.get(f'/api/v1/staff/doctor/patients/{uuid.uuid4()}/')
        self.assertEqual(res.status_code, 404)

    def test_assign_nurse_success(self):
        p     = self.make_patient()
        nurse = self.make_nurse()
        res   = self.doc_client.post(
            f'/api/v1/staff/doctor/patients/{p.id}/assign-nurse/',
            {'nurse_id': str(nurse.id)},
            format='json'
        )
        self.assertEqual(res.status_code, 200)

    def test_assign_nurse_missing_id(self):
        p   = self.make_patient()
        res = self.doc_client.post(
            f'/api/v1/staff/doctor/patients/{p.id}/assign-nurse/',
            {}, format='json'
        )
        self.assertEqual(res.status_code, 400)

    def test_assign_nurse_duplicate(self):
        p     = self.make_patient()
        nurse = self.make_nurse()
        self.doc_client.post(
            f'/api/v1/staff/doctor/patients/{p.id}/assign-nurse/',
            {'nurse_id': str(nurse.id)}, format='json'
        )
        res = self.doc_client.post(
            f'/api/v1/staff/doctor/patients/{p.id}/assign-nurse/',
            {'nurse_id': str(nurse.id)}, format='json'
        )
        self.assertEqual(res.status_code, 400)

    def test_remove_assignment(self):
        from hospitals.models import PatientAssignment
        p     = self.make_patient()
        nurse = self.make_nurse()
        PatientAssignment.objects.create(
            patient=p, staff=nurse, role='nurse', assigned_by=self.doctor
        )
        res = self.doc_client.post(
            f'/api/v1/staff/doctor/patients/{p.id}/remove-assignment/{nurse.id}/'
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(PatientAssignment.objects.filter(patient=p, staff=nurse).exists())

    def test_remove_nonexistent_assignment(self):
        p   = self.make_patient()
        res = self.doc_client.post(
            f'/api/v1/staff/doctor/patients/{p.id}/remove-assignment/{uuid.uuid4()}/'
        )
        self.assertEqual(res.status_code, 400)


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR — SEND TO LAB
# ═══════════════════════════════════════════════════════════════════════════════

class DoctorSendToLabTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.doctor = self.make_doctor()
        self.doc_client = APIClient()
        self.doc_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {doctor_token(self.doctor.id, self.hospital.id)}'
        )
        self.patient = self.make_patient()
        self.lab = Lab.objects.create(
            hospital=self.hospital,
            lab_type='biochemistry',
            name='Biochemistry Lab',
            is_active=True,
        )

    def test_send_to_lab_success(self):
        res = self.doc_client.post('/api/v1/staff/doctor/patients/' + str(self.patient.id) + '/send-to-lab/', {
            'patient_id':      str(self.patient.id),
            'lab_id':          str(self.lab.id),
            'chest_pain_type': 'Typical Angina',
            'diagnosis':       'Possible CAD',
            'treatment_plan':  'Beta blockers',
            'notes':           '',
        }, format='json')
        self.assertEqual(res.status_code, 201)

    def test_send_to_lab_missing_diagnosis(self):
        res = self.doc_client.post('/api/v1/staff/doctor/patients/' + str(self.patient.id) + '/send-to-lab/', {
            'patient_id':      str(self.patient.id),
            'lab_id':          str(self.lab.id),
            'chest_pain_type': 'Typical Angina',
            'diagnosis':       '',
            'treatment_plan':  'Beta blockers',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_send_to_lab_invalid_lab_id(self):
        res = self.doc_client.post('/api/v1/staff/doctor/patients/' + str(self.patient.id) + '/send-to-lab/', {
            'patient_id':      str(self.patient.id),
            'lab_id':          str(uuid.uuid4()),
            'chest_pain_type': 'Typical Angina',
            'diagnosis':       'Diagnosis',
            'treatment_plan':  'Treatment',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_send_to_lab_duplicate_request(self):
        payload = {
            'patient_id':      str(self.patient.id),
            'lab_id':          str(self.lab.id),
            'chest_pain_type': 'Typical Angina',
            'diagnosis':       'Diagnosis',
            'treatment_plan':  'Treatment',
        }
        self.doc_client.post('/api/v1/staff/doctor/patients/' + str(self.patient.id) + '/send-to-lab/', payload, format='json')
        res = self.doc_client.post('/api/v1/staff/doctor/patients/' + str(self.patient.id) + '/send-to-lab/', payload, format='json')
        self.assertEqual(res.status_code, 400)


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR — MEDICAL RECORD DETAIL / VERSIONING
# ═══════════════════════════════════════════════════════════════════════════════

class DoctorMedicalRecordTests(BaseTestCase):
    databases = '__all__'

    def setUp(self):
        super().setUp()
        self.doctor = self.make_doctor()
        self.web_client = Client()
        session = self.web_client.session
        session['staff_id'] = str(self.doctor.id)
        session['staff_name'] = self.doctor.full_name
        session['staff_role'] = 'doctor'
        session['hospital_id'] = str(self.hospital.id)
        session['staff_hospital'] = self.hospital.hospital_name
        session.save()
        self.patient = self.make_patient()

    def _make_finalized_record(self):
        from hospitals.services import service_finalize_doctor_approval_item

        item = NurseQueueItem.objects.create(
            hospital=self.hospital,
            patient=self.patient,
            doctor=self.doctor,
            title='Chest Pain Review',
            primary_diagnosis='Possible CAD',
            key_instruction='Monitor symptoms and rest',
            doctor_note='Initial doctor note',
            blood_pressure='120/80',
            pulse_rate=80,
            temperature_c='36.8',
            spo2_percent=98,
            random_blood_sugar='110',
            nurse_tests_performed='ECG',
            nurse_observation='Stable',
            treatment_given='Aspirin',
            medications_administered='Aspirin',
            follow_up_notes='Follow up in a week',
            status=NurseQueueItem.STATUS_COMPLETED,
        )
        finalized_item, error = service_finalize_doctor_approval_item(
            item_id=item.id,
            hospital_id=self.hospital.id,
            doctor_id=self.doctor.id,
            next_appointment_date='2026-05-12',
            doctor_final_notes='Initial final notes',
        )
        self.assertIsNone(error)
        return finalized_item

    def test_doctor_medical_record_edit_creates_new_version(self):
        finalized_item = self._make_finalized_record()

        res = self.web_client.post(f'/staff/doctor/medical-records/{finalized_item.finalized_record_id}/', {
            'title': 'Chest Pain Review',
            'primary_diagnosis': 'Confirmed CAD',
            'key_instruction': 'Continue medication and rest',
            'doctor_note': 'Updated note',
            'blood_pressure': '118/78',
            'pulse_rate': '78',
            'temperature_c': '36.7',
            'spo2_percent': '99',
            'random_blood_sugar': '108',
            'nurse_tests_performed': 'ECG, Troponin',
            'nurse_observation': 'Improving',
            'treatment_given': 'Adjusted treatment',
            'medications_administered': 'Aspirin, Statin',
            'follow_up_notes': 'Return in 3 days',
            'next_appointment_date': '2026-05-15',
            'doctor_final_notes': 'Updated final notes',
            'closing_statement': 'Stable for discharge',
            'nurse_discharge_statement': 'Discharge complete',
            'change_reason': 'Doctor updated the final diagnosis and plan',
        })

        self.assertEqual(res.status_code, 302)
        finalized_item.refresh_from_db()
        meta_versions = MedicalRecordMeta.objects.filter(record_id=finalized_item.finalized_record_id).order_by('version')
        self.assertEqual(meta_versions.count(), 2)
        self.assertEqual(meta_versions.last().version, 2)
        self.assertEqual(len(finalized_item.finalized_record_history), 2)
        self.assertEqual(finalized_item.primary_diagnosis, 'Confirmed CAD')

    def test_doctor_medical_record_detail_shows_edit_button(self):
        finalized_item = self._make_finalized_record()
        res = self.web_client.get(f'/staff/doctor/medical-records/{finalized_item.finalized_record_id}/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Edit Record')

    def test_lab_record_detail_shows_integrity_badge_for_selected_version(self):
        from hospitals.models import Lab, LabRequest, LabAssignment
        from hospitals.services import service_create_medical_record, service_edit_medical_record

        technician = self.make_technician('42')
        lab = Lab.objects.create(hospital=self.hospital, lab_type='biochemistry', name='Bio Lab')
        lab_request = LabRequest.objects.create(
            patient=self.patient,
            lab=lab,
            requested_by=self.doctor,
            chest_pain_type='typical',
            diagnosis='Initial diagnosis',
            treatment_plan='Initial plan',
            notes='Initial notes',
        )
        LabAssignment.objects.create(lab=lab, technician=technician)

        record, error = service_create_medical_record(
            lab_request_id=lab_request.id,
            technician_id=technician.id,
            hospital_id=self.hospital.id,
            data={'age': '31', 'gender': 'Male'},
        )
        self.assertIsNone(error)

        updated_record, error = service_edit_medical_record(
            record_id=record.record_id,
            technician_id=technician.id,
            hospital_id=self.hospital.id,
            data={'age': '32', 'gender': 'Male'},
            change_reason='Updated age after review',
        )
        self.assertIsNone(error)

        res = self.web_client.get(f'/staff/records/{updated_record.record_id}/?v=1')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Record Integrity: Verified')
        self.assertContains(res, 'Local DB:')
        self.assertContains(res, 'MediChain:')

    def test_lab_record_verification_deterministic(self):
        from hospitals.models import Lab, LabRequest, LabAssignment
        from hospitals.services import service_create_medical_record, service_edit_medical_record, service_get_record_detail

        technician = self.make_technician('99')
        lab = Lab.objects.create(hospital=self.hospital, lab_type='biochemistry', name='Bio Lab 2')
        lab_request = LabRequest.objects.create(
            patient=self.patient,
            lab=lab,
            requested_by=self.doctor,
            chest_pain_type='typical',
            diagnosis='Initial diagnosis',
            treatment_plan='Initial plan',
            notes='Initial notes',
        )
        LabAssignment.objects.create(lab=lab, technician=technician)

        record_v1, error = service_create_medical_record(
            lab_request_id=lab_request.id,
            technician_id=technician.id,
            hospital_id=self.hospital.id,
            data={'age': '40', 'gender': 'Male'},
        )
        self.assertIsNone(error)

        record_v2, error = service_edit_medical_record(
            record_id=record_v1.record_id,
            technician_id=technician.id,
            hospital_id=self.hospital.id,
            data={'age': '41', 'gender': 'Male'},
            change_reason='update age',
        )
        self.assertIsNone(error)

        # verify v1, v2 and latest (no version specified) all compute/compare deterministically
        r1, lr1, bundle1, err1 = service_get_record_detail(record_v1.record_id, self.hospital.id, version_number=1)
        self.assertIsNone(err1)
        self.assertTrue(bundle1['hash']['verified'])

        r2, lr2, bundle2, err2 = service_get_record_detail(record_v1.record_id, self.hospital.id, version_number=2)
        self.assertIsNone(err2)
        self.assertTrue(bundle2['hash']['verified'])

        r_latest, lr_latest, bundle_latest, err_latest = service_get_record_detail(record_v1.record_id, self.hospital.id, version_number=None)
        self.assertIsNone(err_latest)
        # latest should match v2 and be verified
        self.assertTrue(bundle_latest['hash']['verified'])

    def test_medical_record_verification_deterministic(self):
        from hospitals.services import service_finalize_doctor_approval_item, service_update_finalized_medical_record, service_get_finalized_medical_record_detail

        finalized_item = self._make_finalized_record()

        # update finalized medical record (creates new version)
        _, errors = service_update_finalized_medical_record(
            record_id=finalized_item.finalized_record_id,
            hospital_id=self.hospital.id,
            doctor_id=self.doctor.id,
            data={
                'title': finalized_item.title,
                'primary_diagnosis': 'Changed Diagnosis',
                'key_instruction': finalized_item.key_instruction,
                'doctor_note': 'Updated note',
            },
            change_reason='test update',
        )
        self.assertIsNone(errors)

        # fetch both versions and ensure verified
        item1, bundle1, err1 = service_get_finalized_medical_record_detail(finalized_item.finalized_record_id, role='doctor', hospital_id=self.hospital.id, staff_id=self.doctor.id, version_number=1)
        self.assertIsNone(err1)
        self.assertTrue(bundle1['hash']['verified'])

        item2, bundle2, err2 = service_get_finalized_medical_record_detail(finalized_item.finalized_record_id, role='doctor', hospital_id=self.hospital.id, staff_id=self.doctor.id, version_number=2)
        self.assertIsNone(err2)
        self.assertTrue(bundle2['hash']['verified'])


# ═══════════════════════════════════════════════════════════════════════════════
# DOCTOR — REASSESS RECORD
# ═══════════════════════════════════════════════════════════════════════════════

class DoctorReassessRecordTests(BaseTestCase):
    databases = '__all__'

    def setUp(self):
        super().setUp()
        self.doctor = self.make_doctor()
        self.tech = self.make_technician()
        self.patient = self.make_patient()
        self.doc_client = APIClient()
        self.doc_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {doctor_token(self.doctor.id, self.hospital.id)}'
        )

    def _make_record(self):
        from hospitals.models import Lab, LabAssignment, LabRequest
        from hospitals.services import service_create_medical_record

        lab = Lab.objects.create(hospital=self.hospital, lab_type='biochemistry', name='Bio Lab')
        LabAssignment.objects.create(lab=lab, technician=self.tech)
        lab_request = LabRequest.objects.create(
            patient=self.patient,
            lab=lab,
            requested_by=self.doctor,
            status=LabRequest.STATUS_PENDING,
            chest_pain_type='typical',
            diagnosis='Diagnosis',
            treatment_plan='Treatment',
        )
        record, error = service_create_medical_record(
            lab_request_id=lab_request.id,
            technician_id=self.tech.id,
            hospital_id=self.hospital.id,
            data={'age': '31', 'gender': 'Male'},
        )
        self.assertIsNone(error)
        return record

    def test_doctor_reassess_record_with_send_to_queue(self):
        record = self._make_record()
        res = self.doc_client.post(f'/api/v1/staff/doctor/records/{record.record_id}/reassess/', {
            'chest_pain_type': 'atypical',
            'diagnosis': 'New diagnosis',
            'treatment_plan': 'New treatment',
            'reason': 'Reviewed patient',
            'reassess_action': 'send_to_queue',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertIn('technician queue', res.data['message'])

    def test_doctor_reassess_record_with_update_only(self):
        record = self._make_record()
        res = self.doc_client.post(f'/api/v1/staff/doctor/records/{record.record_id}/reassess/', {
            'chest_pain_type': 'atypical',
            'diagnosis': 'New diagnosis',
            'treatment_plan': 'New treatment',
            'reason': 'Reviewed patient',
            'reassess_action': 'update_only',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertIn('status was not changed', res.data['message'])


# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICIAN — DASHBOARD, PROFILE, LAB QUEUE
# ═══════════════════════════════════════════════════════════════════════════════

class TechnicianTests(BaseTestCase):
    databases = '__all__'

    def setUp(self):
        super().setUp()
        self.tech = self.make_technician()
        self.tech_client = APIClient()
        self.tech_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {technician_token(self.tech.id, self.hospital.id)}'
        )

    def test_technician_dashboard(self):
        res = self.tech_client.get('/api/v1/staff/technician/dashboard/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('total_records', res.data)

    def test_technician_dashboard_blocked_for_doctor(self):
        doc = self.make_doctor()
        doc_client = APIClient()
        doc_client.credentials(HTTP_AUTHORIZATION=f'Bearer {doctor_token(doc.id, self.hospital.id)}')
        res = doc_client.get('/api/v1/staff/technician/dashboard/')
        self.assertEqual(res.status_code, 403)

    def test_technician_profile(self):
        res = self.tech_client.get('/api/v1/staff/technician/profile/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['email'], self.tech.email)

    def test_technician_update_personal(self):
        res = self.tech_client.patch('/api/v1/staff/technician/profile/update-personal/', {
            'date_of_birth':    '1992-05-10',
            'gender':           'Female',
            'years_experience': '3',
            'license_number':   'TECHLIC001',
            'home_address':     '456 Ave',
            'bio':              'Lab specialist',
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.bio, 'Lab specialist')

    def test_technician_update_password_success(self):
        res = self.tech_client.patch('/api/v1/staff/technician/profile/update-password/', {
            'current_password':    'pass1234',
            'new_password':        'techpass99',
            'confirm_new_password':'techpass99',
        }, format='json')
        self.assertEqual(res.status_code, 200)

    def test_lab_queue_empty_without_assignment(self):
        res = self.tech_client.get('/api/v1/staff/technician/lab-queue/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [])

    def test_technician_patients_list(self):
        from hospitals.models import LabAssignment, LabRequest

        doctor = self.make_doctor()
        patient = self.make_patient()
        lab = Lab.objects.create(hospital=self.hospital, lab_type='biochemistry', name='Bio Lab')
        LabAssignment.objects.create(lab=lab, technician=self.tech)
        LabRequest.objects.create(
            patient=patient,
            lab=lab,
            requested_by=doctor,
            status=LabRequest.STATUS_PENDING,
            chest_pain_type='typical',
            diagnosis='Diagnosis',
            treatment_plan='Treatment',
        )

        res = self.tech_client.get('/api/v1/staff/technician/patients/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['patient']['id'], str(patient.id))
        self.assertEqual(res.data[0]['assigned_by']['id'], str(doctor.id))

    def test_technician_records_list_empty(self):
        res = self.tech_client.get('/api/v1/staff/technician/records/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 0)

    def test_technician_create_record_accepts_browser_payload(self):
        from hospitals.models import Lab, LabAssignment, LabRequest

        doctor = self.make_doctor()
        patient = self.make_patient()
        lab = Lab.objects.create(
            hospital=self.hospital,
            lab_type='biochemistry',
            name='Bio Lab',
            custom_field_schema=[
                {
                    'label': 'Specimen Notes',
                    'key': 'specimen_notes',
                    'type': 'text',
                    'required': False,
                    'fill_by': 'technician',
                }
            ],
        )
        LabAssignment.objects.create(lab=lab, technician=self.tech)
        lab_request = LabRequest.objects.create(
            patient=patient,
            lab=lab,
            requested_by=doctor,
            status=LabRequest.STATUS_PENDING,
            chest_pain_type='typical',
            diagnosis='Diagnosis',
            treatment_plan='Treatment',
        )

        res = self.tech_client.post('/api/v1/staff/technician/records/create/', {
            'lab_request_id': str(lab_request.id),
            'age': 31,
            'gender': 'Male',
            'technician_change_reason': '',
            'custom_field_values': {
                'specimen_notes': 'Collected after fasting',
            },
        }, format='json')

        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data['success'])
        self.assertIn('record_id', res.data)

    def test_technician_edit_record_success(self):
        from hospitals.models import Lab, LabAssignment, LabRequest
        from hospitals.services import service_create_medical_record

        doctor = self.make_doctor()
        patient = self.make_patient()
        lab = Lab.objects.create(
            hospital=self.hospital,
            lab_type='biochemistry',
            name='Bio Lab',
        )
        LabAssignment.objects.create(lab=lab, technician=self.tech)
        lab_request = LabRequest.objects.create(
            patient=patient,
            lab=lab,
            requested_by=doctor,
            status=LabRequest.STATUS_PENDING,
            chest_pain_type='typical',
            diagnosis='Diagnosis',
            treatment_plan='Treatment',
        )

        record, error = service_create_medical_record(
            lab_request_id=lab_request.id,
            technician_id=self.tech.id,
            hospital_id=self.hospital.id,
            data={'age': '31', 'gender': 'Male'},
        )
        self.assertIsNone(error)

        res = self.tech_client.patch(f'/api/v1/staff/technician/records/{record.record_id}/edit/', {
            'age': 32,
            'gender': 'Female',
            'custom_field_values': {},
            'change_reason': 'Corrected value',
        }, format='json')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertIn('record_id', res.data)


# ═══════════════════════════════════════════════════════════════════════════════
# NURSE — PROFILE UPDATES
# ═══════════════════════════════════════════════════════════════════════════════

class NurseUpdatePersonalTests(BaseTestCase):
    databases = '__all__'

    def setUp(self):
        super().setUp()
        self.nurse = self.make_nurse()
        self.nurse_client = APIClient()
        self.nurse_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {nurse_token(self.nurse.id, self.hospital.id)}'
        )

    def test_nurse_update_personal_success(self):
        res = self.nurse_client.patch('/api/v1/staff/nurse/profile/update-personal/', {
            'date_of_birth': '1990-05-15',
            'gender': 'Female',
            'years_experience': 5,
            'license_number': 'LIC123456',
            'home_address': '123 Nurse St',
            'bio': 'Experienced nurse',
        }, format='json')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertIn('nurse', res.data)

    def test_nurse_update_password_success(self):
        res = self.nurse_client.patch('/api/v1/staff/nurse/profile/update-password/', {
            'current_password': 'pass1234',
            'new_password': 'nursepass99',
            'confirm_new_password': 'nursepass99',
        }, format='json')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])


# ═══════════════════════════════════════════════════════════════════════════════
# LABS — ADMIN CRUD
# ═══════════════════════════════════════════════════════════════════════════════

class LabTests(BaseTestCase):
    databases = '__all__'

    def test_create_lab_success(self):
        res = self.admin_client.post('/api/v1/staff/labs/', {
            'lab_type': 'biochemistry',
            'name':     'Biochemistry Lab',
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertTrue(Lab.objects.filter(hospital=self.hospital, lab_type='biochemistry').exists())

    def test_create_duplicate_lab_type(self):
        Lab.objects.create(hospital=self.hospital, lab_type='biochemistry', name='Bio Lab')
        res = self.admin_client.post('/api/v1/staff/labs/', {
            'lab_type': 'biochemistry',
            'name':     'Another Bio Lab',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_list_labs(self):
        Lab.objects.create(hospital=self.hospital, lab_type='biochemistry', name='Bio Lab')
        Lab.objects.create(hospital=self.hospital, lab_type='hematology', name='Hemo Lab')
        res = self.admin_client.get('/api/v1/staff/labs/')
        self.assertEqual(res.status_code, 200)

    def test_lab_detail(self):
        lab = Lab.objects.create(hospital=self.hospital, lab_type='biochemistry', name='Bio Lab')
        res = self.admin_client.get(f'/api/v1/staff/labs/{lab.id}/')
        self.assertEqual(res.status_code, 200)

    def test_lab_not_found(self):
        res = self.admin_client.get(f'/api/v1/staff/labs/{uuid.uuid4()}/')
        self.assertEqual(res.status_code, 404)

    def test_assign_technician_to_lab(self):
        lab  = Lab.objects.create(hospital=self.hospital, lab_type='biochemistry', name='Bio Lab')
        tech = self.make_technician()
        res  = self.admin_client.post(
            f'/api/v1/staff/labs/{lab.id}/assign-technician/',
            {'technician_id': str(tech.id)},
            format='json'
        )
        self.assertEqual(res.status_code, 200)

    def test_assign_technician_duplicate(self):
        from hospitals.models import LabAssignment
        lab  = Lab.objects.create(hospital=self.hospital, lab_type='biochemistry', name='Bio Lab')
        tech = self.make_technician()
        LabAssignment.objects.create(lab=lab, technician=tech)
        res  = self.admin_client.post(
            f'/api/v1/staff/labs/{lab.id}/assign-technician/',
            {'technician_id': str(tech.id)},
            format='json'
        )
        self.assertEqual(res.status_code, 400)

    def test_remove_technician_from_lab(self):
        from hospitals.models import LabAssignment
        lab  = Lab.objects.create(hospital=self.hospital, lab_type='biochemistry', name='Bio Lab')
        tech = self.make_technician()
        LabAssignment.objects.create(lab=lab, technician=tech)
        res  = self.admin_client.post(
            f'/api/v1/staff/labs/{lab.id}/remove-technician/{tech.id}/'
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(LabAssignment.objects.filter(lab=lab, technician=tech).exists())


# ═══════════════════════════════════════════════════════════════════════════════
# PERMISSION BOUNDARY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class PermissionBoundaryTests(BaseTestCase):
    """Verify that role-gated endpoints reject the wrong roles."""

    databases = '__all__'

    def setUp(self):
        super().setUp()
        self.doctor = self.make_doctor()
        self.tech   = self.make_technician()

        self.doc_client = APIClient()
        self.doc_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {doctor_token(self.doctor.id, self.hospital.id)}'
        )
        self.tech_client = APIClient()
        self.tech_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {technician_token(self.tech.id, self.hospital.id)}'
        )

    def test_admin_endpoint_rejects_doctor(self):
        res = self.doc_client.get('/api/v1/staff/doctors/')
        self.assertEqual(res.status_code, 403)

    def test_admin_endpoint_rejects_technician(self):
        res = self.tech_client.get('/api/v1/staff/doctors/')
        self.assertEqual(res.status_code, 403)

    def test_doctor_endpoint_rejects_technician(self):
        res = self.tech_client.get('/api/v1/staff/doctor/patients/')
        self.assertEqual(res.status_code, 403)

    def test_technician_endpoint_rejects_doctor(self):
        res = self.doc_client.get('/api/v1/staff/technician/lab-queue/')
        self.assertEqual(res.status_code, 403)

    def test_unauthenticated_admin_endpoint(self):
        res = self.client.get('/api/v1/dashboard/')
        self.assertEqual(res.status_code, 401)

    def test_unauthenticated_doctor_endpoint(self):
        res = self.client.get('/api/v1/staff/doctor/patients/')
        self.assertEqual(res.status_code, 401)