# services/playlist_service.py
from models import Playlist, Track, db, User, playlist_tracks
from utils import make_spotify_request
import requests
from flask import session

class MusicService:
    
    @staticmethod
    def get_user_playlists(user_id):
        """Retrieve playlists for a given user."""
        return Playlist.query.filter_by(owner_id=user_id).all()  # This should return instances of Playlist

    @staticmethod
    def sync_user_playlists(spotify_id, access_token):
        """Sync Spotify playlists for a user and save them in the database."""

        # Validate the presence of spotify_id and access_token
        if not spotify_id or not access_token:
            print("Error: Missing spotify_id or access_token.")
            return None

        # Retrieve user from database
        user = User.query.filter_by(spotify_id=spotify_id).first()
        if not user:
            print("Error: User not found.")
            return None

        # Fetch user playlists from Spotify API
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            playlists_data = make_spotify_request("https://api.spotify.com/v1/me/playlists", headers=headers)
            if not playlists_data:
                print("Error: No playlist data retrieved.")
                return None
        except Exception as e:
            print(f"Error in make_spotify_request: {e}")
            return None

        # Synchronize playlists with database
        for item in playlists_data.get('items', []):
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
                # Update existing playlist information if already in database
                playlist.total_tracks = item['tracks']['total']
                playlist.image_url = item['images'][0]['url'] if item['images'] else None

        db.session.commit()
        return MusicService.get_user_playlists(user.id)

    @staticmethod
    def get_playlist_by_spotify_id(spotify_id):
        """Retrieve a playlist from the database using Spotify playlist ID."""
        return Playlist.query.filter_by(spotify_id=spotify_id).first_or_404()
    
    @staticmethod
    def get_sorted_tracks(playlist_id, sort_by):
        """Fetch and sort tracks in a playlist by the specified field."""
        return (
            db.session.query(Track)
            .join(playlist_tracks)
            .join(Playlist)
            .filter(Playlist.id == playlist_id)
            .order_by(sort_by)
            .all()
        )

    @staticmethod
    def fetch_top_tracks(access_token):
        """Fetch the user's top tracks from Spotify."""
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get("https://api.spotify.com/v1/me/top/tracks", headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching top tracks: {response.status_code} - {response.text}")
            return None

    @staticmethod
    def fetch_recently_played(access_token):
        """Fetch the user's recently played tracks from Spotify."""
        url = "https://api.spotify.com/v1/me/player/recently-played?limit=20"
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching recently played tracks: {response.status_code} - {response.text}")
            return None
        return response.json()

    @staticmethod
    def fetch_recommendations(params, access_token):
        """Fetch music recommendations based on seed values from Spotify."""
        url = "https://api.spotify.com/v1/recommendations"
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Error fetching recommendations: {response.status_code} - {response.text}")
            return None
        return response.json()

    @staticmethod
    def add_track_to_playlist(playlist_id, track_id, access_token):
        """Add a track to a Spotify playlist."""
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        data = {'uris': [f'spotify:track:{track_id}']}
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            return True, "Track added successfully."
        else:
            error_message = response.json().get("error", {}).get("message", "An error occurred.")
            print(f"Error adding track to playlist: {response.status_code} - {error_message}")
            return False, f"Failed to add track: {error_message}"

    @staticmethod
    def remove_track_from_playlist(playlist_id, track_id):
        """Remove a track from a playlist using the internal playlist ID."""
        try:
            # Fetch the playlist using the internal ID
            playlist = Playlist.query.get(playlist_id)
            if not playlist:
                print(f"Playlist with internal ID {playlist_id} not found.")
                return False
            
            # Fetch the track using the Spotify ID
            track = Track.query.filter_by(spotify_id=track_id).first()
            if not track:
                print(f"Track with ID {track_id} not found.")
                return False

            # Remove the track from the playlist
            playlist.tracks.remove(track)
            db.session.commit()  # Make sure to commit the session
            return True
        except Exception as e:
            print(f"Error removing track from playlist: {e}")
            return False



    @staticmethod
    def search_spotify(query, access_token):
        """
        Search Spotify for albums, artists, and tracks matching the query.
        """
        search_url = "https://api.spotify.com/v1/search"
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {
            'q': query,
            'type': 'album,artist,track',  # Search for albums, artists, and tracks
            'limit': 10  # Limit the number of results for each type
        }

        response = requests.get(search_url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()  # Return the search results as JSON
        else:
            print(f"Error in Spotify search: {response.status_code} - {response.text}")
            return None
        
    @staticmethod
    def fetch_artist(artist_id, access_token):
        """
        Fetches details of an artist, including their top tracks and albums.
        """
        headers = {'Authorization': f'Bearer {access_token}'}

        # Fetch artist details
        artist_url = f"https://api.spotify.com/v1/artists/{artist_id}"
        artist_response = requests.get(artist_url, headers=headers)
        if artist_response.status_code != 200:
            print(f"Error fetching artist: {artist_response.status_code} - {artist_response.text}")
            return None, None, None

        artist_data = artist_response.json()

        # Fetch artist's top tracks
        top_tracks_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
        top_tracks_params = {'market': 'US'}
        top_tracks_response = requests.get(top_tracks_url, headers=headers, params=top_tracks_params)
        top_tracks_data = top_tracks_response.json() if top_tracks_response.status_code == 200 else None

        # Fetch artist's albums
        albums_url = f"https://api.spotify.com/v1/artists/{artist_id}/albums"
        albums_params = {'include_groups': 'album', 'market': 'US', 'limit': 10}
        albums_response = requests.get(albums_url, headers=headers, params=albums_params)
        albums_data = albums_response.json() if albums_response.status_code == 200 else None

        return artist_data, top_tracks_data, albums_data
    
    @staticmethod
    def fetch_album(album_id, access_token):
        """
        Fetches details for a specific album by ID from the Spotify API.
        """
        headers = {'Authorization': f'Bearer {access_token}'}
        album_url = f"https://api.spotify.com/v1/albums/{album_id}"
        
        response = requests.get(album_url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch album with ID {album_id}: {response.status_code} - {response.text}")
            return None