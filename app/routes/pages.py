from flask import Blueprint, render_template, abort, make_response
from app.models import Note
from app import db

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    return render_template('index.html')


@pages_bp.route('/googleb06055eade7239f1.html')
def google_verification():
    return "google-site-verification: googleb06055eade7239f1.html"


@pages_bp.route('/robots.txt')
def robots():
    response = make_response("User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: https://codevault-m7er.onrender.com/sitemap.xml")
    response.headers["Content-Type"] = "text/plain"
    return response


@pages_bp.route('/sitemap.xml')
def sitemap():
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://codevault-m7er.onrender.com/</loc>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>
</urlset>"""
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response


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
