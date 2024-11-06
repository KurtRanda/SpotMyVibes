# services/auth_service.py
# This module handles Spotify OAuth login and authentication requests.

from flask import session, redirect, url_for
from utils import generate_code_verifier_and_challenge
from urllib.parse import urlencode
import requests, time

class AuthService:
    @staticmethod
    def login():
        """Initiate the Spotify OAuth login process by redirecting the user to Spotify's authorization page."""

        # Generate a code verifier and challenge for PKCE (Proof Key for Code Exchange)
        code_verifier, code_challenge = generate_code_verifier_and_challenge()
        session['code_verifier'] = code_verifier  # Store code verifier in session for use during callback

        # Define Spotify authorization URL and required parameters
        auth_url = "https://accounts.spotify.com/authorize"
        params = {
            'response_type': 'code',
            'client_id': session.get('SPOTIFY_CLIENT_ID'),  # Spotify client ID
            'redirect_uri': session.get('SPOTIFY_REDIRECT_URI'),  # Redirect URI for Spotify callback
            'scope': 'user-read-private user-read-email user-read-recently-played user-top-read playlist-modify-public playlist-modify-private',  # Access permissions
            'code_challenge_method': 'S256',  # Code challenge method for PKCE
            'code_challenge': code_challenge  # Code challenge generated from code verifier
        }

        # Redirect user to Spotify's authorization page with the specified parameters
        return redirect(auth_url + '?' + urlencode(params))


