from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


# ─── Custom JWT Authentication ────────────────────────────────────────────────

# extends simplejwt's default authentication to extract our custom claims
# and attach them to request.user_payload for use in views and permissions
class MediChainJWTAuthentication(JWTAuthentication):

    def authenticate(self, request):
        result = super().authenticate(request)

        if result is None:
            # no token provided — request.user_payload will be None
            request.user_payload = None
            return None

        user, token = result

        # extract our custom claims from the token and attach to request
        request.user_payload = {
            'user_type':      token.get('user_type'),
            'hospital_id':    token.get('hospital_id'),
            'hospital_name':  token.get('hospital_name'),
            'account_status': token.get('account_status'),
            'staff_id':       token.get('staff_id'),
            'staff_role':     token.get('staff_role'),
        }

        return user, token
