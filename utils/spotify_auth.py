# Manage spotify authentication

# utils/spotify_auth.py

from flask import session, redirect, url_for, request
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, timedelta
from models import User
from app import db, login_manager
from flask_login import login_user, logout_user, current_user

def login():
    sp_oauth = SpotifyOAuth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

def callback():
    sp_oauth = SpotifyOAuth()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    
    if token_info:
        access_token = token_info['access_token']
        refresh_token = token_info['refresh_token']
        expires_at = datetime.now() + timedelta(seconds=token_info['expires_in'])

        # Get user info from Spotify
        headers = {'Authorization': f'Bearer {access_token}'}
        response = request.get('https://api.spotify.com/v1/me', headers=headers)
        user_info = response.json()

        # Check if user exists
        user = User.query.filter_by(spotify_id=user_info['id']).first()
        if not user:
            user = User(
                spotify_id=user_info['id'],
                display_name=user_info.get('display_name'),
                email=user_info.get('email'),
                profile_image=user_info['images'][0]['url'] if user_info.get('images') else None,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=expires_at
            )
            db.session.add(user)
            db.session.commit()
        else:
            # Update tokens
            user.access_token = access_token
            user.refresh_token = refresh_token
            user.token_expiry = expires_at
            db.session.commit()

        login_user(user)
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

def logout():
    logout_user()
    return redirect(url_for('home'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
