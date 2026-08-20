import os
import uuid
import mimetypes
import boto3
from flask import Blueprint, request, jsonify, send_from_directory, current_app, redirect
from werkzeug.utils import secure_filename
from app import db
from app.models import Note, FileAttachment
from app.utils import allowed_file

files_bp = Blueprint('files', __name__)

def get_s3_client():
    if not current_app.config.get('S3_BUCKET'):
        return None
    from botocore.client import Config
    return boto3.client(
        's3',
        endpoint_url=current_app.config.get('S3_ENDPOINT_URL'),
        aws_access_key_id=current_app.config.get('S3_ACCESS_KEY'),
        aws_secret_access_key=current_app.config.get('S3_SECRET_KEY'),
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )

def _check_password(note, provided_password):
    import bcrypt
    if not note.is_password_protected:
        return True
    if not provided_password:
        return False
    return bcrypt.checkpw(provided_password.encode('utf-8'), note.password_hash.encode('utf-8'))


# ── Upload File to Note ───────────────────────────────────────────────────────
@files_bp.route('/notes/<note_id>/files', methods=['POST'])
def upload_file(note_id):
    note = Note.query.get_or_404(note_id)
    if note.is_expired():
        return jsonify({'error': 'Note has expired'}), 410

    password = request.headers.get('X-Note-Password') or request.form.get('password', '')
    if note.is_password_protected and not _check_password(note, password):
        return jsonify({'error': 'Invalid password'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    allowed_exts = current_app.config['ALLOWED_EXTENSIONS']
    if not allowed_file(file.filename, allowed_exts):
        return jsonify({'error': f'File type not allowed. Allowed: {", ".join(sorted(allowed_exts))}'}), 400

    # Limit per note: 10 files max
    if len(note.files) >= 10:
        return jsonify({'error': 'Maximum 10 files per note'}), 400

    original_name = secure_filename(file.filename)
    ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else ''
    stored_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    mime_type, _ = mimetypes.guess_type(original_name)
    mime_type = mime_type or 'application/octet-stream'

    s3_client = get_s3_client()
    bucket_name = current_app.config.get('S3_BUCKET')

    if s3_client and bucket_name:
        s3_client.upload_fileobj(
            file,
            bucket_name,
            stored_name,
            ExtraArgs={'ContentType': mime_type}
        )
    else:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        save_path = os.path.join(upload_folder, stored_name)
        file.save(save_path)

    attachment = FileAttachment(
        note_id=note.id,
        filename=original_name,
        stored_name=stored_name,
        file_size=file_size,
        mime_type=mime_type,
    )
    db.session.add(attachment)
    db.session.commit()

    return jsonify({'success': True, 'file': attachment.to_dict()}), 201


# ── List Files for Note ───────────────────────────────────────────────────────
@files_bp.route('/notes/<note_id>/files', methods=['GET'])
def list_files(note_id):
    note = Note.query.get_or_404(note_id)
    password = request.headers.get('X-Note-Password') or request.args.get('password', '')
    if note.is_password_protected and not _check_password(note, password):
        return jsonify({'error': 'Password required'}), 401

    return jsonify([f.to_dict() for f in note.files]), 200


# ── Download File ─────────────────────────────────────────────────────────────
@files_bp.route('/files/<int:file_id>/download', methods=['GET'])
def download_file(file_id):
    attachment = FileAttachment.query.get_or_404(file_id)
    note = Note.query.get_or_404(attachment.note_id)

    password = request.headers.get('X-Note-Password') or request.args.get('password', '')
    if note.is_password_protected and not _check_password(note, password):
        return jsonify({'error': 'Password required'}), 401

    s3_client = get_s3_client()
    bucket_name = current_app.config.get('S3_BUCKET')

    if s3_client and bucket_name:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': attachment.stored_name,
                'ResponseContentDisposition': f'attachment; filename="{attachment.filename}"'
            },
            ExpiresIn=3600
        )
        return redirect(url)
    else:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        return send_from_directory(
            upload_folder,
            attachment.stored_name,
            as_attachment=True,
            download_name=attachment.filename,
        )


# ── Preview File (inline for images) ─────────────────────────────────────────
@files_bp.route('/files/<int:file_id>/preview', methods=['GET'])
def preview_file(file_id):
    attachment = FileAttachment.query.get_or_404(file_id)
    note = Note.query.get_or_404(attachment.note_id)

    password = request.headers.get('X-Note-Password') or request.args.get('password', '')
    if note.is_password_protected and not _check_password(note, password):
        return jsonify({'error': 'Password required'}), 401

    s3_client = get_s3_client()
    bucket_name = current_app.config.get('S3_BUCKET')

    if s3_client and bucket_name:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': attachment.stored_name,
                'ResponseContentDisposition': 'inline'
            },
            ExpiresIn=3600
        )
        return redirect(url)
    else:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        return send_from_directory(
            upload_folder,
            attachment.stored_name,
            as_attachment=False,
        )


# ── Delete File ───────────────────────────────────────────────────────────────
@files_bp.route('/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    attachment = FileAttachment.query.get_or_404(file_id)
    note = Note.query.get_or_404(attachment.note_id)

    data = request.get_json(silent=True) or {}
    password = request.headers.get('X-Note-Password') or data.get('password', '')
    if note.is_password_protected and not _check_password(note, password):
        return jsonify({'error': 'Invalid password'}), 401

    s3_client = get_s3_client()
    bucket_name = current_app.config.get('S3_BUCKET')

    if s3_client and bucket_name:
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=attachment.stored_name)
        except Exception as e:
            print(f"Error deleting from S3: {e}")
    else:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        fpath = os.path.join(upload_folder, attachment.stored_name)
        if os.path.exists(fpath):
            os.remove(fpath)

    db.session.delete(attachment)
    db.session.commit()
    return jsonify({'success': True, 'message': 'File deleted'}), 200
