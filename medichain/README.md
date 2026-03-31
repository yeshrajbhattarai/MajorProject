# MediChain - Hospital Management & Medical Records System

A secure, multi-tenant medical records management platform that enables hospitals to manage patient data, staff, lab tests, and medical records with **complete data isolation** between hospitals.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Prerequisites](#prerequisites)
4. [Installation & Setup](#installation--setup)
5. [Project Structure](#project-structure)
6. [Running the Application](#running-the-application)
7. [API Endpoints](#api-endpoints)
8. [Key Features](#key-features)
9. [Database & Multi-Tenancy](#database--multi-tenancy)
10. [Testing the Application](#testing-the-application)
11. [Future Scope](#future-scope)
12. [Troubleshooting](#troubleshooting)

---

## 🏥 Project Overview

**MediChain** is a Django-based REST API backend for healthcare management with these core features:

- **Multi-Hospital Platform**: Each hospital operates independently with isolated databases
- **Role-Based Access Control**: Doctors, Nurses, Technicians, Hospital Admins
- **Secure Patient Data Management**: Encrypted personal information, SHA-256 hashed identifiers
- **Lab Testing System**: Create, track, and manage lab requests with technician assignments
- **Medical Records System**: Store patient vitals, test results with version history and audit trails
- **Encrypted Storage**: Aadhar/Voter ID encryption using Fernet, password hashing with bcrypt
- **REST API**: Complete API for all hospital operations

---

## 🏗️ System Architecture

### Multi-Tenant Database Design

```
┌─────────────────────────────────────────────────────────────┐
│           Central Database: medichain                       │
│  ┌────────────┬──────────────┬─────────────┐               │
│  │ hospitals  │ hospital_     │  patients   │               │
│  │ (accounts) │ users(staff)  │  (metadata) │               │
│  └────────────┴──────────────┴─────────────┘               │
│      Shared across all hospitals                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
    Used for: Authentication, hospital setup, patient 
    registration, staff management
                           
┌──────────────────────┬──────────────────────┬──────────────────────┐
│  Hospital A Private  │  Hospital B Private  │  Hospital C Private  │
│ medichain_h_xxxx1    │ medichain_h_xxxx2    │ medichain_h_xxxx3    │
│ ┌──────────────────┐ │ ┌──────────────────┐ │ ┌──────────────────┐ │
│ │ medical_records  │ │ │ medical_records  │ │ │ medical_records  │ │
│ │ record_versions  │ │ │ record_versions  │ │ │ record_versions  │ │
│ └──────────────────┘ │ └──────────────────┘ │ └──────────────────┘ │
└──────────────────────┴──────────────────────┴──────────────────────┘
     Isolated per hospital - Others CANNOT access
```

### Key Architecture Features
- **Database Router**: Routes `hospital_local` models to hospital-specific databases
- **Thread-Local Context**: Current hospital context managed via `set_hospital_db()`
- **Automatic DB Creation**: New hospital → auto-provision dedicated MySQL database
- **Complete Isolation**: No cross-hospital data leakage possible at database level

---

## 📦 Prerequisites

Before starting, ensure you have:

- **Python 3.9+** - Download from [python.org](https://www.python.org/downloads/)
- **MySQL 8.0+** - Download from [mysql.com](https://www.mysql.com/downloads/)
- **Git** - Download from [git-scm.com](https://git-scm.com/)
- **VS Code** (Optional) - For development

### System Requirements
- RAM: Minimum 2GB (4GB recommended)
- Disk Space: Minimum 2GB
- OS: Windows 10+, macOS 10.15+, or Ubuntu 18.04+

---

## 🚀 Installation & Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-username/medichain.git
cd medichain
```

### Step 2: Create Python Virtual Environment

```powershell
# On Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Key dependencies:**
- Django 4.2+
- djangorestframework
- djangorestframework-simplejwt
- mysql-connector-python
- cryptography (Fernet encryption)
- bcrypt

### Step 4: Configure Environment Variables

Create a `.env` file in the project root:

```env
# Django Settings
SECRET_KEY=your-secret-key-here-generate-one
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DB_ENGINE=django.db.backends.mysql
DB_NAME=medichain
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306

# Email Configuration (for OTP sending)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Security
FERNET_KEY=your-fernet-key-here

# JWT Settings (auto-managed by Django)
ACCESS_TOKEN_LIFETIME=8  # hours
REFRESH_TOKEN_LIFETIME=7  # days
```

**Generate SECRET_KEY:**
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

**Generate FERNET_KEY:**
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### Step 5: Create MySQL Database

```sql
-- Open MySQL command line or MySQL Workbench
CREATE DATABASE IF NOT EXISTS medichain;
GRANT ALL PRIVILEGES ON medichain.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
```

### Step 6: Run Migrations

```bash
# Apply all migrations to central database
python manage.py migrate

# Check migration status
python manage.py showmigrations
```

**What migrations do:**
- Create all tables in `medichain` database
- Set up hospital accounts, staff, patients
- Prepare hospital-local app for per-hospital databases

---

## 📁 Project Structure

```
medichain/
├── manage.py                          # Django management script
├── requirements.txt                   # Python dependencies
├── .env                              # Environment variables (DO NOT COMMIT)
│
├── medichain/                        # Main Django project config
│   ├── settings.py                   # Settings, DB config, installed apps
│   ├── urls.py                       # Main URL router
│   ├── asgi.py                       # ASGI config (production)
│   └── wsgi.py                       # WSGI config (production)
│
├── hospitals/                        # Main app - all business logic
│   ├── models.py                     # Database models (Hospital, HospitalUser, Patient, etc.)
│   ├── serializers.py                # DRF serializers for API
│   ├── api_views.py                  # API endpoint classes (400+ endpoints)
│   ├── api_urls.py                   # API routes (/api/v1/*)
│   ├── views.py                      # Web view handlers (admin, doctor, technician portals)
│   ├── urls.py                       # Web routes
│   │
│   ├── local_models.py               # Hospital-local models (MedicalRecord, MedicalRecordVersion)
│   ├── hospital_db.py                # Dynamic hospital DB management
│   ├── db_router.py                  # Database routing logic
│   │
│   ├── authentication.py             # JWT auth & verification
│   ├── permissions.py                # Permission classes (IsDoctor, IsAdmin, etc.)
│   ├── decorators.py                 # Custom decorators
│   ├── emails.py                     # OTP & email sending
│   ├── encryption.py                 # Fernet & hashing utilities
│   ├── services.py                   # Business logic services
│   ├── utils.py                      # Helper functions
│   ├── middleware.py                 # Request middleware
│   │
│   ├── migrations/                   # Database migrations
│   │   ├── 0001_initial.py           # Initial Hospital model
│   │   ├── 0006_hospitaluser.py      # Staff management
│   │   ├── 0008_patient.py           # Patients
│   │   ├── 0010_patientassignment.py # Nurse/technician assignments
│   │   ├── 0011_lab_labrequest.py    # Lab testing system
│   │   └── 0012_lab_request_revisions.py  # Audit trail
│   │
│   └── tests.py                      # Unit tests
│
├── hospital_local/                   # Per-hospital database app
│   ├── models.py                     # Imports from local_models
│   ├── migrations/                   # Migrations for per-hospital tables
│   │   └── 0001_initial.py           # Creates medical_records & versions tables
│   │
│   └── apps.py
│
├── templates/                        # HTML templates for web views
│   └── hospitals/
│       ├── auth/
│       │   ├── register.html         # Hospital registration
│       │   └── verify_otp.html       # OTP verification
│       ├── admin/
│       │   ├── h_dashboard.html      # Hospital admin dashboard
│       │   ├── h_profile.html        # Hospital profile
│       │   ├── doctors_list.html     # Manage doctors
│       │   ├── nurses_list.html      # Manage nurses
│       │   ├── technicians_list.html # Manage technicians
│       │   └── patients_list.html    # View all patients
│       ├── doctor/
│       │   ├── doctor_dashboard.html # Doctor portal
│       │   ├── doctor_patients_list.html
│       │   └── doctor_patient_detail.html
│       └── technician/
│           ├── technician_dashboard.html
│           └── technician_patients_list.html
│
├── static/                           # CSS & JS assets
│   └── css/
│       ├── theme.css                 # Main stylesheet
│       ├── h_dashboard.css
│       ├── h_profile.css
│       └── register.css
│
└── media/                            # Uploaded files
    └── licenses/                     # Hospital license documents
```

---

## ▶️ Running the Application

### Start Development Server

```bash
# Activate virtual environment
.\venv\Scripts\Activate.ps1  # Windows
# or
source venv/bin/activate    # macOS/Linux

# Run development server
python manage.py runserver

# Server will start at http://localhost:8000
```

### Access Points

| URL | Purpose |
|-----|---------|
| `http://localhost:8000/` | Web portal home |
| `http://localhost:8000/api/v1/` | API root |
| `http://localhost:8000/api/v1/register/` | Hospital registration |
| `http://localhost:8000/api/v1/login/` | Hospital login |
| `http://localhost:8000/admin/` | Django admin panel |

---

## 🔌 API Endpoints

All API endpoints start with `/api/v1/`

### Authentication Endpoints
```
POST   /register/              Register new hospital
POST   /verify-otp/            Verify registration OTP
POST   /resend-otp/            Resend OTP
POST   /login/                 Hospital login
POST   /logout/                Hospital logout
```

### Hospital Dashboard & Profile
```
GET    /dashboard/             Hospital overview & stats
GET    /profile/               Hospital profile details
PUT    /profile/update-name/           Update hospital name
PUT    /profile/update-license/        Update license
PUT    /profile/update-address/        Update address
PUT    /profile/update-password/       Update password
```

### Staff Management (Admin Only)
```
GET    /staff/doctors/         List all doctors
GET    /staff/doctors/<id>/    Get doctor details
GET    /staff/nurses/          List all nurses
GET    /staff/nurses/<id>/     Get nurse details
GET    /staff/technicians/     List all technicians
GET    /staff/technicians/<id>/Get technician details
```

### Patient Management
```
GET    /staff/patients/        List all patients in hospital
GET    /staff/patients/<id>/   Get patient details
```

### Doctor Portal
```
GET    /staff/doctor/dashboard/                    Doctor overview
GET    /staff/doctor/profile/                      Doctor profile
PUT    /staff/doctor/profile/update-personal/     Update personal info
PUT    /staff/doctor/profile/update-password/     Update password
POST   /staff/doctor/patients/add/                 Add new patient
GET    /staff/doctor/patients/                     List assigned patients
GET    /staff/doctor/patients/<id>/                View patient details
POST   /staff/doctor/patients/<id>/assign-nurse/  Assign nurse
POST   /staff/doctor/patients/<id>/assign-technician/  Assign technician
DELETE /staff/doctor/patients/<id>/remove-assignment/<staff_id>/
POST   /staff/doctor/patients/<id>/send-to-lab/   Send to lab for testing
POST   /staff/doctor/records/<id>/reassess/       Reassess medical record
```

### Technician Portal
```
GET    /staff/technician/dashboard/               Technician overview
GET    /staff/technician/profile/                 Technician profile
PUT    /staff/technician/profile/update-personal/ Update personal info
PUT    /staff/technician/profile/update-password/ Update password
GET    /staff/technician/patients/                Assigned patients
GET    /staff/technician/patients/<id>/           Patient details
GET    /staff/technician/lab-queue/               Pending lab tests
GET    /staff/technician/lab-requests/<id>/      Lab request details
POST   /staff/technician/records/create/          Create medical record
GET    /staff/technician/records/                 View created records
GET    /staff/records/<id>/                       Record details
GET    /staff/records/<id>/history/               Record change history
```

### Lab Management
```
GET    /staff/labs/                               List all labs
GET    /staff/labs/<id>/                          Lab details
POST   /staff/labs/<id>/assign-technician/        Assign technician
DELETE /staff/labs/<id>/remove-technician/<staff_id>/
```

### API Response Format

**Success Response:**
```json
{
  "status": "success",
  "data": {
    "id": "uuid",
    "name": "...",
    ...
  }
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Error description",
  "code": "ERROR_CODE"
}
```

---

## 🔐 Key Features Explained

### 1. Hospital Registration & Authentication

**Flow:**
```
Hospital Registration
    ↓
Verify OTP via Email
    ↓
Hospital Account Created (Status: PENDING)
    ↓
Login with Email + Password
    ↓
Receive JWT Access & Refresh Tokens
    ↓
Access API endpoints with Authorization header
```

**JWT Token Usage:**
```bash
# Every API request needs this header
Authorization: Bearer <your_jwt_token>
```

### 2. Staff Management (Doctors, Nurses, Technicians)

- Created by hospital admins
- Each has role-based access control
- Can update their own profile & password
- Assigned to patients via `PatientAssignment` model

**Roles:**
- **Doctor**: Create patients, assign staff, send to labs, reassess records
- **Nurse**: View assigned patients, support care
- **Technician**: Manage lab tests, create medical records

### 3. Multi-Tenant Data Isolation

**How it works:**
```python
# When doctor from Hospital A hits endpoint:
def get_patient_medical_record(request, patient_id):
    hospital_id = request.user.hospital.id
    set_hospital_db(hospital_id)  # ← Magic happens here
    
    # Now any query routes to Hospital A's database
    record = MedicalRecord.objects.get(id=patient_id)
    
    # ✅ Hospital B cannot access this
    return record
```

### 4. Secure Data Storage

**Encrypted Fields:**
- Government ID (Aadhar/Voter ID) - **Fernet encrypted**
- Government ID Hash - **SHA-256** (for duplicate checking without exposing ID)
- Password - **bcrypt hashed**

**Why?**
- Fernet encryption = reversible (can decrypt if needed with key)
- SHA-256 hash = one-way (cannot reverse, used for matching)
- bcrypt = password-specific hashing (slow, salted)

### 5. Lab Testing System

**Workflow:**
```
Doctor → Sends patient to lab (LabRequest created)
    ↓
Lab admin assigns technician
    ↓
Technician views in lab queue (/staff/technician/lab-queue/)
    ↓
Technician performs tests, creates medical record
    ↓
Record stored in Hospital's private database
    ↓
Doctor reviews & can reassess if needed
```

### 6. Medical Records with Audit Trail

**MedicalRecord stores:**
- Patient vitals (age, BP, cholesterol, glucose, heart rate)
- ECG results
- SHA-256 hash of data (tamper detection)
- Version number

**MedicalRecordVersion tracks:**
- Every change made
- Who made it
- When it was made
- What changed
- Reason for change

**Example audit trail:**
```
Version 1: Initial record created by Dr. Smith, 2024-03-30
Version 2: BP corrected by Dr. Johnson, Reason: "Misread initial"
Version 3: Reassessed by Dr. Smith, Reason: "Follow-up"
```

---

## 💾 Database & Multi-Tenancy

### Understanding the Database Structure

**Central Database (`medichain`):**
```sql
-- Contains all hospitals
SELECT * FROM hospitals;

-- All staff across hospitals
SELECT * FROM hospital_users WHERE hospital_id='...';

-- Patient metadata
SELECT * FROM patients WHERE registered_by='...';
```

**Hospital A's Private Database (`medichain_h_xxxx1`):**
```sql
-- ONLY Hospital A's medical records
-- Hospital B cannot even connect to this database
SELECT * FROM medical_records;
```

### Creating a New Hospital's Database

When a new hospital registers:
1. `HospitalRegisterAPI` creates entry in `medichain.hospitals`
2. `create_hospital_database()` auto-provisions: `medichain_h_xxxx`
3. `hospital_local` migrations create tables in new database
4. Hospital's database is now isolated and secured

### Manual Database Setup (if auto-creation fails)

```sql
-- Create hospital-specific database
CREATE DATABASE medichain_h_a1b2c3d4;

-- Grant access to user
GRANT ALL PRIVILEGES ON medichain_h_a1b2c3d4.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
```

Then run:
```bash
python manage.py migrate hospital_local --database=hospital_a1b2c3d4
```

---

## ✅ Testing the Application

### Test Scenario 1: Hospital Registration & Login

```bash
# 1. Register Hospital
curl -X POST http://localhost:8000/api/v1/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "hospital_name": "City Hospital",
    "email": "admin@cityhospital.com",
    "password": "SecurePass123",
    "contact_number": "9876543210"
  }'

# Response:
# {
#   "status": "success",
#   "message": "OTP sent to email",
#   "request_id": "uuid"
# }

# 2. Verify OTP (Check email for OTP)
curl -X POST http://localhost:8000/api/v1/verify-otp/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@cityhospital.com",
    "otp": "123456"
  }'

# 3. Login
curl -X POST http://localhost:8000/api/v1/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@cityhospital.com",
    "password": "SecurePass123"
  }'

# Response:
# {
#   "status": "success",
#   "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "hospital": {...}
# }
```

### Test Scenario 2: Add Doctor & Create Patient

```bash
# Using access token from login
TOKEN="your_access_token_here"

# 1. Get hospital dashboard (verify authentication)
curl -X GET http://localhost:8000/api/v1/dashboard/ \
  -H "Authorization: Bearer $TOKEN"

# 2. Add Doctor (done by admin)
curl -X POST http://localhost:8000/api/v1/staff/doctors/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Dr. Rajesh Kumar",
    "email": "dr.rajesh@cityhospital.com",
    "phone": "9990001111",
    "employee_id": "DOC001",
    "specialization": "Cardiology",
    "password": "DoctorPass123"
  }'

# 3. Doctor login
curl -X POST http://localhost:8000/api/v1/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dr.rajesh@cityhospital.com",
    "password": "DoctorPass123"
  }'

# 4. Doctor adds patient
curl -X POST http://localhost:8000/api/v1/staff/doctor/patients/add/ \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Doe",
    "gov_id_type": "aadhar",
    "gov_id_number": "123456789012",
    "gender": "Male",
    "phone": "9876543210",
    "email": "john@email.com",
    "address": "123 Main St, City"
  }'
```

### Test Scenario 3: Lab Testing Workflow

```bash
TOKEN="doctor_token"

# 1. Send patient to lab
curl -X POST http://localhost:8000/api/v1/staff/doctor/patients/{patient_id}/send-to-lab/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lab_id": "lab_uuid",
    "chest_pain_type": "typical",
    "diagnosis": "Chest pain evaluation needed",
    "treatment_plan": "Run full cardiac panel"
  }'

# Response includes lab_request_id

# 2. Technician views lab queue
curl -X GET http://localhost:8000/api/v1/staff/technician/lab-queue/ \
  -H "Authorization: Bearer $TECHNICIAN_TOKEN"

# 3. Technician creates medical record
curl -X POST http://localhost:8000/api/v1/staff/technician/records/create/ \
  -H "Authorization: Bearer $TECHNICIAN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "lab_request_id": "lab_request_uuid",
    "age": 45,
    "gender": "Male",
    "blood_pressure_systolic": 120,
    "blood_pressure_diastolic": 80,
    "cholesterol": 200,
    "blood_glucose": 95.5,
    "heart_rate": 72,
    "ecg_result": "normal"
  }'

# 4. Doctor reviews record
curl -X GET http://localhost:8000/api/v1/staff/records/{record_id}/ \
  -H "Authorization: Bearer $DOCTOR_TOKEN"

# 5. Doctor reassesses (creates new version)
curl -X POST http://localhost:8000/api/v1/staff/doctor/records/{record_id}/reassess/ \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Follow-up assessment"
  }'
```

### Using Postman/Insomnia for Testing

1. **Import Collection**: Create API requests in Postman
2. **Set Base URL**: `http://localhost:8000/api/v1/`
3. **Store Token**: After login, save token in environment variable
4. **Use in Headers**: `Authorization: Bearer {{access_token}}`
5. **Test Each Endpoint**: Follow the API endpoints list

---

## 🚀 Future Scope

These features are **designed but NOT YET IMPLEMENTED**. Your co-developer will add these:

### Phase 2: Cross-Hospital Data Sharing

**Feature**: Hospital B requests patient data from Hospital A

**Implementation Plan**:
```
New Models Needed:
├── DataRequestFrom
│   ├── requesting_hospital
│   ├── owner_hospital
│   ├── patient_id
│   ├── status (pending / approved / rejected / expired)
│   ├── patient_consent (boolean)
│   └── approval_workflow
│
├── DataAccessToken
│   ├── request_id
│   ├── temporary_token
│   ├── expires_at (24 hours)
│   └── scope (which patient)
│
└── CrossHospitalAuditLog
    ├── accessing_hospital
    ├── owning_hospital
    ├── data_accessed
    ├── timestamp
    └── purpose

New APIs Needed:
├── POST /data-request/                    # Hospital B submits request
├── GET /data-requests/                    # Hospital A admin sees requests
├── POST /data-requests/<id>/approve/      # Hospital A approves
├── POST /data-requests/<id>/reject/       # Hospital A rejects
├── GET /cross-hospital/patients/<id>/records/  # Access with temp token
└── GET /cross-hospital/audit-log/        # View access history
```

**Approval Workflow**:
```
Hospital B Request
    ↓
Hospital A Admin Reviews
    ↓
Patient Gives Consent
    ↓
Both Approve → Temp Token Generated (24hr)
    ↓
Hospital B Can Access Patient Data Once
    ↓
Access Logged & Audited
```

**Compatibility with existing code**:
- ✅ Database router already supports selective access
- ✅ Permission system can handle cross-hospital permissions
- ✅ No breaking changes needed
- ✅ Builds on top of current architecture

---

## 🔧 Troubleshooting

### Issue: MySQL Connection Error

```
Error: mysql.connector.errors.ProgrammingError: 1049 (42000): Unknown database
```

**Solution:**
```bash
# Create database manually
mysql -u root -p
CREATE DATABASE medichain;
GRANT ALL PRIVILEGES ON medichain.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# Try migrations again
python manage.py migrate
```

### Issue: OTP Not Sending

```
SMTPServerDisconnected: Connection unexpectedly closed
```

**Check `.env`:**
- ✅ `EMAIL_HOST_USER` is correct Gmail address
- ✅ `EMAIL_HOST_PASSWORD` is Google App Password (not Gmail password)
- ✅ Enable 2FA on Gmail
- ✅ Create App Password at myaccount.google.com/apppasswords

### Issue: JWT Token Invalid

```
401 Unauthorized: Invalid token
```

**Check:**
```python
# Make sure token is in header
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...

# Token should be copied exactly after login
# Check token hasn't expired (8 hour lifetime)
# Use refresh token to get new token if expired:
POST /api/v1/token/refresh/
{
  "refresh": "your_refresh_token"
}
```

### Issue: Hospital Database Not Created

```
Error: Operational Error 1049 Unknown Database
```

**Solution:**
```bash
# Manually register the database
python manage.py shell

from hospitals.hospital_db import create_hospital_database
hospital_id = 'your-hospital-uuid-here'
create_hospital_database(hospital_id)
exit()
```

### Issue: Migrations Not Running

```bash
# Show migration status
python manage.py showmigrations

# Run specific migration
python manage.py migrate hospitals 0012_labrequestrevision

# Rollback if needed
python manage.py migrate hospitals 0010_alter_hospitaluser_role
```

### Issue: Static Files Not Loading

```bash
# Collect static files
python manage.py collectstatic --noinput

# Check static folder exists
ls static/  # or dir static\ on Windows
```

---

## 📚 Additional Resources

### Django & DRF Documentation
- [Django Docs](https://docs.djangoproject.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Django JWT Authentication](https://django-rest-framework-simplejwt.readthedocs.io/)

### Encryption
- [cryptography.io - Fernet](https://cryptography.io/en/latest/fernet/)
- [bcrypt](https://pypi.org/project/bcrypt/)

### MySQL
- [MySQL Docs](https://dev.mysql.com/doc/)
- [MySQL Workbench](https://www.mysql.com/products/workbench/)

---

## 📝 Development Notes for Your Co-Developer

### Key Files to Understand First

1. **`hospitals/models.py`** - Database schema (start here)
2. **`hospitals/api_views.py`** - API logic (400+ endpoints)
3. **`hospitals/db_router.py`** - Multi-tenancy magic
4. **`hospitals/authentication.py`** - JWT handling
5. **`hospitals/local_models.py`** - Hospital-local models

### Code Conventions

- **Models**: Always include `class Meta: db_table = 'table_name'`
- **Serializers**: Validate input, handle nested relations
- **Views**: Use appropriate permission classes
- **API Responses**: Standardized with `status`, `data`, `message`

### Testing Checklist

- [ ] Register new hospital
- [ ] Login with hospital account
- [ ] Add staff (doctor, nurse, technician)
- [ ] Create patient
- [ ] Assign staff to patient
- [ ] Send patient to lab
- [ ] Create medical record as technician
- [ ] View record as doctor
- [ ] Check database isolation (Hospital B cannot see Hospital A's data)

---

## 🎯 Quick Start Summary

```bash
# 1. Clone & setup
git clone <repo>
cd medichain
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install & configure
pip install -r requirements.txt
# Create .env file with credentials

# 3. Setup database
# Create MySQL database manually
python manage.py migrate

# 4. Run server
python manage.py runserver

# 5. Test
# Register hospital at http://localhost:8000/api/v1/register/
# Login & get token
# Use token for API calls
```

---

## 📞 Contact & Support

For questions or issues:
1. Check Troubleshooting section above
2. Review code comments in relevant files
3. Check Django/DRF documentation
4. Test endpoint in Postman with sample data

---

## 📄 License

[Add your license here]

---

**Last Updated**: March 30, 2026
**Version**: 1.0.0
**Status**: Production Ready (MVP)
