from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.contrib.auth.models import AnonymousUser

class MediChainJWTAuthentication(JWTAuthentication):

    def get_user(self, validated_token):
        # tokens are not tied to Django User — return anonymous user
        # real identity is in user_payload (custom claims)
        return AnonymousUser()

    def authenticate(self, request):
        result = super().authenticate(request)

        if result is None:
            request.user_payload = None
            return None

        user, token = result

        request.user_payload = {
            'user_type':      token.get('user_type'),
            'hospital_id':    token.get('hospital_id'),
            'hospital_name':  token.get('hospital_name'),
            'account_status': token.get('account_status'),
            'staff_id':       token.get('staff_id'),
            'staff_role':     token.get('staff_role'),
            'patient_id':     token.get('patient_id'),
            'patient_name':   token.get('patient_name'),
        }

        return user, token