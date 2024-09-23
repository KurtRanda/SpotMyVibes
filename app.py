from flask import Flask, jsonify, redirect, request, session, url_for, render_template, abort, make_response, flash 
from flask_wtf.csrf import CSRFProtect
from datetime import timedelta
from dotenv import load_dotenv
from sqlalchemy.orm import joinedload
from models import db, User, Track, Genre, Playlist, Recommendation, UserTrack, playlist_tracks  # Import db and all models
import requests, base64, os, hashlib, secrets, time
from flask_migrate import Migrate
from urllib.parse import urlencode
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine

load_dotenv()
app = Flask(__name__)
app.config['DEBUG'] = True
# Get DATABASE_URL dynamically from the environment and fix URI for SQLAlchemy compatibility
DATABASE_URL = os.getenv('DATABASE_URL') 
if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")
else:
    raise ValueError("DATABASE_URL environment variable is not set.")

# Configuration for SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure you have a secret key for sessions and CSRF protection
app.secret_key = secrets.token_hex(16)

app.config['SESSION_COOKIE_SECURE'] = True  # Ensures cookies are sent over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevents JavaScript from accessing session cookie
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Controls when cookies are sent (Lax is recommended for OAuth)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# CSRF Protection
csrf = CSRFProtect()
csrf.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Initialize the database with the app context
db.init_app(app)

# Spotify API details
client_id = os.getenv('SPOTIFY_CLIENT_ID')  # Corrected environment variable usage
client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')  # Corrected environment variable usage
redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI', 'https://spotmyvibes.herokuapp.com/callback')
scope = 'user-read-private user-read-email user-read-recently-played user-top-read playlist-modify-public playlist-modify-private'

# Check if the client ID and secret are set, if not, raise an error
if not client_id or not client_secret:
    raise ValueError("Spotify Client ID or Client Secret environment variables are not set.")

# Spotify Authorization URL
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
token_url = "https://accounts.spotify.com/api/token"
profile_url = 'https://api.spotify.com/v1/me'


### Helper functions ###

# Helper function to generate code verifier and challenge for PKCE
def generate_code_verifier_and_challenge():
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge


def make_spotify_request(url, method='GET', params=None, data=None):
    access_token = session.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}'}

    if method == 'GET':
        response = requests.get(url, headers=headers, params=params)
    elif method == 'POST':
        headers['Content-Type'] = 'application/json'
        response = requests.post(url, headers=headers, json=data)
    elif method == 'DELETE':
        headers['Content-Type'] = 'application/json'
        response = requests.delete(url, headers=headers, json=data)

    if response.status_code != 200:
        flash(f"Error: {response.status_code} - {response.text}")
        return None
    return response.json()

def get_valid_access_token():
    if ensure_access_token():
        return session.get('access_token')
    else:
        return redirect(url_for('login_route'))

def ensure_access_token():
    expires_in = session.get('expires_in')
    token_acquired_at = session.get('token_acquired_at')

    if not expires_in or not token_acquired_at:
        return False  # No token, need to log in again

    current_time = int(time.time())
    if current_time - token_acquired_at >= expires_in:
        refresh_access_token()

    return True

def refresh_access_token():
    refresh_token = session.get('refresh_token')
    
    if not refresh_token:
        flash("Refresh token is missing. Please log in again.")
        return None

    refresh_response = requests.post(token_url, data={
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
    })

    if refresh_response.status_code == 200:
        token_info = refresh_response.json()
        session['access_token'] = token_info.get('access_token')
        session['expires_in'] = token_info.get('expires_in')
        session['token_acquired_at'] = int(time.time())
        return True
    else:
        error_description = refresh_response.json().get('error_description', 'Unknown error')
        flash(f"Error refreshing access token: {error_description}")
        return None


def fetch_genre_for_artist(artist_id):
    access_token = session.get('access_token')
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    artist_url = f"https://api.spotify.com/v1/artists/{artist_id}"
    response = requests.get(artist_url, headers=headers)

    if response.status_code == 200:
        artist_data = response.json()
        genres = artist_data.get('genres', [])
        return ', '.join(genres) if genres else 'Unknown'
    
    return 'Unknown'

def sync_user_playlists():
    user = User.query.filter_by(spotify_id=session.get('spotify_id')).first()
    if not user:
        return None

    playlists_data = make_spotify_request("https://api.spotify.com/v1/me/playlists")
    if not playlists_data:
        return None

    for item in playlists_data['items']:
        playlist = Playlist.query.filter_by(spotify_id=item['id']).first()
        if not playlist:
            playlist = Playlist(
                spotify_id=item['id'],
                name=item['name'],
                owner_id=user.id,
                total_tracks=item['tracks']['total'],
                image_url=item['images'][0]['url'] if item['images'] else None
            )
            db.session.add(playlist)
        else:
            playlist.total_tracks = item['tracks']['total']
            playlist.image_url = item['images'][0]['url'] if item['images'] else None

    db.session.commit()
    return Playlist.query.filter_by(owner_id=user.id).all()

def sync_playlist_with_spotify(playlist_id):
    access_token = session.get('access_token')
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # Fetch the playlist from the database
    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first_or_404()

    # Sync the tracks for this playlist with Spotify API
    sync_tracks_for_playlist(playlist.id, playlist.spotify_id)

    print(f"Playlist {playlist.spotify_id} synced with Spotify.")


def sync_tracks_for_playlist(playlist_id, playlist_spotify_id):
    access_token = session.get('access_token')
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    # Initialize the base URL and offset
    tracks_url = f"https://api.spotify.com/v1/playlists/{playlist_spotify_id}/tracks"
    offset = 0
    limit = 100
    all_tracks = []

    # Fetch tracks with pagination (Spotify API limits to 100 tracks, using pagination to exceed that number)
    while True:
        response = requests.get(
            tracks_url,
            headers=headers,
            params={'limit': limit, 'offset': offset}
        )
        tracks_data = response.json()

        if response.status_code != 200:
            print(f"Failed to fetch tracks for playlist {playlist_spotify_id}: {response.json()}")
            return

        # Append the fetched tracks to the all_tracks list
        all_tracks.extend(tracks_data['items'])

        # Check if there are more tracks to fetch
        if not tracks_data['next']:
            break

        # Increment the offset by the limit to fetch the next set of tracks
        offset += limit

    # Sync the tracks in the database
    playlist = Playlist.query.filter_by(id=playlist_id).first_or_404()

    # Get the existing tracks' Spotify IDs in the playlist
    existing_tracks = {track.spotify_id for track in playlist.tracks}

    # Fetch the Spotify track IDs from the response
    spotify_track_ids = {item['track']['id'] for item in all_tracks if item['track'] and item['track'].get('id')}

    # Remove tracks from the playlist that are no longer in the Spotify playlist
    tracks_to_remove = [track for track in playlist.tracks if track.spotify_id not in spotify_track_ids]
    for track in tracks_to_remove:
        playlist.tracks.remove(track)

    # Add new tracks from the Spotify playlist to the database
    for item in all_tracks:
        track_data = item['track']
        # Ensure the track has a valid Spotify ID
        if not track_data or not track_data.get('id'):
            print(f"Skipping track with missing Spotify ID: {track_data}")
            continue

        if track_data['id'] not in existing_tracks:
            # Check if the track already exists in the database
            new_track = Track.query.filter_by(spotify_id=track_data['id']).first()
            if not new_track:
                # Fetch the genre dynamically or set it to 'Unknown' if not available
                genre = fetch_genre_for_artist(track_data['artists'][0]['id']) if track_data['artists'] else 'Unknown'

                new_track = Track(
                    spotify_id=track_data['id'],
                    name=track_data['name'],
                    album=track_data['album']['name'],
                    artists=', '.join([artist['name'] for artist in track_data['artists']]),
                    image_url=track_data['album']['images'][0]['url'] if track_data['album']['images'] else None,
                    genre=genre  # Ensure genre is a string, not a class
                )
                db.session.add(new_track)
                db.session.flush()  # Ensure the new track is saved

            # Check if the track is already in the playlist before adding
            if new_track not in playlist.tracks:
                playlist.tracks.append(new_track)

    # Commit the changes once all tracks are synced
    db.session.commit()


def get_artist_id(artist_name, access_token):
    search_url = "https://api.spotify.com/v1/search"
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'q': artist_name,
        'type': 'artist',
        'limit': 1  # Limit the result to only one artist
    }
    response = requests.get(search_url, headers=headers, params=params)

    if response.status_code == 200:
        results = response.json()
        if results['artists']['items']:
            return results['artists']['items'][0]['id']  # Return the first artist's ID
    return None


def get_track_id(track_name, access_token):
    search_url = "https://api.spotify.com/v1/search"
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'q': track_name,
        'type': 'track',
        'limit': 1  # Limit the result to only one track
    }
    response = requests.get(search_url, headers=headers, params=params)

    if response.status_code == 200:
        results = response.json()
        if results['tracks']['items']:
            return results['tracks']['items'][0]['id']  # Return the first track's ID
    return None


### Routes ###
@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/routes')
def list_routes():
    return jsonify([str(rule) for rule in app.url_map.iter_rules()])


@app.route('/login')
def login_route():
    code_verifier, code_challenge = generate_code_verifier_and_challenge()
    session['code_verifier'] = code_verifier
    session.permanent = True
    print(f"Session code_verifier set: {session.get('code_verifier')}") #debugging 404 error

    auth_params = {
        'response_type': 'code',
        'client_id': client_id,
        'scope': 'user-read-private user-read-email user-read-recently-played user-top-read playlist-modify-public playlist-modify-private',
        'redirect_uri': redirect_uri,
        'code_challenge_method': 'S256',
        'code_challenge': code_challenge
    }

    auth_url = 'https://accounts.spotify.com/authorize?' + urlencode(auth_params)
    return redirect(auth_url)


@app.route('/callback')
@csrf.exempt
def callback():
    code = request.args.get('code')
    if not code:
        return 'Authorization failed: No code provided', 400
    

    if code:
        code_verifier = session.get('code_verifier')
        print(f"Session code_verifier retrieved: {session.get('code_verifier')}") #404 debugging

        if not code_verifier:
            return 'Authorization failed: No code verifier found in session', 400
       
       # Payload for token exchange
        payload = {
            'client_id': client_id,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'code_verifier': code_verifier,
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.post(token_url, data=payload, headers=headers)
        response_data = response.json()

        if response.status_code == 200:
            session['access_token'] = response_data.get('access_token')
            session['refresh_token'] = response_data.get('refresh_token')
            session['expires_in'] = response_data.get('expires_in')
            session['token_acquired_at'] = int(time.time())

            profile_data = make_spotify_request(profile_url)

            session['spotify_id'] = profile_data['id']
            user = User.query.filter_by(spotify_id=profile_data['id']).first()

            if not user:
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
            # Log the error from Spotify's response for further debugging
            print(f"Error from Spotify: {response_data}")
            print(f"Authorization Code: {code}")
            print(f"Code Verifier: {code_verifier}")
            print(f"Payload being sent to Spotify: {payload}")
            return f"Error: {response_data.get('error_description', 'Unknown error')}", 400
    else:
        return 'Authorization failed', 400



@app.route('/profile')
def profile():
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    profile_data = make_spotify_request(profile_url)
    playlists = sync_user_playlists()

    return render_template('profile.html', profile=profile_data, playlists=playlists)

@app.route('/playlists')
def playlists():
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    # Sync the playlists from Spotify API (sync all playlists)
    sync_user_playlists()

    # Fetch the user based on the Spotify ID stored in the session
    user = User.query.filter_by(spotify_id=session.get('spotify_id')).first()

    if not user:
        return "User not found", 404

    # Fetch playlists from the database after syncing
    playlists = Playlist.query.filter_by(owner_id=user.id).all()

    return render_template('playlists.html', playlists=playlists)

@app.route('/playlist/<string:playlist_id>')
def view_playlist(playlist_id):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first_or_404()

    # Sync the tracks for this playlist when the user selects it
    sync_tracks_for_playlist(playlist.id, playlist.spotify_id)

    # Fetch the tracks associated with this playlist
    tracks = playlist.tracks  # Fetch using the many-to-many relationship

    response = make_response(render_template('view_playlist.html', playlist=playlist, tracks=tracks))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


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

    # Ensure the response structure is as expected
    if 'items' not in top_tracks_data:
        return "Error: Unexpected response structure from Spotify API", 400

    # Fetch playlists from the database
    user = User.query.filter_by(spotify_id=session.get('spotify_id')).first()
    playlists = Playlist.query.filter_by(owner_id=user.id).all()

    # Fetch genre for each track's artist and add it to the track data
    tracks_with_genres = []
    for track in top_tracks_data['items']:
        artist_id = track['artists'][0]['id']
        genre = fetch_genre_for_artist(artist_id)
        track['genre'] = genre
        tracks_with_genres.append(track)

    return render_template('top_tracks.html', tracks=tracks_with_genres, playlists=playlists)

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

    # Fetch playlists from database 
    user = User.query.filter_by(spotify_id=session.get('spotify_id')).first()
    playlists = Playlist.query.filter_by(owner_id=user.id).all()

    # Attach genres to tracks
    tracks_with_genres = []
    for item in recently_played_data['items']:
        track = item['track']
        
        if 'artists' in track and track['artists']:
            artist_id = track['artists'][0]['id']
            genre = fetch_genre_for_artist(artist_id)
            track['genre'] = genre
            tracks_with_genres.append(track)
        else:
            print(f"Skipping track with no artists: {track.get('name', 'Unknown')}")

    return render_template('recently_played.html', tracks=tracks_with_genres, playlists=playlists)

@app.route('/recommendations', methods=['GET'])
def recommendations():
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    access_token = session.get('access_token')

    recommendation_type = request.args.get('type')
    value = request.args.get('value')

    if not recommendation_type or not value:
        return render_template('recommendations.html')

    url = "https://api.spotify.com/v1/recommendations"
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    params = {'limit': 10}

    if recommendation_type == 'genre':
        params['seed_genres'] = value.lower()
    elif recommendation_type == 'artist':
        artist_id = get_artist_id(value, access_token)
        if artist_id:
            params['seed_artists'] = artist_id
        else:
            return "Artist not found."
    elif recommendation_type == 'track':
        track_id = get_track_id(value, access_token)
        if track_id:
            params['seed_tracks'] = track_id
        else:
            return "Track not found."

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        recommendations_data = response.json()
        tracks = recommendations_data['tracks']
        return render_template('recommendations.html', tracks=tracks)
    else:
        return f"Error fetching recommendations: {response.status_code}"

@app.route('/playlist/<string:playlist_id>/sort/<string:sort_by>')
def sort_tracks(playlist_id, sort_by):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    # Get the playlist
    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first_or_404()

    # Build the query for sorting
    if sort_by == 'artist':
        sorted_tracks = db.session.query(Track).join(playlist_tracks).join(Playlist).filter(Playlist.id == playlist.id).order_by(Track.artists).all()
    elif sort_by == 'album':
        sorted_tracks = db.session.query(Track).join(playlist_tracks).join(Playlist).filter(Playlist.id == playlist.id).order_by(Track.album).all()
    elif sort_by == 'name':
        sorted_tracks = db.session.query(Track).join(playlist_tracks).join(Playlist).filter(Playlist.id == playlist.id).order_by(Track.name).all()
    elif sort_by == 'genre':
        sorted_tracks = sorted(playlist.tracks, key=lambda track: track.genre if track.genre else '')  # Handle possible None values
    else:
        return "Invalid sort option", 400

    # Render the playlist with sorted tracks
    return render_template('view_playlist.html', playlist=playlist, tracks=sorted_tracks)


@app.route('/search', methods=['GET'])
def search_results():
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    query = request.args.get('query')
    search_params = {'q': query, 'type': 'album,artist,track', 'limit': 20, 'offset': 0}
    search_results = make_spotify_request('https://api.spotify.com/v1/search', params=search_params)

    if search_results:
        albums, artists, tracks = [], [], []
        for album in search_results.get('albums', {}).get('items', []):
            albums.append({
                'id': album['id'], 'name': album['name'], 'artist': album['artists'][0]['name'], 
                'image_url': album['images'][0]['url'] if album['images'] else None
            })
        for artist in search_results.get('artists', {}).get('items', []):
            artists.append({
                'id': artist['id'], 'name': artist['name'], 'genres': ", ".join(artist['genres']),
                'image_url': artist['images'][0]['url'] if artist['images'] else None
            })
        for track in search_results.get('tracks', {}).get('items', []):
            tracks.append({
                'id': track['id'], 'name': track['name'], 'artist': track['artists'][0]['name'], 
                'album': track['album']['name'], 'image_url': track['album']['images'][0]['url']
            })

        playlists = sync_user_playlists()
        return render_template('search_results.html', albums=albums, artists=artists, tracks=tracks, playlists=playlists)
    else:
        return render_template('search_results.html', error="Something went wrong or no results found")


@app.route('/album/<string:album_id>')
def view_album(album_id):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    album_data = make_spotify_request(f"https://api.spotify.com/v1/albums/{album_id}")

    if album_data:
        album = {
            'name': album_data['name'], 'artist': album_data['artists'][0]['name'],
            'release_date': album_data['release_date'], 'image_url': album_data['images'][0]['url'] if album_data['images'] else None,
            'tracks': [{'spotify_id': track['id'], 'name': track['name'], 'artist': ', '.join([artist['name'] for artist in track['artists']])}
                       for track in album_data['tracks']['items']]
        }
        playlists = sync_user_playlists()
        return render_template('view_album.html', album=album, playlists=playlists)
    else:
        return redirect(url_for('search_results'))


@app.route('/artist/<string:artist_id>')
def view_artist(artist_id):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    artist_data = make_spotify_request(f"https://api.spotify.com/v1/artists/{artist_id}")
    top_tracks_data = make_spotify_request(f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?market=US")
    albums_data = make_spotify_request(f"https://api.spotify.com/v1/artists/{artist_id}/albums")

    if artist_data and top_tracks_data and albums_data:
        artist = {'id': artist_data['id'], 'name': artist_data['name'], 'genres': ", ".join(artist_data.get('genres', [])),
                  'followers': artist_data['followers']['total'], 'image_url': artist_data['images'][0]['url']}

        top_tracks = [{'spotify_id': track['id'], 'name': track['name'], 'artist': ', '.join([artist['name'] for artist in track['artists']]),
                       'album': track['album']['name'], 'image_url': track['album']['images'][0]['url']}
                      for track in top_tracks_data['tracks']]

        albums = [{'spotify_id': album['id'], 'name': album['name'], 'image_url': album['images'][0]['url'] if album['images'] else None}
                  for album in albums_data['items']]

        playlists = sync_user_playlists()
        return render_template('view_artist.html', artist=artist, top_tracks=top_tracks, albums=albums, playlists=playlists)
    else:
        return redirect(url_for('search_results'))

@app.route('/playlist/<string:track_id>/add', methods=['POST'])
def add_track_to_playlist(track_id):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    # Get the selected playlist ID from the form
    playlist_id = request.form.get('playlist_id')

    # Ensure that both the track and playlist ID are present
    if not track_id or not playlist_id:
        return "Invalid track or playlist", 400

    # Get the access token and sync the track with Spotify
    access_token = session.get('access_token')
    add_track_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    response = requests.post(
        add_track_url,
        headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'},
        json={'uris': [f'spotify:track:{track_id}']}
    )

    if response.status_code == 201:
        # Success: Track added to the playlist
        flash('Track added successfully to the playlist!', 'success')
        sync_playlist_with_spotify(playlist_id)  # Sync the playlist with Spotify after the track is added
    else:
        # Handle failure
        flash(f"Failed to add track: {response.json().get('error', {}).get('message')}", 'danger')

    # Redirect back to the referring page (like top tracks or search results)
    return redirect(request.referrer)


@app.route('/playlist/<string:playlist_id>/remove_track/<string:track_id>', methods=['POST'])
def remove_track_from_playlist(playlist_id, track_id):
    if not ensure_access_token():
        return redirect(url_for('login_route'))

    # Fetch the playlist and track from the database
    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first_or_404()
    track = Track.query.filter_by(spotify_id=track_id).first_or_404()

    # Remove the track from the playlist in the database
    if track in playlist.tracks:
        playlist.tracks.remove(track)
        db.session.commit()

    # Now, remove the track from Spotify
    access_token = session.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    remove_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    data = {"tracks": [{"uri": f"spotify:track:{track_id}"}]}

    response = requests.delete(remove_url, headers=headers, json=data)

    if response.status_code == 200:
        flash(f"Track {track.name} successfully removed from Spotify playlist.")
        sync_playlist_with_spotify(playlist_id)  # Sync the playlist with Spotify after track is removed
    else:
        flash(f"Failed to remove track from Spotify: {response.text}")

    # Redirect back to the playlist view
    return redirect(url_for('view_playlist', playlist_id=playlist_id))


@app.route('/logout')
def logout_route():
    session.clear()
    return redirect(url_for('welcome'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


