import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'codevault-super-secret-key-change-in-prod')
    # For PostgreSQL (e.g. postgresql://user:pass@localhost:5432/db)
    # Note: If the URL starts with 'postgres://', SQLAlchemy requires 'postgresql://' instead.
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'codevault.db'))
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Global Site Password ───────────────────────────────────────
    # Every visitor must enter this password to access CodeVault.
    # Change this value to whatever you want the site password to be.
    SITE_PASSWORD = os.environ.get('SITE_PASSWORD', 'codevault123')

    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SAMESITE = 'Lax'

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB limit

    ALLOWED_EXTENSIONS = {
        'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp',
        'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'zip', 'tar', 'gz', '7z',
        'py', 'js', 'ts', 'html', 'css', 'json', 'xml', 'yaml', 'yml',
        'md', 'csv', 'mp3', 'mp4', 'mov', 'avi'
    }

    # Note expiry options (in seconds)
    EXPIRY_OPTIONS = {
        'never': None,
        '1h': 3600,
        '1d': 86400,
        '7d': 604800,
        '30d': 2592000,
    }
