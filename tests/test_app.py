import pytest
from app import app, db
from sqlalchemy import MetaData


@pytest.fixture
def test_client():
    """Fixture to set up a test client for the Flask app."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    app.config['SESSION_TYPE'] = 'filesystem'
    
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()

        # Use MetaData to drop all tables safely
        meta = MetaData()
        meta.reflect(bind=db.engine)
        meta.drop_all(bind=db.engine)


def test_welcome_route(test_client):
    """Test the welcome route."""
    response = test_client.get('/')
    assert response.status_code == 200
    assert b"Welcome" in response.data  # Adjust this string based on the welcome page content


def test_404_error_handler(test_client):
    """Test the 404 error handler."""
    response = test_client.get('/nonexistent-route')
    assert response.status_code == 404
    assert b"Page Not Found" in response.data  # Adjust this string based on the 404 page content


def test_500_error_handler(test_client):
    """Test the 500 error handler by triggering an internal server error."""
    # Modify app config for this test
    app.config['TESTING'] = True
    app.config['PROPAGATE_EXCEPTIONS'] = False  # Disable exception propagation
    
    response = test_client.get('/error')
    assert response.status_code == 500
    assert b"Internal Server Error" in response.data  # Adjust based on your 500 page content

def test_datetimefilter_full():
    """Test the custom Jinja2 datetime filter with 'full' format."""
    test_date = "2023-01-01T12:34:56.000Z"
    formatted_date = app.jinja_env.filters['datetimeformat'](test_date, 'full')
    assert formatted_date == "Sunday, 01 January 2023 at 12:34 PM"


def test_datetimefilter_medium():
    """Test the custom Jinja2 datetime filter with 'medium' format."""
    test_date = "2023-01-01T12:34:56.000Z"
    formatted_date = app.jinja_env.filters['datetimeformat'](test_date, 'medium')
    assert formatted_date == "01 Jan 2023, 12:34 PM"


def test_datetimefilter_custom():
    """Test the custom Jinja2 datetime filter with a custom format."""
    test_date = "2023-01-01T12:34:56.000Z"
    custom_format = "%Y/%m/%d %H:%M:%S"
    formatted_date = app.jinja_env.filters['datetimeformat'](test_date, custom_format)
    assert formatted_date == "2023/01/01 12:34:56"





