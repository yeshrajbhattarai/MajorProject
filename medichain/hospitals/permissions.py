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
    Allow access to staff members (doctors, nurses, technicians) who are:
    1. Authenticated with a valid JWT token
    2. Have a valid user_payload in the request
    3. Have 'staff' user_type (not hospital_admin)
    4. Have 'active' status (implied by having valid token)
    """

    def has_permission(self, request, view):
        # Check if user_payload exists (set by authentication class)
        if not hasattr(request, 'user_payload'):
            return False

        user_payload = request.user_payload

        # Must be staff, not admin
        if user_payload.get('user_type') != 'staff':
            return False

        # staff_id must exist
        if not user_payload.get('staff_id'):
            return False

        # hospital_id must exist
        if not user_payload.get('hospital_id'):
            return False

        return True


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
