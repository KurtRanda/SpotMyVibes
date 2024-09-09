import pytest
from flask import url_for
from app import app, db, User, Playlist, Track
from unittest.mock import patch
# Fixture for setting up and tearing down the app context for each test
@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # In-memory database for tests
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing

    with app.app_context():
        db.create_all()  # Create all tables before the tests
        client = app.test_client()  # Flask test client instance
        yield client
        db.drop_all()  # Drop all tables after the tests

# Test the login route
def test_login(client):
    # Simulate a request to the login route
    response = client.get('/login')
    assert response.status_code == 302  # Redirect to Spotify auth page

# Test fetching top tracks (mocking the Spotify API response)
@patch('app.ensure_access_token', return_value=True)
def test_top_tracks(mock_ensure_access_token, client, requests_mock):
    # Mock the response from Spotify API for top tracks
    spotify_top_tracks_url = 'https://api.spotify.com/v1/me/top/tracks'
    requests_mock.get(spotify_top_tracks_url, json={
        "items": [
            {
                "id": "test_track_id_1",
                "name": "Test Track 1",
                "album": {"name": "Test Album 1", "images": [{"url": "https://example.com/image1.jpg"}]},
                "artists": [{"name": "Test Artist 1"}]
            }
        ]
    })

    # Mock session data for the logged-in user
    with client.session_transaction() as sess:
        sess['access_token'] = 'fake_access_token'
        sess['spotify_id'] = 'test_user'

    response = client.get('/top_tracks')
    assert response.status_code == 200  # Ensure a 200 response
    assert b"Test Track 1" in response.data  # Check if the track is in the response
 # Check that the track is in the response

# Test fetching playlists
def test_playlists(client, requests_mock):
    # Mock the Spotify API response for playlists
    spotify_playlists_url = 'https://api.spotify.com/v1/me/playlists'
    requests_mock.get(spotify_playlists_url, json={
        "items": [
            {
                "id": "test_playlist_id_1",
                "name": "Test Playlist 1",
                "tracks": {"total": 10},
                "images": [{"url": "https://example.com/playlist1.jpg"}]
            }
        ]
    })

    # Mock session data for the logged-in user
    with client.session_transaction() as sess:
        sess['access_token'] = 'fake_access_token'
        sess['spotify_id'] = 'test_user'

    # Create a test user in the database
    test_user = User(spotify_id="test_user", display_name="Test User", email="test@example.com")
    db.session.add(test_user)
    db.session.commit()

    response = client.get('/playlists')
    assert response.status_code == 200
    assert b"Test Playlist 1" in response.data  # Check that the playlist is in the response

# Test adding a track to a playlist
from unittest.mock import patch

@patch('app.ensure_access_token', return_value=True)
def test_add_track_to_playlist(mock_ensure_access_token, client, requests_mock):
    # Mock the Spotify API response for adding track to playlist
    spotify_add_track_url = 'https://api.spotify.com/v1/playlists/test_playlist_id_1/tracks'
    requests_mock.post(spotify_add_track_url, status_code=201, json={"snapshot_id": "test_snapshot_id"})

    # Mock session data for the logged-in user
    with client.session_transaction() as sess:
        sess['access_token'] = 'fake_access_token'
        sess['spotify_id'] = 'test_user'

    # Create and commit the test user to the database
    test_user = User(spotify_id="test_user", display_name="Test User", email="test@example.com")
    db.session.add(test_user)
    db.session.commit()  # Ensure the user is saved before adding the playlist

    # Now create the playlist with the correct owner_id
    test_playlist = Playlist(spotify_id="test_playlist_id_1", name="Test Playlist 1", owner_id=test_user.id)
    db.session.add(test_playlist)
    db.session.commit()

    # Simulate adding a track to the playlist
    response = client.post(f'/playlist/test_track_id_1/add', data={
        'playlist_id': 'test_playlist_id_1'
    })

    assert response.status_code == 302  # Redirect after success
    # Check the flash message (assuming you flash a message after adding the track)
    assert b'Track added successfully' in response.data


