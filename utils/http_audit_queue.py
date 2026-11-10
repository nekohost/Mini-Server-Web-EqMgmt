"""Retry required HTTP audit writes across queue saturation and process restarts."""
import json
import os
import sqlite3
from contextlib import closing

from utils.equipment_audit_migration import private_directory


EXACT_PATHS = ('/assistant', '/admin/ai/providers')
PREFIXES = ('/api/ai/', '/internal/ai/', '/api/admin/ai/')


def protected_path(path):
    return path in EXACT_PATHS or path.startswith(PREFIXES)


def cleanup_filter():
    clauses = ['RequestPath != ?' for _ in EXACT_PATHS] + ['RequestPath NOT GLOB ?' for _ in PREFIXES]
    return ' AND '.join(clauses), (*EXACT_PATHS, *(prefix + '*' for prefix in PREFIXES))


def _open(path):
    private_directory(path.parent)
    if path.is_symlink():
        raise ValueError('invalid audit spool path')
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    os.close(descriptor)
    os.chmod(path, 0o600)
    db = sqlite3.connect(path, timeout=5)
    try:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('CREATE TABLE IF NOT EXISTS pending(id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
    except Exception:
        db.close()
        raise
    return db


def enqueue(path, event):
    with closing(_open(path)) as db, db:
        db.execute('INSERT INTO pending(body) VALUES(?)', (json.dumps(event, ensure_ascii=False),))


def drain(path, persist):
    """Keep the retry row until the destination commits. A crash after delivery can duplicate an event."""
    if not path.exists():
        return
    with closing(_open(path)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        # Limit memory per retry even if an individual audited response is very large.
        row = db.execute('SELECT id, body FROM pending ORDER BY id LIMIT 1').fetchone()
        if row:
            persist([json.loads(row[1])])
            db.execute('DELETE FROM pending WHERE id=?', (row[0],))
