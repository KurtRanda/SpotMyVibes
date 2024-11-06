# config.py

import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables from a .env file if it exists
load_dotenv()

class Config:
    """Base configuration class for the application."""

    # Secret key for session management and CSRF protection
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default_secret_key')  # Ensure to change this in production
    
    # SQLAlchemy database configuration
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        # Replace for PostgreSQL compatibility in SQLAlchemy
        SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://")
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'  # Fallback to local SQLite

    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable modification tracking to save resources

    # Spotify API credentials
    SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', 'your_spotify_client_id')
    SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', 'your_spotify_client_secret')
    
    # Spotify redirect URI - different in development vs. production
    SPOTIFY_REDIRECT_URI = (
        'http://127.0.0.1:5000/auth/callback' 
        if os.getenv("FLASK_ENV") == "development" 
        else os.getenv('SPOTIFY_REDIRECT_URI', 'https://your-production-url.com/auth/callback')
    )

    # Spotify API scope for required permissions
    SPOTIFY_SCOPE = (
        'user-read-private user-read-email user-read-recently-played '
        'user-top-read playlist-modify-public playlist-modify-private'
    )

    # Spotify API endpoints for authorization and token exchange
    SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
    SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
    SPOTIFY_PROFILE_URL = "https://api.spotify.com/v1/me"

    # Flask session settings
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)  # Session timeout set to 60 minutes


