from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index, Column, Integer, ForeignKey, String

db = SQLAlchemy()

# Association table linking playlists to tracks in a many-to-many relationship
playlist_tracks = db.Table(
    'playlist_tracks',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlists.id', ondelete="CASCADE"), primary_key=True),
    db.Column('track_id', db.Integer, db.ForeignKey('tracks.id', ondelete="CASCADE"), primary_key=True),
)

class User(db.Model):
    """Represents a Spotify user with associated playlists and recommendations."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(255), nullable=False, unique=True)
    display_name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    profile_image_url = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    access_token = db.Column(db.String(255))

    # One-to-many relationship with playlists and recommendations
    playlists = db.relationship('Playlist', backref='user', lazy=True, cascade="all, delete-orphan")
    recommendations = db.relationship('Recommendation', backref='user', lazy=True, cascade="all, delete-orphan")


class Track(db.Model):
    """Represents a track on Spotify, with attributes for easy retrieval and filtering."""
    __tablename__ = 'tracks'

    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(255), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    album = db.Column(db.String(255), index=True)
    artists = db.Column(db.String(255), index=True)
    image_url = db.Column(db.String(255))
    genre = db.Column(db.String, nullable=True, index=True)  # Genre as a string for quick access
    playlists = db.relationship('Playlist', secondary=playlist_tracks, back_populates='tracks')

    __table_args__ = (
        Index('ix_track_name_album_artists', 'name', 'album', 'artists'),  # Composite index for sorting
    )


class Playlist(db.Model):
    """Represents a playlist associated with a user, containing multiple tracks."""
    __tablename__ = 'playlists'

    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(255), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    total_tracks = db.Column(db.Integer)
    image_url = db.Column(db.String(255))

    # Many-to-many relationship with tracks
    tracks = db.relationship('Track', secondary=playlist_tracks, back_populates='playlists')

    __table_args__ = (
        Index('ix_playlist_owner_id', 'owner_id'),
    )


class Recommendation(db.Model):
    """Stores recommended tracks for users based on their preferences or listening history."""
    __tablename__ = 'recommendations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    recommended_track_id = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Association table for tracks and genres, if genres are assigned at runtime
association_table = db.Table(
    'association',
    db.Column('track_id', db.Integer, db.ForeignKey('tracks.id', ondelete="CASCADE")),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id', ondelete="CASCADE"))
)


class Genre(db.Model):
    """Represents musical genres for classification."""
    __tablename__ = 'genres'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)



