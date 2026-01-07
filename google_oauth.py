

import os
from google.oauth2 import id_token
from google.auth.transport import requests

# ✅ USE ONLY ONE CLIENT ID (Web Application)
GOOGLE_CLIENT_ID = "161607308272-lt5t46on0fr93kmdsa0kdpma3jr5457m.apps.googleusercontent.com"



def verify_google_token(token):
    """
    Verify Google ID token sent from frontend.
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )

        if idinfo["iss"] not in [
            "accounts.google.com",
            "https://accounts.google.com"
        ]:
            raise ValueError("Wrong issuer")

        return {
            "google_id": idinfo["sub"],
            "email": idinfo["email"],
            "name": idinfo["name"],
            "picture": idinfo.get("picture"),
            "role": "officer"
        }

    except Exception as e:
        print("Google token verification failed:", e)
        return None
