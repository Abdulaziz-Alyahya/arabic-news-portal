import json
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from backend.snapshot_store import SnapshotStore
from data.news_snapshot import create_snapshot, digest, readonly, validate_database, validate_manifest

ROOT = Path(__file__).resolve().parents[1]


class Snapshots(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source.db'
        with closing(readonly(ROOT / 'data/articles.db')) as origin, closing(sqlite3.connect(self.source)) as target:
            origin.backup(target)
        self.snapshot = self.root / 'published.sqlite'
        self.manifest = self.root / 'manifest.json'
        self.value = create_snapshot(self.source, self.snapshot, self.manifest)
        self.store = SnapshotStore(self.source, self.root / 'cache')

    def fetch(self, name, limit, destination=None):
        payload = self.manifest.read_bytes() if name.endswith('.json') else self.snapshot.read_bytes()
        if destination:
            destination.write(payload)
            return len(payload)
        return payload

    def activate(self):
        with patch.object(self.store, '_fetch', side_effect=self.fetch):
            return self.store.refresh()

    def test_wal_backup_preserves_committed_data_without_source_writes(self):
        with closing(sqlite3.connect(self.source)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute("UPDATE story_groups SET representative_title='WAL committed' WHERE cluster_id=(SELECT min(cluster_id) FROM story_groups)")
            writer.commit()
            before = digest(self.source)
            create_snapshot(self.source, self.snapshot, self.manifest)
            self.assertEqual(before, digest(self.source))
            with closing(readonly(self.snapshot)) as reader:
                self.assertEqual(reader.execute('SELECT representative_title FROM story_groups ORDER BY cluster_id LIMIT 1').fetchone()[0], 'WAL committed')
                self.assertEqual(reader.execute('PRAGMA journal_mode').fetchone()[0], 'delete')

    def test_activation_unchanged_manifest_avoids_database_download(self):
        self.assertTrue(self.activate())
        with patch.object(self.store, '_fetch', side_effect=self.fetch) as fetch:
            self.assertFalse(self.store.refresh())
            self.assertEqual(fetch.call_count, 1)

    def test_failed_download_keeps_working_snapshot_and_recovers(self):
        self.activate()
        active = self.store.active
        self.store.version = 'older'
        with patch.object(self.store, '_fetch', side_effect=TimeoutError):
            self.assertFalse(self.store.refresh())
        self.assertEqual(active, self.store.active)
        self.assertEqual(self.store.next_delay, 120)
        self.assertTrue(self.activate())
        self.assertEqual(self.store.next_delay, 60)

    def test_checksum_mismatch_and_corrupt_database_rejected(self):
        for matching_checksum in (False, True):
            self.snapshot.write_bytes(b'not sqlite')
            if matching_checksum:
                checksum = digest(self.snapshot)
                self.manifest.write_text(json.dumps(dict(self.value, sha256=checksum, version=checksum, size_bytes=self.snapshot.stat().st_size)))
            self.assertFalse(self.activate())
            self.assertEqual(self.store.active, self.source)
        self.assertEqual(list(self.store.cache.iterdir()), [])

    def test_missing_table_and_incompatible_column_rejected(self):
        with closing(sqlite3.connect(self.snapshot)) as c:
            c.execute('DROP TABLE article_orientation')
            c.commit()
        with self.assertRaises(ValueError):
            validate_database(self.snapshot)
        create_snapshot(self.source, self.snapshot, self.manifest)
        with closing(sqlite3.connect(self.snapshot)) as c:
            c.execute('ALTER TABLE articles RENAME COLUMN title_ar TO incompatible')
            c.commit()
        with self.assertRaises(ValueError):
            validate_database(self.snapshot)

    def test_manifest_validation(self):
        for change in ({'schema_version': 2}, {'version': 'bad'}, {'size_bytes': 1000000000}, {'size_bytes': True}):
            with self.assertRaises(ValueError):
                validate_manifest(dict(self.value, **change))

    def test_active_reader_survives_activation_and_old_file_cleanup(self):
        self.activate()
        old = self.store.active
        with self.store.connection() as reader:
            before = reader.execute('SELECT count(*) FROM articles').fetchone()
            with closing(sqlite3.connect(self.source)) as writer:
                writer.execute("INSERT INTO articles(title_ar,url) VALUES('new','https://example.com/new')")
                writer.commit()
            create_snapshot(self.source, self.snapshot, self.manifest)
            self.assertTrue(self.activate())
            self.assertTrue(old.exists())
            self.assertEqual(reader.execute('SELECT count(*) FROM articles').fetchone(), before)
            with self.store.connection() as new_reader:
                self.assertEqual(new_reader.execute('SELECT count(*) FROM articles').fetchone()[0], before[0] + 1)
        self.assertFalse(old.exists())

    def test_restart_fallback_and_remote_recovery(self):
        self.activate()
        restarted = SnapshotStore(self.source, self.root / 'fresh-cache')
        self.assertEqual(restarted.active, self.source)
        with patch.object(restarted, '_fetch', side_effect=OSError):
            self.assertFalse(restarted.refresh())
        with restarted.connection() as reader:
            self.assertIsNotNone(reader.execute('SELECT count(*) FROM articles').fetchone())
        with patch.object(restarted, '_fetch', side_effect=self.fetch):
            self.assertTrue(restarted.refresh())

    def test_rollback_to_version_with_open_reader_keeps_active_file(self):
        self.activate()
        original_snapshot = self.snapshot.read_bytes()
        original_manifest = self.manifest.read_bytes()
        with self.store.connection():
            with closing(sqlite3.connect(self.source)) as writer:
                writer.execute("UPDATE story_groups SET representative_title='changed'")
                writer.commit()
            create_snapshot(self.source, self.snapshot, self.manifest)
            self.activate()
            self.snapshot.write_bytes(original_snapshot)
            self.manifest.write_bytes(original_manifest)
            self.assertTrue(self.activate())
            self.assertTrue(self.store.active.exists())
        self.assertTrue(self.store.active.exists())

    def test_api_contracts_unchanged_when_using_runtime_snapshot(self):
        from backend import story_service
        self.activate()
        with patch.object(story_service, 'DATABASE_PATH', str(self.source)):
            before_groups = story_service.get_story_groups()
            cluster_id = before_groups[0]['cluster_id']
            before_articles = story_service.get_story_articles(cluster_id)
            with patch.object(story_service, 'SNAPSHOT_STORE', self.store):
                self.assertEqual(before_groups, story_service.get_story_groups())
                self.assertEqual(before_articles, story_service.get_story_articles(cluster_id))

    def test_concurrent_refresh_does_not_overlap(self):
        self.store.refresh_lock.acquire()
        try:
            with patch.object(self.store, '_fetch') as fetch:
                self.assertFalse(self.store.refresh())
                fetch.assert_not_called()
        finally:
            self.store.refresh_lock.release()

    def test_http_fetch_size_bounds(self):
        import io
        with patch('backend.snapshot_store.urllib.request.urlopen', return_value=io.BytesIO(b'oversized')) as opened:
            with self.assertRaises(ValueError):
                self.store._fetch('news-manifest.json', 3)
            self.assertEqual(opened.call_args.kwargs['timeout'], 10)

    def test_publisher_stages_only_data_and_uses_render_skip(self):
        from scripts.publish_news import publish
        calls = []
        def fake_git(*args):
            calls.append(args)
            if args[0] == 'rev-parse':
                return 'same-blob'
            if args[:2] == ('diff', '--cached'):
                return '' if not any(c[0] == 'add' for c in calls) else 'data/articles.db'
            return ''
        with patch('scripts.publish_news.logical_digest', return_value='changed'), patch('scripts.publish_news.create_snapshot') as snapshot, patch('scripts.publish_news.git', side_effect=fake_git), patch('scripts.publish_news.subprocess.run') as push:
            push.return_value.returncode = 0
            publish('main', 'before')
        snapshot.assert_called_once()
        self.assertIn(('add', 'data/articles.db', 'data/news-snapshot.sqlite', 'data/news-manifest.json'), calls)
        self.assertIn(('commit', '-m', 'Update Arabic news data [skip render]'), calls)

    def test_read_connections_reject_writes(self):
        self.activate()
        with self.store.connection() as reader:
            with self.assertRaises(sqlite3.OperationalError):
                reader.execute('DELETE FROM articles')


if __name__ == '__main__':
    unittest.main()
