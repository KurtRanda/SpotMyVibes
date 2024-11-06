# routes/user_routes.py
# This module provides user-specific routes, such as viewing the user's profile page.

from flask import Blueprint, render_template, redirect, url_for, session
from utils import ensure_access_token
from models import User
from services.spotify_service import sync_user_playlists

# Blueprint for user-related routes
user_bp = Blueprint('user', __name__)

@user_bp.route('/profile')
def profile():
    """Display the user's profile, including synced playlists from Spotify."""

    # Ensure the user is authenticated and has a valid access token
    if not ensure_access_token():
        return redirect(url_for('auth.login'))

    # Retrieve access token from the session
    access_token = session.get('access_token')

    # Sync playlists with Spotify using the Spotify service
    playlists = sync_user_playlists(access_token)

    # Retrieve the user from the database by Spotify ID in the session
    user = User.query.filter_by(spotify_id=session.get('spotify_id')).first()

    # Collect user profile data for display
    profile_data = {
        'display_name': user.display_name if user else "User",
        'email': user.email if user else "",
        'profile_image_url': user.profile_image_url if user else ""
    }

    # Render the profile page with the user's playlists and profile data
    return render_template('profile.html', playlists=playlists, profile=profile_data)

