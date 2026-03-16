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
