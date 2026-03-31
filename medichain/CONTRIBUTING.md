# Contributing to MediChain

Thank you for contributing to MediChain! This document provides guidelines for contributing code, reporting issues, and implementing new features.

---

## 📋 Before You Start

1. **Read the README.md** - Understand the project architecture
2. **Review the models** - Understand database schema in `hospitals/models.py`
3. **Check existing code** - Review similar implementations before coding
4. **Test locally** - Always test changes before committing

---

## 🔄 Development Workflow

### 1. Create a Feature Branch

```bash
# Always create a new branch for features/fixes
git checkout -b feature/cross-hospital-data-sharing
# or
git checkout -b fix/jwt-token-validation
```

### 2. Make Changes

- Follow code conventions (see below)
- Keep commits atomic and descriptive
- Write meaningful commit messages

### 3. Test Your Changes

```bash
# Test locally
python manage.py runserver

# Run tests if applicable
python manage.py test

# Test with Postman/Insomnia
```

### 4. Commit & Push

```bash
git add .
git commit -m "feat: implement cross-hospital data requests"
git push origin feature/cross-hospital-data-sharing
```

### 5. Create Pull Request

- Add clear description of changes
- Link related issues
- Request review

---

## 📐 Code Conventions

### Models

```python
# ✅ GOOD
class DataRequestFrom(models.Model):
    """
    Hospital B requesting patient data from Hospital A.
    
    Example:
        request = DataRequestFrom.objects.create(
            requesting_hospital=hospital_b,
            owner_hospital=hospital_a,
            patient_id=patient_uuid,
            status='pending'
        )
    """
    
    # Always include docstring
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requesting_hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='data_requests_sent')
    owner_hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='data_requests_received')
    patient_id = models.UUIDField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Always include Meta
    class Meta:
        db_table = 'data_requests_from'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.requesting_hospital.hospital_name} → {self.owner_hospital.hospital_name}"


# ❌ AVOID
class DataRequest(models.Model):
    # No docstring
    id = models.CharField(max_length=36, primary_key=True)  # Should be UUIDField
    hospital1 = models.ForeignKey('Hospital')  # Should use on_delete
    # No class Meta
```

### API Serializers

```python
# ✅ GOOD
class DataRequestFromSerializer(serializers.ModelSerializer):
    """Serialize DataRequestFrom for API responses."""
    
    requesting_hospital_name = serializers.CharField(
        source='requesting_hospital.hospital_name', read_only=True
    )
    owner_hospital_name = serializers.CharField(
        source='owner_hospital.hospital_name', read_only=True
    )
    
    class Meta:
        model = DataRequestFrom
        fields = ['id', 'requesting_hospital', 'requesting_hospital_name', 
                  'owner_hospital', 'owner_hospital_name', 'patient_id', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']
        
    def validate(self, data):
        """Validate that requesting_hospital != owner_hospital."""
        if data['requesting_hospital'] == data['owner_hospital']:
            raise serializers.ValidationError("Cannot request from own hospital")
        return data
```

### API Views

```python
# ✅ GOOD
class DataRequestAPIView(APIView):
    """
    API endpoint for managing cross-hospital data requests.
    
    POST: Create new data request
    GET: List data requests
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = DataRequestFromSerializer
    
    def post(self, request):
        """
        Create cross-hospital data request.
        
        Expected payload:
            {
                "owner_hospital_id": "hospital-uuid",
                "patient_id": "patient-uuid",
                "reason": "Post-op follow-up"
            }
        
        Returns:
            201 Created with request details
            400 Bad Request if validation fails
        """
        hospital_id = request.user.hospital.id
        
        # Validate input
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'status': 'error', 'message': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create request
        data_request = DataRequestFrom.objects.create(
            requesting_hospital_id=hospital_id,
            **serializer.validated_data
        )
        
        # Send notification to owner hospital admin
        notify_hospital_admin(data_request)
        
        return Response(
            {'status': 'success', 'data': DataRequestFromSerializer(data_request).data},
            status=status.HTTP_201_CREATED
        )
```

### Database Router Considerations

When adding new models:

```python
# ✅ Central database? (Shared across hospitals)
class DataRequestFrom(models.Model):
    class Meta:
        db_table = 'data_requests_from'  # Goes in 'medichain' database
        app_label = 'hospitals'  # Routes to default

# ✅ Hospital-local? (Separate per hospital)  
class HospitalSpecificData(models.Model):
    class Meta:
        db_table = 'hospital_specific_data'  # Goes in 'medichain_h_xxxx'
        app_label = 'hospital_local'  # Routes to hospital-specific db via router
```

---

## 🎯 Implementing Cross-Hospital Features

### Feature: Cross-Hospital Data Requests

**Implementation Checklist:**

- [ ] **Models**
  - [ ] `DataRequestFrom` - Request model
  - [ ] `CrossHospitalAuditLog` - Audit trail model
  - [ ] `DataAccessToken` - Temporary access token model
  - [ ] Create migration

- [ ] **Serializers**
  - [ ] `DataRequestFromSerializer`
  - [ ] `DataAccessTokenSerializer`
  - [ ] Validation for cross-hospital rules

- [ ] **API Views**
  - [ ] `CreateDataRequestAPI` - Hospital B submits request
  - [ ] `ListDataRequestsAPI` - Hospital A admin views pending
  - [ ] `ApproveDataRequestAPI` - Hospital A approves
  - [ ] `RejectDataRequestAPI` - Hospital A rejects
  - [ ] `CrossHospitalRecordAccessAPI` - Access with temp token

- [ ] **Permissions**
  - [ ] `CanRequestCrossHospitalData`
  - [ ] `IsHospitalAdmin` (to approve requests)
  - [ ] `HasValidAccessToken`

- [ ] **Services**
  - [ ] Token generation & expiration
  - [ ] Notification system
  - [ ] Audit logging

- [ ] **URLs**
  - [ ] Add routes to `api_urls.py`

- [ ] **Tests**
  - [ ] Request creation
  - [ ] Approval workflow
  - [ ] Token validation
  - [ ] Data access restrictions
  - [ ] Audit logging

### Step-by-Step Implementation Example

**Step 1: Create Model**

```python
# In hospitals/models.py

class DataRequestFrom(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_EXPIRED = 'expired'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_EXPIRED, 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requesting_hospital = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name='data_requests_sent'
    )
    owner_hospital = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name='data_requests_received'
    )
    patient_id = models.UUIDField(db_index=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    patient_consent = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        HospitalUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    rejection_reason = models.TextField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'data_requests_from'
        ordering = ['-created_at']
        
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"{self.requesting_hospital.hospital_name} requests {self.patient_id}"
```

**Step 2: Create Migration**

```bash
python manage.py makemigrations
# Check the migration file is created
python manage.py migrate
```

**Step 3: Create Serializer**

```python
# In hospitals/serializers.py

class DataRequestFromSerializer(serializers.ModelSerializer):
    requesting_hospital_name = serializers.CharField(
        source='requesting_hospital.hospital_name', read_only=True
    )
    owner_hospital_name = serializers.CharField(
        source='owner_hospital.hospital_name', read_only=True
    )
    
    class Meta:
        model = DataRequestFrom
        fields = [
            'id', 'requesting_hospital', 'requesting_hospital_name',
            'owner_hospital', 'owner_hospital_name', 'patient_id',
            'reason', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
```

**Step 4: Create API View**

```python
# In hospitals/api_views.py

class CreateDataRequestAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        hospital_id = request.user.hospital.id
        
        owner_hospital_id = request.data.get('owner_hospital_id')
        patient_id = request.data.get('patient_id')
        reason = request.data.get('reason')
        
        # Validation
        if hospital_id == owner_hospital_id:
            return Response(
                {'status': 'error', 'message': 'Cannot request from own hospital'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create request
        expires_at = timezone.now() + timedelta(days=30)
        data_request = DataRequestFrom.objects.create(
            requesting_hospital_id=hospital_id,
            owner_hospital_id=owner_hospital_id,
            patient_id=patient_id,
            reason=reason,
            expires_at=expires_at
        )
        
        return Response(
            {'status': 'success', 'data': DataRequestFromSerializer(data_request).data},
            status=status.HTTP_201_CREATED
        )
```

**Step 5: Add URL Routes**

```python
# In hospitals/api_urls.py

path('data-requests/', CreateDataRequestAPI.as_view(), name='api_create_data_request'),
```

**Step 6: Test**

```bash
python manage.py runserver
# Test endpoint with Postman
POST http://localhost:8000/api/v1/data-requests/
Authorization: Bearer <token>
Content-Type: application/json

{
  "owner_hospital_id": "hospital-uuid",
  "patient_id": "patient-uuid",
  "reason": "Post-op follow-up"
}
```

---

## 🧪 Testing Guidelines

### Unit Tests

```python
# In hospitals/tests.py

from django.test import TestCase
from hospitals.models import Patient, Hospital

class PatientTests(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            hospital_name='Test Hospital',
            email='test@hospital.com',
            contact_number='9876543210'
        )
    
    def test_patient_creation(self):
        patient = Patient.objects.create(
            full_name='John Doe',
            gov_id_type='aadhar',
            gov_id_number='123456789012',
            registered_by=self.hospital
        )
        self.assertEqual(patient.full_name, 'John Doe')
        
# Run tests
python manage.py test hospitals
```

### Integration Tests

Test complete workflows:
- Hospital registration → Login → Create patient → Assign staff → Lab request → Medical record

### Manual Testing

Always test with Postman before committing:
1. Register hospital
2. Login
3. Create staff
4. Add patient
5. Complete workflow
6. Verify database isolation

---

## 📝 Commit Message Convention

```
feat: add cross-hospital data request system
fix: resolve JWT token expiration issue
docs: update README with setup instructions
refactor: simplify database router logic
test: add unit tests for patient model
chore: update dependencies
```

**Format**: `<type>: <subject>`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Dependencies, build

---

## 🐛 Reporting Issues

Include:
- Clear description
- Steps to reproduce
- Expected vs actual behavior
- Environment details (Python version, OS, etc.)
- Error logs/screenshots

---

## ✅ Pre-Commit Checklist

Before pushing code:

- [ ] Code follows conventions
- [ ] All tests pass
- [ ] No hardcoded secrets (credentials)
- [ ] `.env` file not committed
- [ ] Meaningful commit message
- [ ] Related files documented
- [ ] Database migrations created
- [ ] Tested locally

---

## 👥 Code Review Process

1. Create Pull Request
2. Peer review
3. Address feedback
4. Run final tests
5. Merge to main branch

---

## 📞 Questions?

Refer to:
1. README.md - General setup & usage
2. Code comments - Implementation details
3. Django documentation
4. DRF documentation

---

Happy coding! 🚀
