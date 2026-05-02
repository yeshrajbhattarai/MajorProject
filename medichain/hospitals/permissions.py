from rest_framework.permissions import BasePermission


# ─── Custom JWT Permissions ───────────────────────────────────────────────────

# base class — extracts and validates the JWT payload on every request
class IsValidJWTUser(BasePermission):

    def has_permission(self, request, view):
        # JWT payload is decoded by JWTAuthentication and attached to request
        # we store our custom claims there — check it exists
        payload = getattr(request, 'user_payload', None)
        return payload is not None


# only hospital admins can access — blocks doctors, nurses, and unauthenticated
class IsHospitalAdmin(BasePermission):

    def has_permission(self, request, view):
        payload = getattr(request, 'user_payload', None)
        if not payload:
            return False
        return payload.get('user_type') == 'hospital_admin'


# hospital user (admin or staff) with active account
class IsHospitalUserActive(BasePermission):
    """
    For GET: allows hospital admins and doctors/nurses to view
    For POST/PATCH/DELETE: requires active account
    This permission reads the JWT claims attached to `request.user_payload`
    and verifies the target Hospital exists and is active.
    """

    def has_permission(self, request, view):
        payload = getattr(request, 'user_payload', None)
        if not payload:
            return False

        user_type = payload.get('user_type')
        hospital_id = payload.get('hospital_id')

        if not hospital_id:
            return False

        # lightweight import to avoid cycle at module import time
        from hospitals.models import Hospital

        try:
            hospital = Hospital.objects.get(id=hospital_id)
        except Hospital.DoesNotExist:
            return False

        # admins are fine
        if user_type == 'hospital_admin':
            # GET allowed for all admins; write operations require active account
            if request.method == 'GET':
                return True
            return hospital.account_status == 'active'

        # staff: only doctors and nurses may perform consent/record actions
        if user_type == 'staff':
            role = payload.get('staff_role')
            if role not in ('doctor', 'nurse'):
                return False
            # GET allowed; write operations require active account
            if request.method == 'GET':
                return True
            return hospital.account_status == 'active'

        return False


# hospital admin with active account (admin-only operations like staff management)
class IsHospitalAdminActive(BasePermission):
    """
    For GET: allows all hospital admins (active or pending)
    For POST/PATCH/DELETE: requires admin with active account
    Used for staff and patient management endpoints.
    """

    def has_permission(self, request, view):
        payload = getattr(request, 'user_payload', None)
        if not payload:
            return False

        user_type = payload.get('user_type')
        if user_type != 'hospital_admin':
            return False

        hospital_id = payload.get('hospital_id')
        if not hospital_id:
            return False

        # lightweight import to avoid cycle at module import time
        from hospitals.models import Hospital

        try:
            hospital = Hospital.objects.get(id=hospital_id)
        except Hospital.DoesNotExist:
            return False

        # GET requests (viewing) allowed for all admins
        if request.method == 'GET':
            return True

        # Write operations (POST, PATCH, DELETE) require active account
        return hospital.account_status == 'active'


# only doctors can access — blocks admins, nurses, and unauthenticated
class IsDoctor(BasePermission):

    def has_permission(self, request, view):
        payload = getattr(request, 'user_payload', None)
        if not payload:
            return False
        return payload.get('staff_role') == 'doctor'


# only nurses can access — blocks admins, doctors, and unauthenticated
class IsNurse(BasePermission):

    def has_permission(self, request, view):
        payload = getattr(request, 'user_payload', None)
        if not payload:
            return False
        return payload.get('staff_role') == 'nurse'


# doctors or nurses can access — blocks admins and unauthenticated
class IsStaff(BasePermission):

    def has_permission(self, request, view):
        payload = getattr(request, 'user_payload', None)
        if not payload:
            return False
        return payload.get('user_type') == 'staff'
    
    
# only technicians can access — blocks admins, doctors, nurses
class IsTechnician(BasePermission):
    def has_permission(self, request, view):
        payload = getattr(request, 'user_payload', None)
        if not payload:
            return False
        return payload.get('staff_role') == 'technician'
