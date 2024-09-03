# stores configuration variables (secret keys and API credentials)

# config.py

import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key_here'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://spotifydb'
    SQLALCHEMY_TRACK_MODIFICATIONS = False


    SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID') or 'your_spotify_client_id'
    SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET') or 'your_spotify_client_secret'
    SPOTIFY_REDIRECT_URI = os.environ.get('SPOTIFY_REDIRECT_URI') or 'http://localhost:5000/callback'
