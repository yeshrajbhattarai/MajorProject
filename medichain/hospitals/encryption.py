from cryptography.fernet import Fernet
from django.conf import settings

def get_fernet():
    key = settings.FERNET_KEYS[0].encode() if isinstance(settings.FERNET_KEYS[0], str) else settings.FERNET_KEYS[0]
    return Fernet(key)

def encrypt(value):
    if not value:
        return value
    return get_fernet().encrypt(value.encode()).decode()

def decrypt(value):
    if not value:
        return value
    return get_fernet().decrypt(value.encode()).decode()