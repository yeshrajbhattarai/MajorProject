from django.core.management.base import BaseCommand
from django.utils import timezone
from hospitals.models import Hospital, HospitalUser, Patient, Lab, LabRequest, LabAssignment
from django.contrib.auth.models import User
import uuid
from datetime import date
from cryptography.fernet import Fernet
from django.conf import settings
import hashlib


class Command(BaseCommand):
    help = 'Seed Samarpan Hospital data with realistic information'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting data seeding for Samarpan Hospital...'))

        # Create Hospital
        hospital_uuid = uuid.uuid4()
        hospital, created = Hospital.objects.update_or_create(
            id=hospital_uuid,
            defaults={
                'hospital_name': 'Samarpan Hospital',
                'contact_number': '9841234500',
                'email': 'admin@samarpanhospital.com',
                'email_verified': True,
                'password_hash': '12345678',
                'license_number': 'LIC-2024-SP-001',
                'license_locked': False,
                'address': 'Thamel, Kathmandu, Nepal',
                'city': 'Kathmandu',
                'state': 'Bagmati',
                'country': 'Nepal',
                'account_status': 'active',
            }
        )
        self.stdout.write(f'Hospital: {hospital.hospital_name} (UUID: {hospital_uuid})')

        # Create Admin
        admin_user, _ = HospitalUser.objects.update_or_create(
            email='samarpandahal20@gmail.com',
            defaults={
                'hospital': hospital,
                'full_name': 'Samarpan Dahal',
                'phone': '+977-9841234567',
                'role': 'hospital_admin',
                'date_of_birth': date(1995, 3, 15),
                'gender': 'M',
                'bio': 'Hospital Administrator',
                'password': '12345678',
                'is_active': True,
            }
        )
        self.stdout.write(f'Admin: {admin_user.email}')

        # Create Doctor
        doctor_user, _ = HospitalUser.objects.update_or_create(
            email='samarpandahal03@gmail.com',
            defaults={
                'hospital': hospital,
                'full_name': 'Dr. Sanjay Dahal',
                'phone': '+977-9847654321',
                'role': 'doctor',
                'date_of_birth': date(1988, 7, 22),
                'gender': 'M',
                'bio': 'Senior Medical Officer',
                'password': '12345678',
                'is_active': True,
            }
        )
        self.stdout.write(f'Doctor: {doctor_user.email}')

        # Create Nurse
        nurse_user, _ = HospitalUser.objects.update_or_create(
            email='yash@hotmail.com',
            defaults={
                'hospital': hospital,
                'full_name': 'Yash Sharma',
                'phone': '+977-9842111111',
                'role': 'nurse',
                'date_of_birth': date(1992, 1, 10),
                'gender': 'M',
                'bio': 'Registered Nurse',
                'password': '12345678',
                'is_active': True,
            }
        )
        self.stdout.write(f'Nurse: {nurse_user.email}')

        # Create Technician 1
        tech1_user, _ = HospitalUser.objects.update_or_create(
            email='dahalsamarpan20@gmail.com',
            defaults={
                'hospital': hospital,
                'full_name': 'Ashok Dahal',
                'phone': '+977-9843222222',
                'role': 'technician',
                'date_of_birth': date(1994, 5, 18),
                'gender': 'M',
                'bio': 'Lab Technician',
                'password': '12345678',
                'is_active': True,
            }
        )
        self.stdout.write(f'Technician 1: {tech1_user.email}')

        # Create Technician 2
        tech2_user, _ = HospitalUser.objects.update_or_create(
            email='royarnav361@gmail.com',
            defaults={
                'hospital': hospital,
                'full_name': 'Arnav Roy',
                'phone': '+977-9844333333',
                'role': 'technician',
                'date_of_birth': date(1996, 11, 5),
                'gender': 'M',
                'bio': 'Lab Technician',
                'password': '12345678',
                'is_active': True,
            }
        )
        self.stdout.write(f'Technician 2: {tech2_user.email}')

        # Create Patient
        cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode() if isinstance(settings.ENCRYPTION_KEY, str) else settings.ENCRYPTION_KEY)
        
        gov_id_number = '123456789012345'
        gov_id_hash = hashlib.sha256(gov_id_number.encode()).hexdigest()
        encrypted_gov_id = cipher_suite.encrypt(gov_id_number.encode()).decode()
        
        patient_uuid = uuid.uuid4()
        patient, _ = Patient.objects.update_or_create(
            phone='9841234567',
            defaults={
                'hospital': hospital,
                'uuid': patient_uuid,
                'full_name': 'Bikram Neupane',
                'age': 35,
                'gender': 'M',
                'address': 'Bhaktapur, Nepal',
                'gov_id_number': encrypted_gov_id,
                'gov_id_hash': gov_id_hash,
                'is_active': True,
            }
        )
        self.stdout.write(f'Patient: {patient.full_name} (UUID: {patient_uuid})')

        # Create Labs
        labs_data = [
            {
                'name': 'Hematology Lab',
                'lab_type': 'hematology',
                'description': 'Complete Blood Count and related tests'
            },
            {
                'name': 'Biochemistry Lab',
                'lab_type': 'biochemistry',
                'description': 'Glucose, Electrolytes, Liver/Kidney Function'
            },
            {
                'name': 'Microbiology Lab',
                'lab_type': 'microbiology',
                'description': 'Culture and Sensitivity tests'
            },
        ]

        labs = []
        for lab_data in labs_data:
            lab, _ = Lab.objects.update_or_create(
                name=lab_data['name'],
                hospital=hospital,
                defaults={
                    'lab_type': lab_data['lab_type'],
                    'description': lab_data['description'],
                }
            )
            labs.append(lab)
            self.stdout.write(f'Lab: {lab.name}')

        # Create Lab Request
        if labs:
            lab_request, _ = LabRequest.objects.update_or_create(
                patient=patient,
                defaults={
                    'hospital': hospital,
                    'diagnosis': 'Routine Health Checkup',
                    'treatment_plan': 'Complete Blood Count and Biochemistry Panel',
                    'status': 'PENDING',
                    'requested_by': doctor_user,
                }
            )
            self.stdout.write(f'Lab Request: {lab_request.id}')

            # Assign lab to lab request
            LabAssignment.objects.get_or_create(
                lab_request=lab_request,
                lab=labs[1],  # Biochemistry Lab
                defaults={'status': 'PENDING'}
            )
            self.stdout.write(f'Lab Assignment: Biochemistry Lab assigned to request')

        self.stdout.write(self.style.SUCCESS('\n✓ Data seeding completed successfully!'))
        self.stdout.write(self.style.SUCCESS('\n=== LOGIN CREDENTIALS ==='))
        self.stdout.write(f'Hospital: Samarpan Hospital (UUID: {hospital_uuid})')
        self.stdout.write(f'\nAdmin Login:')
        self.stdout.write(f'  Email: samarpandahal20@gmail.com')
        self.stdout.write(f'  Password: 12345678')
        self.stdout.write(f'\nDoctor Login:')
        self.stdout.write(f'  Email: samarpandahal03@gmail.com')
        self.stdout.write(f'  Password: 12345678')
        self.stdout.write(f'\nNurse Login:')
        self.stdout.write(f'  Email: yash@hotmail.com')
        self.stdout.write(f'  Password: 12345678')
        self.stdout.write(f'\nTechnicians:')
        self.stdout.write(f'  Email: dahalsamarpan20@gmail.com (Password: 12345678)')
        self.stdout.write(f'  Email: royarnav361@gmail.com (Password: 12345678)')
        self.stdout.write(f'\nPatient:')
        self.stdout.write(f'  Name: Bikram Neupane')
        self.stdout.write(f'  Phone: 9841234567')
        self.stdout.write(f'  UUID: {patient_uuid}')
