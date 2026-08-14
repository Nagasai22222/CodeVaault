from flask import Blueprint, render_template, abort
from app.models import Note
from app import db

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    return render_template('index.html')


@pages_bp.route('/<note_id>')
def view_note(note_id):
    note = Note.query.get(note_id)
    if not note:
        abort(404)
    if note.is_expired():
        db.session.delete(note)
        db.session.commit()
        abort(410)
    return render_template('note.html', note_id=note_id,
                           is_protected=note.is_password_protected,
                           title=note.title)


@pages_bp.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@pages_bp.errorhandler(410)
def gone(e):
    return render_template('410.html'), 410
