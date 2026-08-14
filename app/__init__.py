import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config

db = SQLAlchemy()


def create_app(config_class=Config):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(config_class)

    # Init extensions
    db.init_app(app)
    CORS(app)

    # Ensure upload and instance dirs exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'instance'), exist_ok=True)

    # Register blueprints — no global gate; access is per-note via 2-step codes
    from app.routes.notes import notes_bp
    from app.routes.files import files_bp
    from app.routes.pages import pages_bp

    app.register_blueprint(notes_bp, url_prefix='/api')
    app.register_blueprint(files_bp, url_prefix='/api')
    app.register_blueprint(pages_bp)

    # Create tables
    with app.app_context():
        db.create_all()

    return app
