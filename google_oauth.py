import os
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests

# Load .env (same folder as app.py)
load_dotenv()

# Read Google Client ID from environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

if not GOOGLE_CLIENT_ID:
    raise RuntimeError("GOOGLE_CLIENT_ID not found in .env file")

def verify_google_token(token):
    """
    Verify Google ID token sent from frontend (Google Identity Services).
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )

        # Validate issuer
        if idinfo.get("iss") not in (
            "accounts.google.com",
            "https://accounts.google.com"
        ):
            raise ValueError("Invalid token issuer")

        return {
            "google_id": idinfo.get("sub"),
            "email": idinfo.get("email"),
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture"),
            "role": "officer"
        }

    except Exception as e:
        print("❌ Google token verification failed:", e)
        return None
