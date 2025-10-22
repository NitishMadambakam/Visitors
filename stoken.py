from itsdangerous import URLSafeTimedSerializer
from key import *
def token(email,salt):
    serializer= URLSafeTimedSerializer(secret_key)
    return serializer.dumps(email,salt=salt)
