# routes/music_routes.py
# This module handles music-related routes, including fetching top tracks, recently played, album, artist, recommendations, and search functionality.

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils import make_spotify_request, ensure_access_token
from models import User, Playlist
from services.spotify_service import get_spotify_id  # Updated import
from services.music_service import MusicService

# Blueprint for music-related routes
music_bp = Blueprint('music', __name__)

@music_bp.route('/top_tracks')
def top_tracks():
    """Fetch and display the user's top tracks."""
    if not ensure_access_token():
        return redirect(url_for('auth.login_route'))

    access_token = session.get('access_token')
    spotify_id = session.get('spotify_id')

    # Fetch top tracks data
    top_tracks_data = MusicService.fetch_top_tracks(access_token)
    if not top_tracks_data:
        flash("Error fetching top tracks.", "danger")
        return "Error fetching top tracks", 400

    # Fetch user playlists if the user is found
    user = User.query.filter_by(spotify_id=spotify_id).first()
    if user:
        user_playlists = MusicService.get_user_playlists(user.id)  # Ensure user.id is passed correctly
        print("User Playlists (top_tracks):", [(p.id, p.name) for p in user_playlists])  # Print the playlists
    else:
        user_playlists = []
        print("User not found.")

    return render_template('top_tracks.html', tracks=top_tracks_data['items'], playlists=user_playlists)


@music_bp.route('/recently_played')
def recently_played():
    """Fetch and display the user's recently played tracks."""
    if not ensure_access_token():
        return redirect(url_for('auth.login_route'))

    access_token = session.get('access_token')
    recently_played_data = MusicService.fetch_recently_played(access_token)

    if not recently_played_data or 'items' not in recently_played_data:
        flash("No recently played tracks found or unable to fetch data.", "danger")
        return render_template('recently_played.html', tracks=[])

    # Fetch user's playlists from the database
    spotify_id = session.get('spotify_id')
    user = User.query.filter_by(spotify_id=spotify_id).first()
    
    if user:
        playlists = MusicService.get_user_playlists(user.id)
        print("User Playlists (recently_played):", [(p.id, p.name) for p in playlists])  # Print the playlists
    else:
        playlists = []
        print("User not found.")

    return render_template('recently_played.html', tracks=recently_played_data['items'], playlists=playlists)



@music_bp.route('/album/<string:album_id>')
def view_album(album_id):
    """Fetch and display details of a specific album."""
    if not ensure_access_token():
        return redirect(url_for('auth.login_route'))

    access_token = session.get('access_token')
    album_data = MusicService.fetch_album(album_id, access_token)

    user = User.query.filter_by(spotify_id=session.get('spotify_id')).first()
    user_playlists = MusicService.get_user_playlists(user.id) if user else []

    if not album_data:
        flash("Error retrieving album information.", "danger")
        return redirect(url_for('music.search_results'))

    # Extract necessary information from the album data
    album_image = album_data['images'][0]['url'] if album_data['images'] else url_for('static', filename='default_album.png')
    tracks = []
    for item in album_data['tracks']['items']:
        track_info = {
            'name': item.get('name', 'Unknown Track'),
            'artists': ', '.join(artist['name'] for artist in item.get('artists', [{'name': 'Unknown Artist'}])),
            'spotify_id': item.get('id')
        }
        tracks.append(track_info)

    # Pass structured data to the template
    return render_template('view_album.html', album=album_data, album_image=album_image, tracks=tracks, playlists=user_playlists)


@music_bp.route('/artist/<string:artist_id>')
def view_artist(artist_id):
    """Fetch and display details of a specific artist."""
    if not ensure_access_token():
        return redirect(url_for('auth.login_route'))

    access_token = session.get('access_token')
    artist_data, top_tracks_data, albums_data = MusicService.fetch_artist(artist_id, access_token)

    if artist_data and top_tracks_data and albums_data:
        # Format followers count for display with commas
        artist_data['formatted_followers'] = f"{artist_data['followers']['total']:,}" if 'followers' in artist_data and 'total' in artist_data['followers'] else 'N/A'

        # Fetch user playlists
        user = User.query.filter_by(spotify_id=session.get('spotify_id')).first()
        user_playlists = MusicService.get_user_playlists(user.id) if user else []

        return render_template(
            'view_artist.html',
            artist=artist_data,
            top_tracks=top_tracks_data['tracks'],
            albums=albums_data['items'],
            playlists=user_playlists
        )
    else:
        flash("Error retrieving artist information.", "danger")
        return redirect(url_for('search_results'))


@music_bp.route('/recommendations')
def recommendations():
    """Fetch and display recommendations based on genre, artist, or track."""
    if not ensure_access_token():
        return redirect(url_for('auth.login_route'))

    access_token = session.get('access_token')
    recommendation_type = request.args.get('type')
    value = request.args.get('value')

    # Show flash message only if both type and value are provided
    if recommendation_type and value:
        params = {'limit': 10}
        if recommendation_type == 'genre':
            params['seed_genres'] = value.lower()
        elif recommendation_type == 'artist':
            artist_id = get_spotify_id(value, "artist", access_token)
            if artist_id:
                params['seed_artists'] = artist_id
            else:
                flash("Artist not found.", "danger")
                return render_template('recommendations.html')
        elif recommendation_type == 'track':
            track_id = get_spotify_id(value, "track", access_token)
            if track_id:
                params['seed_tracks'] = track_id
            else:
                flash("Track not found.", "danger")
                return render_template('recommendations.html')
        else:
            flash("Invalid recommendation type.", "danger")
            return render_template('recommendations.html')

        recommendations_data = MusicService.fetch_recommendations(params, access_token)
        if recommendations_data:
            tracks = recommendations_data['tracks']
            return render_template('recommendations.html', tracks=tracks)
        else:
            flash("Error fetching recommendations.", "danger")
            return render_template('recommendations.html', tracks=[])

    # Render the form without a flash message if no parameters are provided
    return render_template('recommendations.html')

@music_bp.route('/search', methods=['GET'])
def search_results():
    """Perform a search on Spotify and display results."""
    if not ensure_access_token():
        return redirect(url_for('auth.login_route'))

    access_token = session.get('access_token')
    query = request.args.get('query')
    search_results = MusicService.search_spotify(query, access_token)

    # Temporarily fetch all playlists, ignoring `user_id` to isolate the issue
    playlists = Playlist.query.all()  # Fetch all playlists without user filter
    print("Playlists fetched (all users):", playlists)  # Debug statement

    if search_results:
        return render_template(
            'search_results.html',
            albums=search_results['albums']['items'],
            artists=search_results['artists']['items'],
            tracks=search_results['tracks']['items'],
            playlists=playlists,  # Pass all playlists temporarily
            query=query  # Pass the query for display
        )
    else:
        flash("Error during search.", "danger")
        return redirect(url_for('home'))

