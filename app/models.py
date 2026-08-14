from datetime import datetime, timezone
from app import db
import json


class Note(db.Model):
    __tablename__ = 'notes'

    id = db.Column(db.String(10), primary_key=True)
    title = db.Column(db.String(200), default='Untitled Note')
    content = db.Column(db.Text, default='')
    is_password_protected = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=True)
    views = db.Column(db.Integer, default=0)
    language = db.Column(db.String(50), default='plaintext')
    is_markdown = db.Column(db.Boolean, default=False)

    # Relationships
    files = db.relationship('FileAttachment', backref='note', lazy=True, cascade='all, delete-orphan')
    history = db.relationship('NoteHistory', backref='note', lazy=True, cascade='all, delete-orphan',
                               order_by='NoteHistory.saved_at.desc()')

    def is_expired(self):
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at.replace(tzinfo=timezone.utc)

    def to_dict(self, include_content=True):
        data = {
            'id': self.id,
            'title': self.title,
            'is_password_protected': self.is_password_protected,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'views': self.views,
            'language': self.language,
            'is_markdown': self.is_markdown,
            'file_count': len(self.files),
        }
        if include_content:
            data['content'] = self.content
        return data


class NoteHistory(db.Model):
    __tablename__ = 'note_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    note_id = db.Column(db.String(10), db.ForeignKey('notes.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.Text, default='')
    title = db.Column(db.String(200), default='')
    saved_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'saved_at': self.saved_at.isoformat() if self.saved_at else None,
            'content_preview': self.content[:200] + ('...' if len(self.content) > 200 else ''),
        }


class FileAttachment(db.Model):
    __tablename__ = 'file_attachments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    note_id = db.Column(db.String(10), db.ForeignKey('notes.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    stored_name = db.Column(db.String(300), nullable=False)
    file_size = db.Column(db.Integer, default=0)
    mime_type = db.Column(db.String(100), default='application/octet-stream')
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'note_id': self.note_id,
            'filename': self.filename,
            'file_size': self.file_size,
            'file_size_human': self._human_size(self.file_size),
            'mime_type': self.mime_type,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'is_image': self.mime_type.startswith('image/') if self.mime_type else False,
        }

    @staticmethod
    def _human_size(size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024**2):.1f} MB"
        return f"{size_bytes / (1024**3):.1f} GB"
