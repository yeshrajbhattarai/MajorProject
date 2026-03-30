# API Reference

Quick reference guide for all MediChain API endpoints. Base URL: `http://localhost:8000/api/v1/`

All endpoints require `Authorization: Bearer <token>` header except auth endpoints.

---

## 🔐 Authentication Endpoints

### Register Hospital

```http
POST /register/
Content-Type: application/json

{
  "hospital_name": "City Hospital",
  "email": "admin@cityhospital.com",
  "password": "SecurePass123",
  "contact_number": "9876543210"
}

Response: 201 Created
{
  "status": "success",
  "message": "OTP sent to email",
  "request_id": "uuid"
}
```

### Verify OTP

```http
POST /verify-otp/
Content-Type: application/json

{
  "email": "admin@cityhospital.com",
  "otp": "123456"
}

Response: 200 OK
{
  "status": "success",
  "message": "Email verified successfully"
}
```

### Resend OTP

```http
POST /resend-otp/
Content-Type: application/json

{
  "email": "admin@cityhospital.com"
}

Response: 200 OK
{
  "status": "success",
  "message": "OTP sent"
}
```

### Login

```http
POST /login/
Content-Type: application/json

{
  "email": "admin@cityhospital.com",
  "password": "SecurePass123"
}

Response: 200 OK
{
  "status": "success",
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "uuid",
    "full_name": "Admin",
    "email": "...",
    "role": "admin"
  }
}
```

### Logout

```http
POST /logout/
Authorization: Bearer {token}

Response: 200 OK
{
  "status": "success",
  "message": "Logged out successfully"
}
```

---

## 🏥 Hospital Dashboard & Profile

### Get Dashboard

```http
GET /dashboard/
Authorization: Bearer {token}

Response: 200 OK
{
  "status": "success",
  "data": {
    "hospital_id": "uuid",
    "hospital_name": "City Hospital",
    "doctors_count": 5,
    "nurses_count": 8,
    "technicians_count": 3,
    "patients_count": 45,
    "pending_lab_requests": 3,
    "account_status": "active",
    "email_verified": true
  }
}
```

### Get Hospital Profile

```http
GET /profile/
Authorization: Bearer {token}

Response: 200 OK
{
  "status": "success",
  "data": {
    "id": "uuid",
    "hospital_name": "City Hospital",
    "email": "admin@cityhospital.com",
    "contact_number": "9876543210",
    "license_number": "LIC123456",
    "address": "123 Main St",
    "city": "New Delhi",
    "state": "Delhi",
    "country": "India"
  }
}
```

### Update Hospital Name

```http
PUT /profile/update-name/
Authorization: Bearer {token}
Content-Type: application/json

{
  "hospital_name": "City Hospital New"
}

Response: 200 OK
```

### Update License

```http
PUT /profile/update-license/
Authorization: Bearer {token}
Content-Type: application/json

{
  "license_number": "LIC789012",
  "license_document": "<file_upload>"
}
```

### Update Address

```http
PUT /profile/update-address/
Authorization: Bearer {token}
Content-Type: application/json

{
  "address": "456 New St",
  "city": "New Delhi",
  "state": "Delhi",
  "country": "India"
}
```

### Update Password

```http
PUT /profile/update-password/
Authorization: Bearer {token}
Content-Type: application/json

{
  "old_password": "OldPass123",
  "new_password": "NewPass123"
}
```

---

## 👨‍⚕️ Staff Management

### List Doctors

```http
GET /staff/doctors/
Authorization: Bearer {token}

Response: 200 OK
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "full_name": "Dr. Rajesh Kumar",
      "email": "dr.rajesh@...",
      "phone": "9990001111",
      "specialization": "Cardiology",
      "status": "active"
    }
  ]
}
```

### Get Doctor Detail

```http
GET /staff/doctors/{doctor_id}/
Authorization: Bearer {token}

Response: 200 OK
{
  "status": "success",
  "data": {
    "id": "uuid",
    "full_name": "Dr. Rajesh Kumar",
    "email": "...",
    "phone": "...",
    "specialization": "Cardiology",
    "bio": "...",
    "years_experience": 10,
    "profile_photo": "url"
  }
}
```

### List Nurses

```http
GET /staff/nurses/
Authorization: Bearer {token}
```

### Get Nurse Detail

```http
GET /staff/nurses/{nurse_id}/
Authorization: Bearer {token}
```

### List Technicians

```http
GET /staff/technicians/
Authorization: Bearer {token}
```

### Get Technician Detail

```http
GET /staff/technicians/{technician_id}/
Authorization: Bearer {token}
```

---

## 👥 Patient Management

### List All Patients

```http
GET /staff/patients/
Authorization: Bearer {token}

Response: 200 OK
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "full_name": "John Doe",
      "gov_id_number": "****6789",
      "phone": "9876543210",
      "email": "john@...",
      "gender": "Male",
      "blood_group": "O+",
      "created_at": "2024-03-30T10:00:00Z"
    }
  ]
}
```

### Get Patient Detail

```http
GET /staff/patients/{patient_id}/
Authorization: Bearer {token}

Response: 200 OK
{
  "status": "success",
  "data": {
    "id": "uuid",
    "full_name": "John Doe",
    "phone": "9876543210",
    "email": "john@...",
    "address": "123 Main St",
    "date_of_birth": "1979-03-30",
    "blood_group": "O+",
    "gender": "Male",
    "created_at": "2024-03-30T10:00:00Z"
  }
}
```

---

## 🩺 Doctor Portal

### Get Doctor Dashboard

```http
GET /staff/doctor/dashboard/
Authorization: Bearer {doctor_token}

Response: 200 OK
{
  "status": "success",
  "data": {
    "doctor_id": "uuid",
    "full_name": "Dr. Rajesh Kumar",
    "total_patients": 15,
    "pending_lab_requests": 2,
    "completed_records": 10
  }
}
```

### Get Doctor Profile

```http
GET /staff/doctor/profile/
Authorization: Bearer {doctor_token}
```

### Update Personal Info

```http
PUT /staff/doctor/profile/update-personal/
Authorization: Bearer {doctor_token}
Content-Type: application/json

{
  "full_name": "Dr. Rajesh Kumar",
  "phone": "9990001111",
  "specialization": "Cardiology",
  "bio": "...",
  "years_experience": 10
}
```

### Update Password

```http
PUT /staff/doctor/profile/update-password/
Authorization: Bearer {doctor_token}
Content-Type: application/json

{
  "old_password": "OldPass",
  "new_password": "NewPass"
}
```

### Add Patient

```http
POST /staff/doctor/patients/add/
Authorization: Bearer {doctor_token}
Content-Type: application/json

{
  "full_name": "John Doe",
  "gov_id_type": "aadhar",
  "gov_id_number": "123456789012",
  "gender": "Male",
  "phone": "9876543210",
  "email": "john@email.com",
  "address": "123 Main St, City",
  "date_of_birth": "1979-03-30",
  "blood_group": "O+"
}

Response: 201 Created
{
  "status": "success",
  "data": {
    "id": "uuid",
    "full_name": "John Doe",
    ...
  }
}
```

### List Doctor's Patients

```http
GET /staff/doctor/patients/
Authorization: Bearer {doctor_token}
```

### Get Patient Detail (Doctor View)

```http
GET /staff/doctor/patients/{patient_id}/
Authorization: Bearer {doctor_token}
```

### Assign Nurse

```http
POST /staff/doctor/patients/{patient_id}/assign-nurse/
Authorization: Bearer {doctor_token}
Content-Type: application/json

{
  "nurse_id": "uuid"
}

Response: 201 Created
```

### Assign Technician

```http
POST /staff/doctor/patients/{patient_id}/assign-technician/
Authorization: Bearer {doctor_token}
Content-Type: application/json

{
  "technician_id": "uuid"
}
```

### Remove Assignment

```http
DELETE /staff/doctor/patients/{patient_id}/remove-assignment/{staff_id}/
Authorization: Bearer {doctor_token}

Response: 204 No Content
```

### Send to Lab

```http
POST /staff/doctor/patients/{patient_id}/send-to-lab/
Authorization: Bearer {doctor_token}
Content-Type: application/json

{
  "lab_id": "uuid",
  "chest_pain_type": "typical",
  "diagnosis": "Chest pain evaluation",
  "treatment_plan": "Cardiac panel test"
}

Response: 201 Created
{
  "status": "success",
  "data": {
    "lab_request_id": "uuid",
    "status": "pending"
  }
}
```

### Reassess Record

```http
POST /staff/doctor/records/{record_id}/reassess/
Authorization: Bearer {doctor_token}
Content-Type: application/json

{
  "reason": "Follow-up assessment"
}

Response: 201 Created
{
  "status": "success",
  "data": {
    "version": 2,
    "created_at": "..."
  }
}
```

---

## 🔬 Technician Portal

### Get Technician Dashboard

```http
GET /staff/technician/dashboard/
Authorization: Bearer {technician_token}

Response: 200 OK
{
  "status": "success",
  "data": {
    "technician_id": "uuid",
    "full_name": "...",
    "assigned_patients": 5,
    "pending_lab_tests": 3,
    "completed_records": 20
  }
}
```

### Get Lab Queue

```http
GET /staff/technician/lab-queue/
Authorization: Bearer {technician_token}

Response: 200 OK
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "patient_name": "John Doe",
      "lab_type": "ckd",
      "status": "pending",
      "created_at": "..."
    }
  ]
}
```

### Get Lab Request Detail

```http
GET /staff/technician/lab-requests/{lab_request_id}/
Authorization: Bearer {technician_token}

Response: 200 OK
{
  "status": "success",
  "data": {
    "id": "uuid",
    "patient_id": "uuid",
    "lab_id": "uuid",
    "chest_pain_type": "typical",
    "diagnosis": "...",
    "treatment_plan": "..."
  }
}
```

### Create Medical Record

```http
POST /staff/technician/records/create/
Authorization: Bearer {technician_token}
Content-Type: application/json

{
  "lab_request_id": "uuid",
  "age": 45,
  "gender": "Male",
  "blood_pressure_systolic": 120,
  "blood_pressure_diastolic": 80,
  "cholesterol": 200,
  "blood_glucose": 95.5,
  "heart_rate": 72,
  "ecg_result": "normal"
}

Response: 201 Created
{
  "status": "success",
  "data": {
    "record_id": "uuid",
    "version": 1,
    "created_at": "..."
  }
}
```

### List Technician's Records

```http
GET /staff/technician/records/
Authorization: Bearer {technician_token}
```

---

## 📋 Medical Records

### Get Record Detail

```http
GET /staff/records/{record_id}/
Authorization: Bearer {token}

Response: 200 OK
{
  "status": "success",
  "data": {
    "id": "uuid",
    "patient_id": "uuid",
    "age": 45,
    "gender": "Male",
    "blood_pressure_systolic": 120,
    "blood_pressure_diastolic": 80,
    "cholesterol": 200,
    "blood_glucose": 95.5,
    "heart_rate": 72,
    "ecg_result": "normal",
    "version": 1,
    "created_at": "...",
    "recorded_by": "Dr. Rajesh Kumar"
  }
}
```

### Get Record History

```http
GET /staff/records/{record_id}/history/
Authorization: Bearer {token}

Response: 200 OK
{
  "status": "success",
  "data": [
    {
      "version": 1,
      "created_at": "...",
      "changed_by": "Technician A",
      "change_reason": "Initial record"
    },
    {
      "version": 2,
      "created_at": "...",
      "changed_by": "Dr. Rajesh Kumar",
      "change_reason": "Follow-up reassessment"
    }
  ]
}
```

---

## 🏥 Lab Management

### List Labs

```http
GET /staff/labs/
Authorization: Bearer {token}

Response: 200 OK
{
  "status": "success",
  "data": [
    {
      "id": "uuid",
      "name": "Cardio Lab",
      "lab_type": "ckd",
      "is_active": true
    }
  ]
}
```

### Get Lab Detail

```http
GET /staff/labs/{lab_id}/
Authorization: Bearer {token}
```

### Assign Technician to Lab

```http
POST /staff/labs/{lab_id}/assign-technician/
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "technician_id": "uuid"
}

Response: 201 Created
```

### Remove Technician from Lab

```http
DELETE /staff/labs/{lab_id}/remove-technician/{technician_id}/
Authorization: Bearer {admin_token}

Response: 204 No Content
```

---

## 📊 Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 204 | No Content - Successful deletion |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Invalid token |
| 403 | Forbidden - No permission |
| 404 | Not Found - Resource not found |
| 500 | Server Error |

---

## 🔑 Common Response Format

### Success
```json
{
  "status": "success",
  "data": {...}
}
```

### Error
```json
{
  "status": "error",
  "message": "Error description",
  "code": "ERROR_CODE"
}
```

---

**Last Updated**: March 30, 2026
