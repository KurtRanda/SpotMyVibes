#Database models
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Table, Column, Integer, ForeignKey

db = SQLAlchemy()

# User Model:
# Represents users of the app.
# playlists establishes a one-to-many relationship between User and Playlist.
# recommendations establishes a one-to-many relationship between User and Recommendation.
playlist_tracks = db.Table('playlist_tracks',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlists.id'), primary_key=True),
    db.Column('track_id', db.Integer, db.ForeignKey('tracks.id'), primary_key=True), extend_existing=True
)

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(255), nullable=False, unique=True)
    display_name = db.Column(db.String(255))
    email = db.Column(db.String(255))
    profile_image_url = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    access_token = db.Column(db.String(255))
    
    playlists = db.relationship('Playlist', backref='user', lazy=True)
    recommendations = db.relationship('Recommendation', backref='user', lazy=True)
# Track Model:
# Represents individual tracks.
# genres establishes a many-to-many relationship with the Genre model.
class Track(db.Model):
    __tablename__ = 'tracks'

    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(255), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=False)
    album = db.Column(db.String(255))
    artists = db.Column(db.String(255))
    image_url = db.Column(db.String(255))
    genre = db.Column(db.String, nullable=True)
    # Many-to-many relationship with playlists
    playlists = db.relationship('Playlist', secondary=playlist_tracks, back_populates='tracks')


# Playlist Model:
# Each playlist is associated with a user via owner_id.
# tracks establishes a relationship to Track model, linking tracks to playlists.

class Playlist(db.Model):
    __tablename__ = 'playlists'
    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(255), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_tracks = db.Column(db.Integer)
    image_url = db.Column(db.String(255))

    # Many-to-many relationship with tracks
    tracks = db.relationship('Track', secondary=playlist_tracks, back_populates='playlists')

# UserTrack Model:
# This model tracks which songs are associated with which playlists.
# track_id is a unique identifier for each track.
class UserTrack(db.Model):
    __tablename__ = 'user_tracks'

    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.String(255), nullable=False)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlists.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

# Recommendation Model:
# Stores recommended tracks for a user.
# reason allows you to store why this track was recommended.
class Recommendation(db.Model):
    __tablename__ = 'recommendations'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recommended_track_id = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Association Table:
# Links tracks to genres in a many-to-many relationship.
association_table = db.Table('association',
    db.Column('track_id', db.Integer, db.ForeignKey('tracks.id')),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id'))
)


# Genre Model:
# Represents musical genres.
class Genre(db.Model):
    __tablename__ = 'genres'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)



