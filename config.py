# stores configuration variables (secret keys and API credentials)

# config.py

import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key_here'
    SQLALCHEMY_DATABASE_URI = os.environ.get('Dpostgres://u7klut5lsablv6:p35cab71cade7259b1d6e06336a575390a0140cbdccb96d56675bdb2d38c86c48@cd5gks8n4kb20g.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/dac8jk08g5o6nb')
    SQLALCHEMY_TRACK_MODIFICATIONS = False


    SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID') or 'your_spotify_client_id'
    SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET') or 'your_spotify_client_secret'
    SPOTIFY_REDIRECT_URI = os.environ.get('SPOTIFY_REDIRECT_URI') or 'http://localhost:5000/callback'
