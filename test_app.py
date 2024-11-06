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

# Test removing a track from a playlist
@patch('app.ensure_access_token', return_value=True)
def test_remove_track_from_playlist(mock_ensure_access_token, client):
    # Mock session data for the logged-in user
    with client.session_transaction() as sess:
        sess['access_token'] = 'fake_access_token'
        sess['spotify_id'] = 'test_user'

    # Create a test user in the database
    test_user = User(spotify_id="test_user", display_name="Test User", email="test@example.com")
    db.session.add(test_user)
    db.session.commit()

    # Create a test playlist and a track
    test_playlist = Playlist(spotify_id="test_playlist_id_1", name="Test Playlist", owner_id=test_user.id)
    test_track = Track(spotify_id="test_track_id_1", name="Test Track", album="Test Album", artists="Test Artist", image_url="https://example.com/image.jpg")
    db.session.add(test_playlist)
    db.session.add(test_track)
    db.session.commit()

    # Associate the track with the playlist
    test_playlist.tracks.append(test_track)
    db.session.commit()

    # Simulate the removal of the track from the playlist
    response = client.post(url_for('playlist.remove_track_from_playlist', playlist_id=test_playlist.spotify_id, track_id=test_track.spotify_id))

    assert response.status_code == 302  # Check for redirect after removal
    assert b'Track removed successfully!' in response.data  # Check the success flash message

    # Verify that the track has been removed from the playlist
    updated_playlist = Playlist.query.filter_by(spotify_id=test_playlist.spotify_id).first()
    assert test_track not in updated_playlist.tracks  # Ensure the track is no longer in the playlist

# Test fetching the playlist view to ensure it's still accessible after removal
def test_view_playlist_after_removal(client):
    # Similar setup as before to create the user and playlist
    with client.session_transaction() as sess:
        sess['access_token'] = 'fake_access_token'
        sess['spotify_id'] = 'test_user'

    test_user = User(spotify_id="test_user", display_name="Test User", email="test@example.com")
    db.session.add(test_user)
    db.session.commit()

    test_playlist = Playlist(spotify_id="test_playlist_id_1", name="Test Playlist", owner_id=test_user.id)
    test_track = Track(spotify_id="test_track_id_1", name="Test Track", album="Test Album", artists="Test Artist", image_url="https://example.com/image.jpg")
    db.session.add(test_playlist)
    db.session.add(test_track)
    db.session.commit()

    test_playlist.tracks.append(test_track)
    db.session.commit()

    # Remove the track
    client.post(url_for('playlist.remove_track_from_playlist', playlist_id=test_playlist.spotify_id, track_id=test_track.spotify_id))

    # View the playlist
    response = client.get(url_for('playlist.view_playlist', playlist_id=test_playlist.spotify_id))
    assert response.status_code == 200  # Ensure the playlist view is accessible
    assert b"No tracks available in this playlist." in response.data  # Check for the message if no tracks exist




