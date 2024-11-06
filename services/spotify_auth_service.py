# services/spotify_auth_service.py

import requests
from flask import session, redirect, url_for, request
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, timedelta
from models import db, User
from flask_login import login_user, logout_user

class SpotifyAuthService:
    def __init__(self):
        # Initialize SpotifyOAuth instance to handle authorization with Spotify API
        self.sp_oauth = SpotifyOAuth()

    def login(self):
        """
        Generate the Spotify authorization URL and redirect the user to Spotify's login page.
        """
        auth_url = self.sp_oauth.get_authorize_url()
        return redirect(auth_url)

    def callback(self):
        """
        Handle the Spotify OAuth callback, exchanging the authorization code for tokens.
        """
        # Retrieve authorization code from the URL parameters
        code = request.args.get('code')
        token_info = self.sp_oauth.get_access_token(code)
        
        if token_info:
            access_token = token_info['access_token']
            refresh_token = token_info['refresh_token']
            expires_at = datetime.now() + timedelta(seconds=token_info['expires_in'])

            # Fetch user info from Spotify API
            user_info = self.fetch_user_info(access_token)

            # Create or update user in the database
            user = self.get_or_create_user(user_info, access_token, refresh_token, expires_at)

            # Log in the user using Flask-Login
            login_user(user)
            return redirect(url_for('user.dashboard'))  # Redirect to user's dashboard or profile page
        else:
            # Redirect to login if the token exchange fails
            return redirect(url_for('auth.login'))

    def fetch_user_info(self, access_token):
        """
        Retrieve user profile information from Spotify API using the access token.
        """
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get('https://api.spotify.com/v1/me', headers=headers)

        # Return the user's profile data in JSON format
        return response.json()

    def get_or_create_user(self, user_info, access_token, refresh_token, expires_at):
        """
        Create a new user in the database if the user doesn't already exist,
        or update the existing user's information.
        """
        user = User.query.filter_by(spotify_id=user_info['id']).first()
        
        if not user:
            # Create a new user if one does not already exist
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
            print(f"New user created: {user.display_name} ({user.spotify_id})")
        else:
            # Update the user's tokens and expiration if they already exist
            user.access_token = access_token
            user.refresh_token = refresh_token
            user.token_expiry = expires_at
            db.session.commit()
            print(f"Updated user: {user.display_name} ({user.spotify_id})")

        return user

    @staticmethod
    def logout():
        """
        Log out the user by clearing the Flask-Login session.
        """
        logout_user()
        session.clear()  # Optionally, clear the session entirely
        return redirect(url_for('home'))  # Redirect to the homepage after logout

