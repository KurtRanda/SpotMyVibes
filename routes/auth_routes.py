# routes/auth_routes.py
# This module handles Spotify OAuth authentication, including login, callback, and logout routes.

from flask import Blueprint, redirect, url_for, session, request, flash, render_template
from utils import generate_code_verifier_and_challenge, make_spotify_request
from models import db, User
from config import Config
import requests
import time
from urllib.parse import urlencode

# Create a Blueprint for authentication routes
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def welcome():
    """Render the welcome page."""
    return render_template('welcome.html')

@auth_bp.route('/login')
def login_route():
    """Initiate the Spotify login process by redirecting to the Spotify authorization page."""
    # Generate code verifier and challenge for PKCE (Proof Key for Code Exchange)
    code_verifier, code_challenge = generate_code_verifier_and_challenge()
    session['code_verifier'] = code_verifier  # Store verifier in session for use during callback
    print(f"Set code_verifier: {code_verifier}")  # Log for debugging
    print(f"Set code_challenge: {code_challenge}")  # Log for debugging
    session.permanent = True  # Keep session active until browser close or logout

    # Prepare authorization URL with required parameters
    auth_params = {
        'response_type': 'code',
        'client_id': Config.SPOTIFY_CLIENT_ID,
        'scope': Config.SPOTIFY_SCOPE,
        'redirect_uri': Config.SPOTIFY_REDIRECT_URI,
        'code_challenge_method': 'S256',
        'code_challenge': code_challenge
    }
    auth_url = 'https://accounts.spotify.com/authorize?' + urlencode(auth_params)
    return redirect(auth_url)

@auth_bp.route('/callback')
def callback():
    """Handle the callback from Spotify after user authorization."""
    # Extract authorization code from the URL
    code = request.args.get('code')
    if not code:
        # Handle missing authorization code
        return 'Authorization failed: No code provided', 400

    code_verifier = session.get('code_verifier')  # Retrieve code verifier from session

    # Exchange authorization code for access and refresh tokens
    payload = {
        'client_id': Config.SPOTIFY_CLIENT_ID,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': Config.SPOTIFY_REDIRECT_URI,
        'code_verifier': code_verifier,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(Config.SPOTIFY_TOKEN_URL, data=payload, headers=headers)
    response_data = response.json()

    # Handle token response
    if response.status_code == 200:
        # Store tokens and expiration info in session
        session['access_token'] = response_data.get('access_token')
        session['refresh_token'] = response_data.get('refresh_token')
        session['expires_in'] = response_data.get('expires_in')
        session['token_acquired_at'] = int(time.time())

        # Fetch and store user profile information
        profile_data = make_spotify_request(Config.SPOTIFY_PROFILE_URL)
        if profile_data:
            spotify_id = profile_data['id']
            session['spotify_id'] = spotify_id  # Store Spotify ID in session
            # Check if the user already exists in the database
            user = User.query.filter_by(spotify_id=spotify_id).first()

            if not user:
                # Create a new user record if one doesn't already exist
                user = User(
                    spotify_id=spotify_id,
                    display_name=profile_data.get('display_name'),
                    email=profile_data.get('email'),
                    profile_image_url=profile_data['images'][0]['url'] if profile_data['images'] else None
                )
                db.session.add(user)
                db.session.commit()
                print("New user created:", user)
            else:
                print("User found:", user)

        return redirect(url_for('user.profile'))
    else:
        # If token request failed, show error and redirect to login
        error_description = response_data.get('error_description', 'Unknown error')
        flash(f"Error refreshing access token: {error_description}")
        return redirect(url_for('auth.login_route'))

@auth_bp.route('/logout')
def logout_route():
    """Clear the session and redirect to the welcome page."""
    session.clear()  # Remove all session data
    return redirect(url_for('welcome'))
