"""Portable, self-contained SQLite snapshots; no third-party dependencies."""
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

SCHEMA_VERSION = 1
MAX_BYTES = 64 * 1024 * 1024
REQUIRED = {
    'articles': {'id': 'INTEGER', 'source_name': 'TEXT', 'title_ar': 'TEXT', 'url': 'TEXT', 'published_at': 'TEXT', 'cluster_id': 'INTEGER'},
    'story_groups': {'cluster_id': 'INTEGER', 'representative_title': 'TEXT', 'article_count': 'INTEGER', 'source_count': 'INTEGER'},
    'source_profiles': {'source_name': 'TEXT', 'political_alignment': 'TEXT', 'ideological_tendency': 'TEXT', 'confidence': 'TEXT'},
    'article_orientation': {'article_id': 'INTEGER', 'political_alignment': 'TEXT', 'ideological_tendency': 'TEXT', 'confidence': 'TEXT'},
}


def readonly(path, immutable=False):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro' + ('&immutable=1' if immutable else ''), uri=True)


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_manifest(value):
    if not isinstance(value, dict) or value.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Unsupported news manifest schema')
    checksum = value.get('sha256')
    if not isinstance(checksum, str) or not re.fullmatch('[0-9a-f]{64}', checksum) or value.get('version') != checksum:
        raise ValueError('Invalid snapshot version/checksum')
    size = value.get('size_bytes')
    if type(size) is not int or not 0 < size <= MAX_BYTES:
        raise ValueError('Invalid snapshot size')
    return value


def validate_database(path):
    # Published files must be standalone, never depend on a remote WAL/journal.
    with closing(readonly(path)) as connection:
        if connection.execute('PRAGMA journal_mode').fetchone()[0].lower() != 'delete':
            raise ValueError('Snapshot must use DELETE journal mode')
        if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity check failed')
        for table, required in REQUIRED.items():
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                raise ValueError('Missing table: ' + table)
            columns = {row[1]: row[2].upper() for row in connection.execute('PRAGMA table_info(' + table + ')')}
            if any(columns.get(name) != kind for name, kind in required.items()):
                raise ValueError('Incompatible schema: ' + table)
        if connection.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Foreign key check failed')


def create_snapshot(source, snapshot, manifest):
    """Backup includes committed WAL pages without checkpointing/modifying source."""
    snapshot, manifest = Path(snapshot), Path(manifest)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=snapshot.parent, suffix='.sqlite')
    os.close(fd)
    try:
        with closing(readonly(source)) as origin, closing(sqlite3.connect(temporary)) as target:
            origin.backup(target)
            target.execute('PRAGMA journal_mode=DELETE')
        validate_database(temporary)
        checksum = digest(temporary)
        value = {'schema_version': SCHEMA_VERSION, 'version': checksum, 'sha256': checksum, 'size_bytes': Path(temporary).stat().st_size}
        os.replace(temporary, snapshot)
        manifest.write_text(json.dumps(value, indent=2) + '\n')
        return value
    finally:
        Path(temporary).unlink(missing_ok=True)
