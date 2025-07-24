import os
from dotenv import load_dotenv
load_dotenv()
import requests
from fastapi.exceptions import HTTPException
import urllib.parse

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8081/auth/google/callback"

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = ['openid',
          'https://www.googleapis.com/auth/userinfo.email',
          'https://www.googleapis.com/auth/userinfo.profile']

def get_credentials(code: str):
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(TOKEN_URL, data=token_data)
    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get token")

    tokens = token_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")

    userinfo_resp = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if userinfo_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch user info")

    userinfo = userinfo_resp.json()

    return {
        "email": userinfo["email"],
        "name": userinfo["name"],
        "access_token": access_token,
        "refresh_token": refresh_token,
        "picture": userinfo.get("picture"),
    }

def get_login_redirect_url() -> str:
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent"
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"