SpotMyVibes
Visit SpotMyVibes

Table of Contents
Introduction
Features
User Flow
Spotify API
Technology Stack
Setup & Installation
Introduction
SpotMyVibes is a personalized music discovery and playlist management app powered by the Spotify API. Users can log in with their Spotify account, discover new music based on their listening habits, explore tracks, albums, and artists, and manage their playlists directly through the app. The platform provides tailored recommendations, insight into top tracks and recently played songs, and a seamless way to curate playlists.

Features
Spotify Login:

Users can authenticate via their Spotify account using Spotify OAuth, ensuring secure login and access to their music data.
Top Tracks:

Displays the user's most listened-to tracks, allowing them to add these to any playlist easily.
Recently Played:

Shows the tracks that the user recently played, with options to add them to playlists or explore more from the artist/album.
Search Functionality:

Allows users to search for tracks, albums, and artists, and view detailed information about each.
Playlist Management:

Users can view, create, and manage playlists, adding tracks from their top tracks, recently played, or searched songs.
Music Recommendations:

Generates music recommendations based on the user’s favorite genres, artists, or tracks, allowing them to explore new music effortlessly.
View Artist/Album Details:

Users can explore the top tracks and albums of any artist or view tracklists of albums, with the ability to add tracks to their playlists.
User Flow
Login: Users are prompted to log in via their Spotify account. Once authenticated, the app fetches their Spotify data.

Dashboard: After logging in, users are greeted with their top tracks and recently played songs. They can also access playlists and search for new music.

Search & Explore: Users can search for tracks, albums, or artists, view their details, and add tracks to their playlists.

Recommendations: Users can get personalized recommendations based on genres, artists, or tracks, and add new tracks to their playlists from the suggestions.

Playlist Management: Users can manage their playlists by adding or removing tracks, viewing detailed playlists, and synchronizing their playlist with Spotify.

Spotify API
SpotMyVibes leverages the Spotify Web API for:

User authentication via Spotify OAuth.
Fetching user’s top tracks, recently played tracks, and playlists.
Searching for tracks, albums, and artists.
Managing playlists (adding/removing tracks).
Notes about Spotify API
The app requires an active Spotify Premium account to access certain features (e.g., playback control).
Spotify’s rate limiting must be taken into account. If many requests are made in a short period, the API may throttle the app temporarily.
Technology Stack
Backend:

Python (Flask): Lightweight web framework for building the backend and handling routes.
PostgreSQL: For persistent storage of user data, playlists, and track information.
SQLAlchemy: ORM for managing database interactions and models.
Frontend:

HTML/CSS: For structuring and styling the web pages.
Jinja2: Templating engine for rendering dynamic content in HTML.
JavaScript: For handling client-side interactions and dynamic page updates.
API:

Spotify Web API: For accessing user data, managing playlists, and fetching recommendations.
Authentication:

Spotify OAuth: Secure user authentication with Spotify's OAuth 2.0.
Deployment:

Render: For hosting the Flask app and PostgreSQL database in a live environment.
