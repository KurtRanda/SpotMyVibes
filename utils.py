import secrets
import os
import hashlib
import base64
import requests
import logging
import app
from models import Track
from datetime import datetime, timedelta
from flask import session, flash, redirect, url_for, Response
from config import Config


# Generate PKCE code verifier and challenge for OAuth
def generate_code_verifier_and_challenge():
    """Generates a code verifier and its corresponding challenge for OAuth PKCE flow."""
    code_verifier = secrets.token_urlsafe(64)  # 64-byte URL-safe string
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')  # SHA256 and URL-safe encoding
    return code_verifier, code_challenge


# General helper for making requests to Spotify's API
def make_spotify_request(url, method='GET', params=None, data=None, headers=None):
    """Makes an HTTP request to the Spotify API, handling errors and logging if necessary."""
    if headers is None:
        access_token = session.get('access_token')
        headers = {'Authorization': f'Bearer {access_token}'}

    try:
        # Perform the request based on the HTTP method
        response = getattr(requests, method.lower())(url, headers=headers, params=params, json=data)
        
        # Check if request was successful
        if not response.ok:
            handle_request_error(response, url, headers, params, data)
            return None

        return response.json()

    except requests.RequestException as e:
        error_message = f"Request failed: {e}"
        logging.error(error_message)
        flash(error_message, "danger") if session else logging.info("Flash not available")
        return None


def handle_request_error(response, url, headers, params, data):
    """Logs error details and optionally flashes the message to the user."""
    error_message = f"Error {response.status_code}: {response.text}"
    logging.error(f"Spotify API request failed: {error_message}")
    logging.debug(f"Request details - URL: {url}, Headers: {headers}, Params: {params}, Data: {data}")
    flash(error_message, "danger") if session else logging.info("Flash not available")


# Ensures the access token is valid, refreshing it if necessary
def ensure_access_token():
    """Checks if the current access token is valid, refreshing it if expired."""
    expires_in = session.get('expires_in')
    token_acquired_at = session.get('token_acquired_at')
    
    if not isinstance(expires_in, int) or not token_acquired_at:
        return redirect(url_for('auth.login_route'))
    
    current_time = int(datetime.utcnow().timestamp())
    
    if current_time - token_acquired_at >= expires_in:
        refresh_result = refresh_access_token()
        if isinstance(refresh_result, Response):  # Check if redirect
            return refresh_result
        elif not refresh_result:
            return redirect(url_for('auth.login_route'))

    return True


# Refreshes the access token using the stored refresh token
def refresh_access_token():
    """Attempts to refresh the Spotify access token using the refresh token."""
    refresh_token = session.get('refresh_token')
    
    # Prepare request to refresh token
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': Config.SPOTIFY_CLIENT_ID,
        'client_secret': Config.SPOTIFY_CLIENT_SECRET,
    }

    response = requests.post('https://accounts.spotify.com/api/token', data=payload)
    
    if response.status_code == 200:
        data = response.json()
        session['access_token'] = data['access_token']
        session['expires_in'] = data['expires_in']
        session['token_acquired_at'] = int(datetime.utcnow().timestamp())
        return True
    else:
        # Handle invalid_grant by clearing session and redirecting to login
        if response.json().get('error') == 'invalid_grant':
            session.clear()
            flash("Session expired or revoked. Please log in again.", "danger")
            return redirect(url_for('auth.login'))
        return False



def get_sort_options():
    """Provides sorting options for tracks in the playlist."""
    return {
        'artist': Track.artists,
        'album': Track.album,
        'name': Track.name,
        'genre': Track.genre
    }


def token_expiry_datetime(expires_in):
    """Calculates token expiry time as a datetime based on the provided seconds."""
    return datetime.utcnow() + timedelta(seconds=expires_in)

