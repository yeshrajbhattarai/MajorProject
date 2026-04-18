from rest_framework.permissions import BasePermission


class IsPatient(BasePermission):
    """Allow only authenticated JWT users with patient role claim."""

    def has_permission(self, request, view):
        payload = getattr(request, 'user_payload', None)
        if not payload:
            return False
        return payload.get('user_type') == 'patient'
