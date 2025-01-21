import pytest
from app import app, db
from models import User, Playlist, Track
from uuid import uuid4


@pytest.fixture
def test_client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    with app.app_context():
        db.create_all()  # Initialize tables
        yield app.test_client()
        db.session.remove()


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure a clean database before each test."""
    with app.app_context():
        yield
        db.session.remove()
        db.reflect()
        db.metadata.drop_all(bind=db.engine, checkfirst=True)
        db.create_all()


def create_user(spotify_id=None):
    """Helper function to create a test user."""
    if spotify_id is None:
        spotify_id = str(uuid4())
    user = User(spotify_id=spotify_id, display_name="Test User", email="test@example.com")
    db.session.add(user)
    db.session.commit()
    return user


def test_user_creation(test_client):
    """Test that a user is created and retrieved correctly."""
    user = create_user()
    retrieved_user = User.query.filter_by(spotify_id=user.spotify_id).first()
    assert retrieved_user is not None
    assert retrieved_user.display_name == "Test User"


def test_playlist_creation(test_client):
    """Test that a playlist is created and retrieved correctly."""
    user = create_user()
    playlist = Playlist(spotify_id=str(uuid4()), name="Test Playlist", owner_id=user.id, total_tracks=5)
    db.session.add(playlist)
    db.session.commit()

    retrieved_playlist = Playlist.query.filter_by(name="Test Playlist").first()
    assert retrieved_playlist is not None
    assert retrieved_playlist.total_tracks == 5


def test_playlist_track_relationship(test_client):
    """Test the many-to-many relationship between playlists and tracks."""
    user = create_user()
    playlist = Playlist(spotify_id=str(uuid4()), name="Test Playlist", owner_id=user.id)
    track = Track(spotify_id=str(uuid4()), name="Test Track", album="Test Album", artists="Test Artist")
    db.session.add_all([playlist, track])
    db.session.commit()

    playlist.tracks.append(track)
    db.session.commit()

    retrieved_playlist = Playlist.query.filter_by(name="Test Playlist").first()
    assert retrieved_playlist is not None
    assert track in retrieved_playlist.tracks
