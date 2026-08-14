import re
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Note, NoteHistory
from app.utils import generate_slug, calculate_expiry
import bcrypt
from datetime import datetime, timezone

notes_bp = Blueprint('notes', __name__)

# Valid code pattern: 3–40 chars, letters / digits / hyphens / underscores
_CODE_RE = re.compile(r'^[A-Za-z0-9_-]{3,40}$')


def _check_code2(note: Note, provided: str) -> bool:
    """Verify the 2nd code (protection PIN) against the stored hash."""
    if not note.is_password_protected:
        return True
    if not provided:
        return False
    return bcrypt.checkpw(provided.encode('utf-8'), note.password_hash.encode('utf-8'))


# ── Create New Code ─────────────────────────────────────────────────────────────
@notes_bp.route('/create', methods=['POST'])
def create_code():
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()

    if not code:
        return jsonify({'error': 'Please enter a code.'}), 400

    if not _CODE_RE.match(code):
        return jsonify({'error': 'Code must be 3–40 characters (letters, numbers, - or _).'}), 400

    note = Note.query.get(code)
    if note:
        if note.is_expired():
            db.session.delete(note)
            db.session.commit()
        else:
            return jsonify({'error': 'This code is already in use. Please choose another.'}), 409

    new_note = Note(
        id=code,
        title='Untitled Note',
        content='',
        is_password_protected=False,
        expires_at=None,
        language='plaintext',
        is_markdown=False,
    )
    db.session.add(new_note)
    db.session.commit()

    result = new_note.to_dict(include_content=True)
    result['exists'] = False
    result['protected'] = False
    result['files'] = []
    return jsonify(result), 201


# ── Access Existing Code ──────────────────────────────────────────────────────
@notes_bp.route('/access', methods=['POST'])
def access_code():
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()

    if not code:
        return jsonify({'error': 'Please enter a code.'}), 400

    note = Note.query.get(code)
    if not note:
        return jsonify({'error': 'Vault not found. Please check your code.'}), 404

    if note.is_expired():
        db.session.delete(note)
        db.session.commit()
        return jsonify({'error': 'This vault has expired.'}), 410

    if note.is_password_protected:
        # Return metadata only — frontend will show 2nd-code gate
        return jsonify({
            'exists': True,
            'protected': True,
            'id': note.id,
            'title': note.title,
            'message': 'This code is protected. Enter your 2nd code to open it.',
        }), 200
    else:
        # Open freely
        note.views += 1
        db.session.commit()
        result = note.to_dict(include_content=True)
        result['exists'] = True
        result['protected'] = False
        result['files'] = [f.to_dict() for f in note.files]
        return jsonify(result), 200


# ── Unlock Protected Note (2nd code verification) ─────────────────────────────
@notes_bp.route('/notes/<note_id>/unlock', methods=['POST'])
def unlock_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.is_expired():
        return jsonify({'error': 'This note has expired.'}), 410

    data = request.get_json(silent=True) or {}
    code2 = data.get('code2', '').strip()

    if not _check_code2(note, code2):
        return jsonify({'error': 'Incorrect 2nd code. Please try again.'}), 401

    note.views += 1
    db.session.commit()

    result = note.to_dict(include_content=True)
    result['exists'] = True
    result['protected'] = True
    result['files'] = [f.to_dict() for f in note.files]
    return jsonify(result), 200


# ── Create Note (programmatic / legacy) ───────────────────────────────────────
@notes_bp.route('/notes', methods=['POST'])
def create_note():
    data = request.get_json(silent=True) or {}

    custom_id = (data.get('id') or '').strip()
    if custom_id:
        if not _CODE_RE.match(custom_id):
            return jsonify({'error': 'Code must be 3–40 chars, letters/digits/-/_'}), 400
        if Note.query.get(custom_id):
            return jsonify({'error': 'That code is already taken.'}), 409
        slug = custom_id
    else:
        for _ in range(10):
            slug = generate_slug()
            if not Note.query.get(slug):
                break
        else:
            return jsonify({'error': 'Could not generate unique ID.'}), 500

    code2_raw = data.get('code2', '').strip()
    password_hash = None
    is_protected = False

    if code2_raw:
        is_protected = True
        password_hash = bcrypt.hashpw(code2_raw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    note = Note(
        id=slug,
        title=data.get('title', 'Untitled Note')[:200],
        content=data.get('content', ''),
        is_password_protected=is_protected,
        password_hash=password_hash,
        expires_at=calculate_expiry(data.get('expiry', 'never')),
        language=data.get('language', 'plaintext'),
        is_markdown=bool(data.get('is_markdown', False)),
    )
    db.session.add(note)
    db.session.commit()
    return jsonify({'success': True, 'note': note.to_dict()}), 201


# ── Get Note ──────────────────────────────────────────────────────────────────
@notes_bp.route('/notes/<note_id>', methods=['GET'])
def get_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.is_expired():
        db.session.delete(note)
        db.session.commit()
        return jsonify({'error': 'This note has expired and been deleted.'}), 410

    code2 = request.headers.get('X-Code2') or request.args.get('code2', '')
    if note.is_password_protected and not _check_code2(note, code2):
        return jsonify({
            'error': '2nd code required',
            'protected': True,
            'id': note.id,
            'title': note.title,
        }), 401

    note.views += 1
    db.session.commit()
    result = note.to_dict(include_content=True)
    result['files'] = [f.to_dict() for f in note.files]
    return jsonify(result), 200


# ── Update Note ───────────────────────────────────────────────────────────────
@notes_bp.route('/notes/<note_id>', methods=['PUT'])
def update_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.is_expired():
        return jsonify({'error': 'This note has expired.'}), 410

    data = request.get_json(silent=True) or {}
    code2 = request.headers.get('X-Code2') or data.get('code2', '')

    if note.is_password_protected and not _check_code2(note, code2):
        return jsonify({'error': 'Invalid 2nd code'}), 401

    # Save current to history
    if note.content:
        history = NoteHistory(note_id=note.id, content=note.content, title=note.title)
        db.session.add(history)
        old = NoteHistory.query.filter_by(note_id=note.id)\
            .order_by(NoteHistory.saved_at.desc()).all()
        if len(old) > 20:
            for o in old[20:]:
                db.session.delete(o)

    if 'title'       in data: note.title       = data['title'][:200]
    if 'content'     in data: note.content      = data['content']
    if 'language'    in data: note.language     = data['language']
    if 'is_markdown' in data: note.is_markdown  = bool(data['is_markdown'])
    if 'expiry'      in data: note.expires_at   = calculate_expiry(data['expiry'])

    # Enable / update 2nd-code protection
    new_code2 = data.get('new_code2', '').strip()
    if new_code2:
        note.is_password_protected = True
        note.password_hash = bcrypt.hashpw(new_code2.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Remove 2nd-code protection
    if data.get('remove_code2'):
        note.is_password_protected = False
        note.password_hash = None

    note.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'success': True, 'note': note.to_dict()}), 200


# ── Delete Note ───────────────────────────────────────────────────────────────
@notes_bp.route('/notes/<note_id>', methods=['DELETE'])
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    data = request.get_json(silent=True) or {}
    code2 = request.headers.get('X-Code2') or data.get('code2', '')

    if note.is_password_protected and not _check_code2(note, code2):
        return jsonify({'error': 'Invalid 2nd code'}), 401

    import os
    for f in note.files:
        fpath = os.path.join(current_app.config['UPLOAD_FOLDER'], f.stored_name)
        if os.path.exists(fpath):
            os.remove(fpath)

    db.session.delete(note)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Note deleted'}), 200


# ── Note History ──────────────────────────────────────────────────────────────
@notes_bp.route('/notes/<note_id>/history', methods=['GET'])
def get_history(note_id):
    note = Note.query.get_or_404(note_id)
    code2 = request.headers.get('X-Code2') or request.args.get('code2', '')
    if note.is_password_protected and not _check_code2(note, code2):
        return jsonify({'error': '2nd code required'}), 401

    history = NoteHistory.query.filter_by(note_id=note_id)\
        .order_by(NoteHistory.saved_at.desc()).limit(20).all()
    return jsonify([h.to_dict() for h in history]), 200


# ── Restore History Version ───────────────────────────────────────────────────
@notes_bp.route('/notes/<note_id>/history/<int:history_id>/restore', methods=['POST'])
def restore_history(note_id, history_id):
    note = Note.query.get_or_404(note_id)
    h = NoteHistory.query.filter_by(id=history_id, note_id=note_id).first_or_404()

    data = request.get_json(silent=True) or {}
    code2 = request.headers.get('X-Code2') or data.get('code2', '')
    if note.is_password_protected and not _check_code2(note, code2):
        return jsonify({'error': '2nd code required'}), 401

    current_h = NoteHistory(note_id=note.id, content=note.content, title=note.title)
    db.session.add(current_h)
    note.content = h.content
    note.title = h.title
    note.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'success': True, 'note': note.to_dict()}), 200



