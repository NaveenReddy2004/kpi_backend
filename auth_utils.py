import jwt
import requests
from jwt import algorithms
from flask import request

SUPABASE_PROJECT_ID = "eyfrfzpszikxbyiclelj"  # Your Supabase project ref ID
SUPABASE_JWKS_URL = f"https://{SUPABASE_PROJECT_ID}.supabase.co/auth/v1/keys"

_cached_keys = None 

def get_supabase_public_keys():
    global _cached_keys
    if _cached_keys:
        return _cached_keys

    try:
        response = requests.get(SUPABASE_JWKS_URL)
        response.raise_for_status()
        _cached_keys = response.json()["keys"]
        return _cached_keys
    except Exception as e:
        print("Failed to fetch Supabase JWKS:", e)
        return []

def validate_jwt_token(token):
    try:
        keys = get_supabase_public_keys()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header["kid"]
        key_data = next((key for key in keys if key["kid"] == kid), None)

        if not key_data:
            print("No matching key found for JWT kid.")
            return None

        public_key = algorithms.RSAAlgorithm.from_jwk(key_data)

        decoded_token = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=None,  
            options={"verify_exp": True}
        )

        return decoded_token  
        
    except Exception as e:
        print("JWT validation error:", str(e))
        return None

def get_user_from_request(req):
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    user = validate_jwt_token(token)
    return user  

