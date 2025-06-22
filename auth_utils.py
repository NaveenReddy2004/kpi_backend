import jwt
import requests
from jwt import algorithms
from flask import request

SUPABASE_PROJECT_ID = "eyfrfzpszikxbyiclelj"  # Your Supabase project ID

def get_supabase_public_keys():
    jwks_url = f"https://{SUPABASE_PROJECT_ID}.supabase.co/auth/v1/keys"
    res = requests.get(jwks_url)
    res.raise_for_status()
    return res.json()["keys"]

def validate_jwt_token(token):
    keys = get_supabase_public_keys()
    header = jwt.get_unverified_header(token)
    kid = header["kid"]

    key_data = next(k for k in keys if k["kid"] == kid)
    public_key = algorithms.RSAAlgorithm.from_jwk(key_data)

    try:
        decoded = jwt.decode(token, public_key, algorithms=["RS256"], audience=None)
        return decoded
    except Exception as e:
        print("JWT validation error:", e)
        return None

def get_user_from_request(req):
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    return validate_jwt_token(token)
