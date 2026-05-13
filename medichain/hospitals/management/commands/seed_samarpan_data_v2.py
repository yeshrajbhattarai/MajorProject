from django.core.management.base import BaseCommand
from hospitals.models import Hospital, HospitalUser, Patient, Lab, LabRequest, LabAssignment
import uuid
from datetime import date
import hashlib


class Command(BaseCommand):
    help = 'Seed Samarpan Hospital data with realistic information'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting data seeding for Samarpan Hospital...'))

        # ===== CREATE HOSPITAL =====
        hospital_uuid = uuid.uuid4()
        hospital, created = Hospital.objects.get_or_create(
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
        self.stdout.write(f'✓ Hospital: {hospital.hospital_name}')

        # ===== CREATE STAFF =====
        staff_data = [
            {
                'email': 'samarpandahal20@gmail.com',
                'full_name': 'Samarpan Dahal',
                'phone': '9841234567',
                'employee_id': 'EMP-001',
                'role': 'doctor',
                'description': 'Hospital Administrator / Senior Doctor'
            },
            {
                'email': 'samarpandahal03@gmail.com',
                'full_name': 'Dr. Sanjay Dahal',
                'phone': '9847654321',
                'employee_id': 'EMP-002',
                'role': 'doctor',
                'description': 'Senior Medical Officer'
            },
            {
                'email': 'yash@hotmail.com',
                'full_name': 'Yash Sharma',
                'phone': '9842111111',
                'employee_id': 'EMP-003',
                'role': 'nurse',
                'description': 'Registered Nurse'
            },
            {
                'email': 'dahalsamarpan20@gmail.com',
                'full_name': 'Ashok Dahal',
                'phone': '9843222222',
                'employee_id': 'EMP-004',
                'role': 'technician',
                'description': 'Lab Technician'
            },
            {
                'email': 'royarnav361@gmail.com',
                'full_name': 'Arnav Roy',
                'phone': '9844333333',
                'employee_id': 'EMP-005',
                'role': 'technician',
                'description': 'Lab Technician'
            },
        ]

        staff_users = {}
        for staff in staff_data:
            user, created = HospitalUser.objects.get_or_create(
                email=staff['email'],
                defaults={
                    'id': uuid.uuid4(),
                    'hospital': hospital,
                    'full_name': staff['full_name'],
                    'phone': staff['phone'],
                    'employee_id': staff['employee_id'],
                    'role': staff['role'],
                    'date_of_birth': date(1990, 5, 15),
                    'gender': 'M',
                    'bio': staff['description'],
                    'password_hash': '12345678',
                    'status': 'active',
                }
            )
            staff_users[staff['email']] = user
            self.stdout.write(f'✓ Staff: {user.full_name} ({user.role})')

        # ===== CREATE PATIENT =====
        gov_id_number = '123456789012345'
        gov_id_hash = hashlib.sha256(gov_id_number.encode()).hexdigest()
        
        patient_uuid = uuid.uuid4()
        patient, created = Patient.objects.get_or_create(
            phone='9841234567',
            defaults={
                'id': patient_uuid,
                'hospital': hospital,
                'full_name': 'Bikram Neupane',
                'gender': 'M',
                'email': 'dahalsamarpan20@gmail.com',
                'address': 'Bhaktapur, Nepal',
                'gov_id_type': 'aadhar',
                'gov_id_number': gov_id_number,
                'gov_id_hash': gov_id_hash,
                'date_of_birth': date(1985, 8, 20),
                'blood_group': 'O+',
                'registered_by': hospital,
                'registered_by_self': False,
                'is_active': True,
            }
        )
        self.stdout.write(f'✓ Patient: {patient.full_name} (Phone: {patient.phone})')

        # ===== CREATE LABS =====
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
            lab, created = Lab.objects.get_or_create(
                name=lab_data['name'],
                hospital=hospital,
                defaults={
                    'lab_type': lab_data['lab_type'],
                    'description': lab_data['description'],
                }
            )
            labs.append(lab)
            self.stdout.write(f'✓ Lab: {lab.name}')

        # ===== CREATE LAB REQUEST =====
        if labs and staff_users.get('samarpandahal03@gmail.com'):
            doctor_user = staff_users['samarpandahal03@gmail.com']
            lab_request, created = LabRequest.objects.get_or_create(
                patient=patient,
                defaults={
                    'hospital': hospital,
                    'diagnosis': 'Routine Health Checkup - Annual Physical',
                    'treatment_plan': 'Complete Blood Count and Biochemistry Panel',
                    'status': 'PENDING',
                    'requested_by': doctor_user,
                }
            )
            self.stdout.write(f'✓ Lab Request: {lab_request.id} created')

            # Assign lab to lab request
            LabAssignment.objects.get_or_create(
                lab_request=lab_request,
                lab=labs[1],  # Biochemistry Lab
                defaults={'status': 'PENDING'}
            )
            self.stdout.write(f'✓ Lab Assignment: Biochemistry Lab assigned to request')

        # ===== SUMMARY =====
        self.stdout.write(self.style.SUCCESS('\n✓ Data seeding completed successfully!'))
        self.stdout.write(self.style.SUCCESS('\n=== HOSPITAL DETAILS ==='))
        self.stdout.write(f'Hospital Name: Samarpan Hospital')
        self.stdout.write(f'Hospital UUID: {hospital_uuid}')
        self.stdout.write(f'License: LIC-2024-SP-001')
        self.stdout.write(f'Location: Thamel, Kathmandu, Nepal')
        
        self.stdout.write(self.style.SUCCESS('\n=== LOGIN CREDENTIALS ==='))
        self.stdout.write(f'\nAdmin/Doctor:')
        self.stdout.write(f'  Email: samarpandahal20@gmail.com')
        self.stdout.write(f'  Password: 12345678')
        self.stdout.write(f'  Role: Doctor (Admin-equivalent)')
        
        self.stdout.write(f'\nDoctor:')
        self.stdout.write(f'  Email: samarpandahal03@gmail.com')
        self.stdout.write(f'  Password: 12345678')
        self.stdout.write(f'  Role: Doctor')
        
        self.stdout.write(f'\nNurse:')
        self.stdout.write(f'  Email: yash@hotmail.com')
        self.stdout.write(f'  Password: 12345678')
        
        self.stdout.write(f'\nTechnicians:')
        self.stdout.write(f'  Email: dahalsamarpan20@gmail.com (Password: 12345678)')
        self.stdout.write(f'  Email: royarnav361@gmail.com (Password: 12345678)')
        
        self.stdout.write(self.style.SUCCESS('\n=== PATIENT DETAILS ==='))
        self.stdout.write(f'Patient Name: Bikram Neupane')
        self.stdout.write(f'Patient Phone: 9841234567')
        self.stdout.write(f'Patient UUID: {patient_uuid}')
        self.stdout.write(f'Gov ID Type: Aadhar')
        self.stdout.write(f'Registered By: Samarpan Hospital')
