from rest_framework_simplejwt.tokens import RefreshToken


# Shared token helper for all app modules (hospital, staff, patient)
def get_tokens_for_payload(payload: dict) -> dict:
    refresh = RefreshToken()

    for key, value in payload.items():
        refresh[key] = value
        refresh.access_token[key] = value

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
