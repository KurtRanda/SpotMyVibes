# app.py

# Standard library imports
from os import getenv

# Third-party imports
from flask import Flask, render_template
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from datetime import datetime
# Local module imports
from config import Config
from models import db
from routes.auth_routes import auth_bp
from routes.user_routes import user_bp
from routes.playlist_routes import playlist_bp
from routes.music_routes import music_bp

# Initialize app and extensions
app = Flask(__name__)
app.config.from_object(Config)

# Database setup
db.init_app(app)

# CSRF Protection
csrf = CSRFProtect(app)

# Initialize Flask-Session
Session(app)

# Register Blueprints for modular routing
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(playlist_bp, url_prefix='/playlist')
app.register_blueprint(music_bp, url_prefix='/music')


# Define and register custom Jinja2 filter for datetime formatting
def datetimeformat(value, format='medium'):
    try:
        # Try parsing with fractional seconds first
        date = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%fZ')
    except ValueError:
        # Fallback to parsing without fractional seconds
        date = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
    
    if format == 'full':
        return date.strftime("%A, %d %B %Y at %I:%M %p")
    elif format == 'medium':
        return date.strftime("%d %b %Y, %I:%M %p")
    else:
        return date.strftime(format)

app.jinja_env.filters['datetimeformat'] = datetimeformat

@app.route('/')
def welcome():
    """Welcome page route."""
    return render_template('welcome.html')

# Error handlers for better user experience
@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(error):
    return render_template('500.html'), 500

# Run the application
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Consider using migrations in production

    # Use environment variable to control debug mode
    app.run(debug=getenv('FLASK_DEBUG', 'True') == 'True')

