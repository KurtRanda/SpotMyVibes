# services/spotify_service.py
from flask import session
from models import db, User, Playlist, Track
from utils import make_spotify_request
import requests


def fetch_genre_for_artist(artist_id):
    """
    Fetches genres for a given artist ID using the Spotify API.
    Returns a comma-separated string of genres or 'Unknown' if no genre is found.
    """
    access_token = session.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}'}
    artist_url = f"https://api.spotify.com/v1/artists/{artist_id}"
    
    try:
        response = requests.get(artist_url, headers=headers)
        if response.status_code == 200:
            artist_data = response.json()
            genres = artist_data.get('genres', [])
            return ', '.join(genres) if genres else 'Unknown'
    except requests.RequestException as e:
        print(f"Failed to fetch genre for artist {artist_id}: {e}")
    
    return 'Unknown'


def sync_user_playlists(access_token):
    """
    Syncs the user's Spotify playlists with the database.
    Retrieves playlists from Spotify, updates or creates them in the database, and returns all synced playlists.
    """
    user = User.query.filter_by(spotify_id=session.get('spotify_id')).first()
    if not user:
        print("Error: User not found.")
        return None

    headers = {'Authorization': f'Bearer {access_token}'}
    playlists_data = make_spotify_request("https://api.spotify.com/v1/me/playlists", headers=headers)
    if not playlists_data:
        print("Error: No playlist data retrieved.")
        return None

    for item in playlists_data['items']:
        playlist = Playlist.query.filter_by(spotify_id=item['id']).first()
        if not playlist:
            # Create new playlist
            playlist = Playlist(
                spotify_id=item['id'],
                name=item['name'],
                owner_id=user.id,
                total_tracks=item['tracks']['total'],
                image_url=item['images'][0]['url'] if item['images'] else None
            )
            db.session.add(playlist)
        else:
            # Update existing playlist
            playlist.total_tracks = item['tracks']['total']
            playlist.image_url = item['images'][0]['url'] if item['images'] else None

    db.session.commit()
    return Playlist.query.filter_by(owner_id=user.id).all()


def sync_playlist_with_spotify(playlist_id):
    """
    Syncs the tracks of a specific playlist with Spotify's data.
    Calls `sync_tracks_for_playlist` to update the playlist tracks in the database.
    """
    access_token = session.get('access_token')
    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first_or_404()
    sync_tracks_for_playlist(playlist.id, playlist.spotify_id)
    print(f"Playlist {playlist.spotify_id} synced with Spotify.")


def sync_tracks_for_playlist(playlist_id, playlist_spotify_id):
    """
    Syncs tracks of a specific playlist with Spotify API.
    Ensures all Spotify tracks are mirrored in the local database, including adding new and removing missing tracks.
    """
    access_token = session.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}'}
    tracks_url = f"https://api.spotify.com/v1/playlists/{playlist_spotify_id}/tracks"
    offset = 0
    limit = 100
    all_tracks = []

    # Fetch tracks with pagination
    while True:
        response = requests.get(tracks_url, headers=headers, params={'limit': limit, 'offset': offset})
        if response.status_code != 200:
            print(f"Failed to fetch tracks for playlist {playlist_spotify_id}: {response.status_code} - {response.text}")
            return

        tracks_data = response.json()
        all_tracks.extend(tracks_data['items'])
        if not tracks_data['next']:
            break
        offset += limit

    # Process tracks to sync with the database
    playlist = Playlist.query.filter_by(id=playlist_id).first_or_404()
    existing_tracks = {track.spotify_id for track in playlist.tracks}
    spotify_track_ids = {item['track']['id'] for item in all_tracks if item['track'] and item['track'].get('id')}

    # Remove tracks that are no longer in the Spotify playlist
    tracks_to_remove = [track for track in playlist.tracks if track.spotify_id not in spotify_track_ids]
    for track in tracks_to_remove:
        playlist.tracks.remove(track)

    # Add new tracks to the playlist
    for item in all_tracks:
        track_data = item['track']
        if not track_data or not track_data.get('id'):
            print(f"Skipping track with missing Spotify ID: {track_data}")
            continue

        # Only add the track if it is not already in the playlist's tracks
        if track_data['id'] not in existing_tracks:
            # Check if the track already exists in the database
            new_track = Track.query.filter_by(spotify_id=track_data['id']).first()
            if not new_track:
                genre = fetch_genre_for_artist(track_data['artists'][0]['id']) if track_data['artists'] else 'Unknown'
                new_track = Track(
                    spotify_id=track_data['id'],
                    name=track_data['name'],
                    album=track_data['album']['name'],
                    artists=', '.join([artist['name'] for artist in track_data['artists']]),
                    image_url=track_data['album']['images'][0]['url'] if track_data['album']['images'] else None,
                    genre=genre
                )
                db.session.add(new_track)

            # Now append the new track to the playlist if it isn't already there
            if new_track not in playlist.tracks:
                playlist.tracks.append(new_track)

    # Commit all changes to the database
    db.session.commit()
    print(f"Synced {len(all_tracks)} tracks for playlist '{playlist.name}' ({playlist_spotify_id})")



def get_spotify_id(query, type_, access_token):
    """
    Generalized function to retrieve Spotify ID for a given type (artist, track, etc.).
    """
    search_url = "https://api.spotify.com/v1/search"
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'q': query, 'type': type_, 'limit': 1}

    response = requests.get(search_url, headers=headers, params=params)
    if response.status_code == 200:
        results = response.json()
        items = results.get(f'{type_}s', {}).get('items', [])
        if items:
            return items[0]['id']
    return None
