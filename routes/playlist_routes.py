# routes/playlist_routes.py
# This module handles playlist-related routes, such as viewing, sorting, and adding/removing tracks from playlists.

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import Playlist, Track, db, playlist_tracks
from utils import ensure_access_token, make_spotify_request, get_sort_options
from services.spotify_service import fetch_genre_for_artist, sync_user_playlists, sync_tracks_for_playlist, sync_playlist_with_spotify
from services.music_service import MusicService
import requests
# Blueprint for playlist-related routes
playlist_bp = Blueprint('playlist', __name__)

@playlist_bp.route('/playlists')
def playlists():
    """Display all playlists for the authenticated user."""
    if not ensure_access_token():
        return redirect(url_for('auth.login'))

    # Retrieve user's playlists from Spotify via MusicService
    access_token = session.get('access_token')
    spotify_id = session.get('spotify_id')
    user_playlists = MusicService.sync_user_playlists(spotify_id, access_token)

    # Render playlists page with user playlists
    return render_template('playlists.html', playlists=user_playlists)

@playlist_bp.route('/playlist/<string:playlist_id>')
def view_playlist(playlist_id):
    """View details and tracks for a specific playlist."""
    if not ensure_access_token():
        return redirect(url_for('auth.login'))

    print(f"Attempting to load playlist with ID: {playlist_id}")  # Log playlist ID for debugging

    # Retrieve the playlist by Spotify ID
    playlist = MusicService.get_playlist_by_spotify_id(playlist_id)
    if not playlist:
        flash("Playlist not found.", "danger")
        return redirect(url_for('playlist.playlists'))

    # Sync tracks for the playlist from Spotify API
    try:
        sync_tracks_for_playlist(playlist.id, playlist.spotify_id)
        print(f"Tracks synchronized for playlist: {playlist.name}")  # Log successful sync
    except Exception as e:
        print(f"Error during sync_tracks_for_playlist: {e}")  # Log any sync errors
        flash("Error synchronizing playlist tracks. Please try again later.", "danger")
        return redirect(url_for('playlist.playlists'))

    # Render the playlist view with synced tracks
    return render_template('view_playlist.html', playlist=playlist, tracks=playlist.tracks)

@playlist_bp.route('/playlist/<string:playlist_id>/sort/<string:sort_by>')
def sort_tracks(playlist_id, sort_by):
    """Sort tracks in a playlist based on the specified criterion."""
    if not ensure_access_token():
        return redirect(url_for('auth.login'))

    # Fetch the playlist and sorting options
    playlist = MusicService.get_playlist_by_spotify_id(playlist_id)
    sort_options = get_sort_options()

    # Validate sort option and retrieve sorted tracks
    if sort_by in sort_options:
        sorted_tracks = MusicService.get_sorted_tracks(playlist.id, sort_options[sort_by])
        return render_template('view_playlist.html', playlist=playlist, tracks=sorted_tracks)
    else:
        flash("Invalid sorting option selected.", "danger")
        return redirect(url_for('playlist.view_playlist', playlist_id=playlist_id))

@playlist_bp.route('/playlist/<string:track_id>/add', methods=['POST'])
def add_track_to_playlist(track_id):
    """Add a specific track to a playlist."""
    if not ensure_access_token():
        return redirect(url_for('auth.login'))

    # Retrieve playlist ID and access token for API call
    playlist_id = request.form.get('playlist_id')
    access_token = session.get('access_token')

    # Attempt to add the track using MusicService
    success, message = MusicService.add_track_to_playlist(playlist_id, track_id, access_token)
    if success:
        flash('Track added successfully to the playlist!', 'success')
    else:
        flash(f"Failed to add track: {message}", 'danger')

    return redirect(request.referrer)

@playlist_bp.route('/playlist/<string:playlist_id>/remove_track/<string:track_id>', methods=['POST'])
def remove_track_from_playlist(playlist_id, track_id):
    """Remove a track from a playlist."""
    if not ensure_access_token():
        return redirect(url_for('auth.login'))

    # Fetch the playlist using the Spotify ID to get the internal ID
    playlist = Playlist.query.filter_by(spotify_id=playlist_id).first()
    if not playlist:
        flash("Playlist not found.", "danger")
        return redirect(url_for('playlist.view_playlists'))

    # Fetch the track using the Spotify ID
    track = Track.query.filter_by(spotify_id=track_id).first()
    if not track:
        flash("Track not found.", "danger")
        return redirect(url_for('playlist.view_playlist', playlist_id=playlist.spotify_id))

    # Attempt to remove the track from the playlist in the local database
    if track in playlist.tracks:
        playlist.tracks.remove(track)
        db.session.commit()  # Commit the changes to the local database


    # Now, remove the track from Spotify
    access_token = session.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    remove_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    data = {"tracks": [{"uri": f"spotify:track:{track_id}"}]}  # Correctly format the track ID

    response = requests.delete(remove_url, headers=headers, json=data)

    if response.status_code == 200:
        flash(f"Track {track.name} successfully removed from Spotify playlist.")
        # Optionally, sync the playlist with Spotify after track is removed
        sync_playlist_with_spotify(playlist_id)  
    else:
        flash(f"Failed to remove track from Spotify: {response.text}")

    # Redirect back to the playlist view
    return redirect(url_for('playlist.view_playlist', playlist_id=playlist.spotify_id))






