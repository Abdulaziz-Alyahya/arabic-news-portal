"""Logical change detection and a checkpoint for successful clustering."""
from contextlib import closing
import hashlib
import json
import sqlite3
from pathlib import Path

DATABASE_PATH = 'data/articles.db'


def title_fingerprint(connection):
    rows = connection.execute('SELECT id, title_ar FROM articles WHERE title_ar IS NOT NULL ORDER BY id').fetchall()
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


def needs_processing(database=DATABASE_PATH):
    with closing(sqlite3.connect(database)) as connection, connection:
        pending = connection.execute('SELECT 1 FROM articles WHERE processed_text IS NULL LIMIT 1').fetchone()
        if pending:
            return True
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE name='pipeline_state'").fetchone()
        if not exists:
            return bool(connection.execute('SELECT 1 FROM articles LIMIT 1').fetchone())
        row = connection.execute("SELECT value FROM pipeline_state WHERE key='clustered_titles'").fetchone()
        return not row or row[0] != title_fingerprint(connection)


def checkpoint(connection):
    connection.execute('CREATE TABLE IF NOT EXISTS pipeline_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    connection.execute("INSERT INTO pipeline_state VALUES ('clustered_titles', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value WHERE value != excluded.value", (title_fingerprint(connection),))


def logical_digest(database=DATABASE_PATH):
    """Ignore SQLite page layout and sequence counters; include the durable checkpoint."""
    if not Path(database).exists():
        return ''
    digest = hashlib.sha256()
    with closing(sqlite3.connect(f'file:{database}?mode=ro', uri=True)) as connection:
        for table in ('articles', 'story_groups', 'source_profiles', 'article_orientation', 'pipeline_state'):
            exists = connection.execute('SELECT 1 FROM sqlite_master WHERE name=?', (table,)).fetchone()
            if not exists:
                continue
            digest.update(table.encode())
            for row in connection.execute(f'SELECT * FROM {table} ORDER BY 1'):
                digest.update(json.dumps(row, ensure_ascii=False).encode())
    return digest.hexdigest()
