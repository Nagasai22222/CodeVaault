import random
import string
from datetime import datetime, timezone, timedelta


def generate_slug(length=8):
    """Generate a random alphanumeric slug for note IDs."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def calculate_expiry(option: str):
    """Return a UTC datetime based on expiry option string."""
    mapping = {
        '1h': timedelta(hours=1),
        '1d': timedelta(days=1),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
    }
    delta = mapping.get(option)
    if delta is None:
        return None
    return datetime.now(timezone.utc) + delta


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if a file's extension is in the allowed set."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def format_datetime(dt: datetime) -> str:
    """Return a friendly datetime string."""
    if dt is None:
        return 'Never'
    now = datetime.now(timezone.utc)
    dt_aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    diff = now - dt_aware
    if diff.total_seconds() < 60:
        return 'just now'
    elif diff.total_seconds() < 3600:
        mins = int(diff.total_seconds() / 60)
        return f'{mins} minute{"s" if mins != 1 else ""} ago'
    elif diff.total_seconds() < 86400:
        hrs = int(diff.total_seconds() / 3600)
        return f'{hrs} hour{"s" if hrs != 1 else ""} ago'
    return dt_aware.strftime('%b %d, %Y at %H:%M UTC')
