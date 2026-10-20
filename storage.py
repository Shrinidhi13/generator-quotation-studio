"""Quotation JSON backups and legacy local-file helpers (unused by the app)."""
import json
import os
from pathlib import Path
import re
import tempfile

from domain import validate_structure

DATA_DIR = Path(__file__).resolve().parent / 'data'


def _validate_id(quote_id):
    if not isinstance(quote_id, str) or not re.fullmatch(r'[a-f0-9-]{36}', quote_id):
        raise ValueError('Invalid quotation ID.')


def _path(quote_id):
    _validate_id(quote_id)
    return DATA_DIR / f'{quote_id}.json'


def export_quote(q):
    validate_structure(q)
    return json.dumps(q, indent=2, ensure_ascii=False, allow_nan=False).encode('utf-8')


def import_quote(content):
    if len(content) > 2_000_000:
        raise ValueError('Quotation backup must be smaller than 2 MB.')
    try:
        q = json.loads(content.decode('utf-8-sig'))
    except (ValueError, UnicodeError, AttributeError):
        raise ValueError('Choose a valid JSON quotation backup.') from None
    validate_structure(q)
    return q


def save_quote(q):
    content = export_quote(q)
    path = _path(q['id'])
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=DATA_DIR, suffix='.tmp', delete=False) as f:
            temp = Path(f.name)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp and temp.exists():
            temp.unlink()
    return path


def load_quote(quote_id):
    return import_quote(_path(quote_id).read_bytes())


def list_quotes():
    if not DATA_DIR.exists():
        return []
    result = []
    for path in sorted(DATA_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True):
        try:
            q = import_quote(path.read_bytes())
            if path.stem != q['id']:
                continue
            result.append(dict(id=q['id'], lead_ref=q['lead_ref'], quote_number=q['quote_number'],
                               revision=q['revision'], customer_name=q['customer']['name'], date=q['date']))
        except (OSError, ValueError):
            continue  # A damaged file never hides the remaining valid drafts.
    return result


