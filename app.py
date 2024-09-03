from flask import Flask, redirect, request, session, url_for, render_template, abort
from models import db, User, Track, Genre, Playlist, Recommendation, UserTrack  # Import `db` and all models
import requests
import base64
import os
import hashlib
import secrets
import time
from flask_migrate import Migrate
from urllib.parse import urlencode
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)

# Configuration for SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://kurt:mysecurepassword@localhost/spotifydb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'  # Ensure you have a secret key

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Initialize the database with the app context
db.init_app(app)

# Spotify API details
client_id = '145d25fd21e4441fa2c343749071f82c'  # Spotify API client ID
client_secret = 'your_client_secret'  # Spotify API client secret
redirect_uri = 'http://127.0.0.1:5000/callback'
scope = 'user-read-private user-read-email user-read-recently-played user-top-read'
token_url = "https://accounts.spotify.com/api/token"
profile_url = 'https://api.spotify.com/v1/me'

# Helper function to generate code verifier and challenge
def generate_code_verifier_and_challenge():
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge

code_verifier, code_challenge = generate_code_verifier_and_challenge()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login_route():
    code_verifier, code_challenge = generate_code_verifier_and_challenge()
    session['code_verifier'] = code_verifier

    auth_params = {
        'response_type': 'code',
        'client_id': client_id,
        'scope': scope,
        'redirect_uri': redirect_uri,
        'code_challenge_method': 'S256',
        'code_challenge': code_challenge
    }

    auth_url = 'https://accounts.spotify.com/authorize?' + urlencode(auth_params)
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')

    if code:
        code_verifier = session.get('code_verifier')

        # Prepare the payload to exchange the authorization code for an access token
        payload = {
            'client_id': client_id,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': code_verifier,
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = requests.post(token_url, data=payload, headers=headers)
        response_data = response.json()

        if response.status_code == 200:
            # Store access token and refresh token in the session
            session['access_token'] = response_data.get('access_token')
            session['refresh_token'] = response_data.get('refresh_token')
            session['expires_in'] = response_data.get('expires_in')
            session['token_acquired_at'] = int(time.time())

            # Fetch user profile data from Spotify
            headers = {
                'Authorization': f'Bearer {session["access_token"]}'
            }
            profile_response = requests.get(profile_url, headers=headers)
            profile_data = profile_response.json()

            # Store spotify_id in session
            session['spotify_id'] = profile_data['id']

            # Check if the user already exists in the database
            user = User.query.filter_by(spotify_id=profile_data['id']).first()

            if not user:
                # Create a new user if not found
                user = User(
                    spotify_id=profile_data['id'],
                    display_name=profile_data['display_name'],
                    email=profile_data['email'],
                    profile_image_url=profile_data['images'][0]['url'] if profile_data['images'] else None
                )
                db.session.add(user)
                db.session.commit()

            return redirect(url_for('profile'))

        else:
            return f"Error: {response_data.get('error_description', 'Unknown error')}", 400
    else:
        return 'Authorization failed', 400

def refresh_access_token():
    refresh_token = session.get('refresh_token')

    # Refresh the access token using the refresh token
    refresh_response = requests.post(token_url, data={
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
    })

    # Parse the new access token
    token_info = refresh_response.json()
    session['access_token'] = token_info.get('access_token')
    session['expires_in'] = token_info.get('expires_in')
    session['token_acquired_at'] = int(time.time())

def ensure_access_token():
    expires_in = session.get('expires_in')
    token_acquired_at = session.get('token_acquired_at')

    if not expires_in or not token_acquired_at:
        return False  # No token, need to log in again

    current_time = int(time.time())
    if current_time - token_acquired_at >= expires_in:
        refresh_access_token()
    
    return True

@app.route('/profile')
def profile():
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    access_token = session.get('access_token')
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    # Fetch user profile data from Spotify
    profile_response = requests.get(profile_url, headers=headers)
    profile_data = profile_response.json()

    # Fetch the user's playlists from Spotify
    playlists_url = "https://api.spotify.com/v1/me/playlists"
    playlists_response = requests.get(playlists_url, headers=headers)
    playlists_data = playlists_response.json()

    for item in playlists_data['items']:
        playlist_spotify_id = item['id']
        playlist = Playlist.query.filter_by(spotify_id=playlist_spotify_id).first()

        if not playlist:
            # Create a new playlist in the database if it doesn't exist
            playlist = Playlist(
                spotify_id=playlist_spotify_id,
                name=item['name'],
                owner_id=session.get('user_id'),  # Assuming the user's ID is stored in the session
                total_tracks=item['tracks']['total'],
                image_url=item['images'][0]['url'] if item['images'] else None
            )
            db.session.add(playlist)
            db.session.commit()

    playlists = Playlist.query.filter_by(owner_id=session.get('user_id')).all()

    return render_template('profile.html', profile=profile_data, playlists=playlists)

##### Search Route ############
@app.route('/search', methods=['GET'])
def search_results():
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    access_token = session.get('access_token')
    query = request.args.get('query')
    search_type = request.args.get('type', 'track')  # Default to track if not provided
    market = request.args.get('market', None)
    limit = request.args.get('limit', 20)
    offset = request.args.get('offset', 0)
    playlist_id = request.args.get('playlist_id')  # Check if search is from a playlist

    # Define the search parameters
    search_params = {
        'q': query,
        'type': search_type,
        'limit': limit,
        'offset': offset,
    }

    # Include market if specified
    if market:
        search_params['market'] = market

    # Print the URL and parameters to verify them
    print(f"Request URL: https://api.spotify.com/v1/search")
    print(f"Search Params: {search_params}")
    print(f"Authorization: Bearer {access_token}")

    # Make the API request to Spotify
    response = requests.get(
        'https://api.spotify.com/v1/search',
        headers={
            'Authorization': f'Bearer {access_token}'
        },
        params=search_params
    )
   
    # Print the response content for debugging
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Content: {response.json()}")

    # Handle the response
    if response.status_code == 200:
        search_results = response.json()

        # Parse the results based on the search type
        parsed_results = []
        if search_type == 'album' and 'albums' in search_results:
            albums = search_results['albums']['items']
            for album in albums:
                album_info = {
                    'name': album.get('name'),
                    'artist': album['artists'][0].get('name') if album['artists'] else None,
                    'release_date': album.get('release_date'),
                    'image_url': album['images'][0]['url'] if album['images'] else None,
                    'spotify_url': album.get('external_urls', {}).get('spotify')
                }
                parsed_results.append(album_info)
        elif search_type == 'track' and 'tracks' in search_results:
            tracks = search_results['tracks']['items']
            for track in tracks:
                track_info = {
                    'name': track.get('name'),
                    'artist': track['artists'][0].get('name') if track['artists'] else None,
                    'album': track['album'].get('name') if track.get('album') else None,
                    'release_date': track['album'].get('release_date') if track.get('album') else None,
                    'image_url': track['album']['images'][0]['url'] if track.get('album') and track['album']['images'] else None,
                    'spotify_url': track.get('external_urls', {}).get('spotify')
                }
                parsed_results.append(track_info)
        elif search_type == 'artist' and 'artists' in search_results:
            artists = search_results['artists']['items']
            for artist in artists:
                artist_info = {
                    'name': artist.get('name'),
                    'followers': artist.get('followers', {}).get('total'),
                    'genres': ", ".join(artist.get('genres', [])),
                    'image_url': artist['images'][0]['url'] if artist['images'] else None,
                    'spotify_url': artist.get('external_urls', {}).get('spotify')
                }
                parsed_results.append(artist_info)
        elif search_type == 'playlist' and 'playlists' in search_results:
            playlists = search_results['playlists']['items']
            for playlist in playlists:
                playlist_info = {
                    'name': playlist.get('name'),
                    'owner': playlist['owner'].get('display_name'),
                    'track_count': playlist.get('tracks', {}).get('total'),
                    'image_url': playlist['images'][0]['url'] if playlist['images'] else None,
                    'spotify_url': playlist.get('external_urls', {}).get('spotify')
                }
                parsed_results.append(playlist_info)

        if playlist_id:
            # Render the playlist view with the search results included
            playlist = get_playlist(playlist_id)  # Fetch the playlist object from the database
            return render_template('view_playlist.html', playlist=playlist, tracks=playlist.tracks, search_results=parsed_results)
        
        # Render the general search results template
        return render_template('search_results.html', results=parsed_results)
    else:
        # Handle errors or no results
        return render_template('search_results.html', error="Something went wrong or no results found")



@app.route('/sync_playlists')
def sync_playlists():
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    access_token = session.get('access_token')
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    playlists_response = requests.get('https://api.spotify.com/v1/me/playlists', headers=headers)
    playlists_data = playlists_response.json()

    # Retrieve the user from the database using the spotify_id stored in the session
    user = User.query.filter_by(spotify_id=session.get('spotify_id')).first()

    if not user:
        return "User not found", 404

    for item in playlists_data['items']:
        # Check if the playlist already exists in the database
        existing_playlist = Playlist.query.filter_by(spotify_id=item['id']).first()

        if not existing_playlist:
            # Add new playlist to the database
            new_playlist = Playlist(
                spotify_id=item['id'],
                name=item['name'],
                owner_id=user.id,  # Adjust this based on your user structure
                total_tracks=item['tracks']['total'],
                image_url=item['images'][0]['url'] if item['images'] else None
            )
            db.session.add(new_playlist)
            db.session.commit()

    return "Playlists synced successfully!"


@app.route('/playlists')
def playlists():
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    access_token = session.get('access_token')
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    playlists_response = requests.get('https://api.spotify.com/v1/me/playlists', headers=headers)
    playlists_data = playlists_response.json()
    
    return render_template('playlists.html', playlists=playlists_data['items'])


def get_playlist(playlist_id):
    """
    Fetches a playlist from the database by its Spotify ID.
    
    Args:
        playlist_id (str): The Spotify ID of the playlist.
    
    Returns:
        Playlist: The Playlist object from the database.
    """
    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first()
    if not playlist:
        raise ValueError(f"Playlist with ID {playlist_id} not found.")
    return playlist


@app.route('/playlist/<string:playlist_id>')
def view_playlist(playlist_id):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first_or_404()

    # Sync the tracks for this playlist when the user selects it
    sync_tracks_for_playlist(playlist.id, playlist.spotify_id)

    # Fetch the tracks from the database after syncing
    tracks = Track.query.filter_by(playlist_id=playlist.id).all()

    return render_template('view_playlist.html', playlist=playlist, tracks=tracks)


def sync_tracks_for_playlist(playlist_id, playlist_spotify_id):
    access_token = session.get('access_token')
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    tracks_url = f"https://api.spotify.com/v1/playlists/{playlist_spotify_id}/tracks"
    response = requests.get(tracks_url, headers=headers)
    tracks_data = response.json()

    with db.session.no_autoflush:
        for item in tracks_data['items']:
            track_data = item.get('track')

            if not track_data:
                continue  # Skip if track data is missing

            spotify_id = track_data.get('id')
            if not spotify_id:
                print(f"Skipping track with missing spotify_id: {track_data.get('name')}")
                continue  # Skip tracks with missing spotify_id

            # Check if the track already exists in the database
            existing_track = Track.query.filter_by(spotify_id=spotify_id, playlist_id=playlist_id).first()

            if existing_track:
                print(f"Track {track_data.get('name')} already exists in playlist {playlist_id}, skipping.")
                continue  # Skip this track since it already exists

            # Safely access image_url
            images = track_data.get('album', {}).get('images', [])
            image_url = images[0]['url'] if images else None

            # If the track does not exist, add it to the database
            new_track = Track(
                spotify_id=spotify_id,
                name=track_data.get('name'),
                album=track_data.get('album', {}).get('name'),
                artists=', '.join([artist['name'] for artist in track_data.get('artists', [])]),
                image_url=image_url,
                playlist_id=playlist_id
            )
            db.session.add(new_track)

        try:
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            print(f"Error committing changes: {e}")

@app.route('/playlist/<string:playlist_id>/add_track', methods=['POST'])
def add_track_to_playlist(playlist_id):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first_or_404()
    track_id = request.form.get('track_id')

    track = Track.query.filter_by(spotify_id=track_id).first()
    if not track:
        # Fetch track details from Spotify API if it doesn't exist in the database
        # You might want to write a function to handle this

    # Associate the track with the playlist
        track.playlist_id = playlist.id
    db.session.commit()

    return redirect(url_for('view_playlist', playlist_id=playlist.spotify_id))

@app.route('/playlist/<string:playlist_id>/remove_track/<string:track_id>', methods=['POST'])
def remove_track_from_playlist(playlist_id, track_id):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first_or_404()
    track = Track.query.filter_by(spotify_id=track_id, playlist_id=playlist.id).first_or_404()

    db.session.delete(track)
    db.session.commit()

    return redirect(url_for('view_playlist', playlist_id=playlist.spotify_id))

@app.route('/playlist/<string:playlist_id>/filter', methods=['GET', 'POST'])
def filter_tracks(playlist_id):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first_or_404()

    if request.method == 'POST':
        genre_name = request.form.get('genre')
        tracks = Track.query.join(Track.genres).filter(Genre.name.ilike(f'%{genre_name}%'), Track.playlist_id == playlist.id).all()
    else:
        tracks = Track.query.filter_by(playlist_id=playlist.id).all()

    return render_template('view_playlist.html', playlist=playlist, tracks=tracks)

@app.route('/playlist/<string:playlist_id>/sort/<string:sort_by>')
def sort_tracks(playlist_id, sort_by):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first_or_404()

    if sort_by == 'name':
        tracks = Track.query.filter_by(playlist_id=playlist.id).order_by(Track.name).all()
    elif sort_by == 'artist':
        tracks = Track.query.filter_by(playlist_id=playlist.id).order_by(Track.artists).all()
    elif sort_by == 'album':
        tracks = Track.query.filter_by(playlist_id=playlist.id).order_by(Track.album).all()
    else:
        tracks = Track.query.filter_by(playlist_id=playlist.id).all()

    return render_template('view_playlist.html', playlist=playlist, tracks=tracks)

@app.route('/top_tracks')
def top_tracks():
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    access_token = session.get('access_token')
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    top_tracks_response = requests.get('https://api.spotify.com/v1/me/top/tracks', headers=headers)

    if top_tracks_response.status_code != 200:
        return f"Error fetching top tracks: {top_tracks_response.status_code} - {top_tracks_response.text}", 400

    top_tracks_data = top_tracks_response.json()

    if 'items' not in top_tracks_data:
        return "Error: Unexpected response structure from Spotify API", 400

    return render_template('top_tracks.html', tracks=top_tracks_data['items'])

@app.route('/tracks', methods=['GET', 'POST'])
def tracks():
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    if request.method == 'POST':
        genre_query = request.form.get('genre')
        tracks = Track.query.join(Track.genres).filter(Genre.name.ilike(f'%{genre_query}%')).all()
    else:
        tracks = Track.query.all()
    return render_template('tracks.html', tracks=tracks)

@app.route('/recently_played')
def recently_played():
    if not ensure_access_token():
        return redirect(url_for('login_route'))
    
    access_token = session.get('access_token')
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    recently_played_response = requests.get('https://api.spotify.com/v1/me/player/recently-played', headers=headers)
    
    if recently_played_response.status_code != 200:
        return f"Error fetching recently played tracks: {recently_played_response.status_code} - {recently_played_response.text}", 400
    
    recently_played_data = recently_played_response.json()

    if 'items' not in recently_played_data or not recently_played_data['items']:
        return "No recently played tracks found.", 200

    return render_template('recently_played.html', tracks=recently_played_data['items'])

@app.route('/logout')
def logout_route():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure the tables are created before running the app
    app.run(debug=True)

