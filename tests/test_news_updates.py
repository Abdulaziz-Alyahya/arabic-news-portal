import contextlib
import hashlib
import io
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import requests
import yaml

import pipeline
from analysis.create_clusters import cluster
from collection.rss_collector import SOURCES, collect
from data.pipeline_state import checkpoint, logical_digest, needs_processing
from processing.prepare_text import prepare
from scripts.publish_news import publish

ROOT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def connect(*args, **kwargs):
    connection = sqlite3.connect(*args, **kwargs)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class Updates(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'articles.db'
        with connect(ROOT / 'data/articles.db') as source, connect(self.db) as target:
            for sql, in source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"):
                target.execute(sql)
        self.cache = Path(self.temp.name) / 'vectors.npz'

    def add(self, title, cluster_id=None, source='Al Jazeera'):
        with connect(self.db) as c:
            return c.execute('INSERT INTO articles(title_ar,body_ar,url,source_name,cluster_id) VALUES(?,?,?,?,?)',
                             (title, title + ' نص عربي', 'https://example.com/' + title, source, cluster_id)).lastrowid

    def test_cached_processing_stable_ids_and_orientation(self):
        a = self.add('A', 7)
        b = self.add('B', 9)
        self.add('C')  # Unmatched singleton must not force every later run to reprocess.
        with connect(self.db) as c:
            c.execute('INSERT INTO story_groups(cluster_id,representative_title,article_count,source_count) VALUES(7,"A",1,1),(9,"B",1,1)')
            c.execute('INSERT INTO source_profiles VALUES("DW Arabic","independent","unclear","medium","existing source profile")')
            c.execute('INSERT INTO article_orientation VALUES(?,"unclear","unclear","low","original")', (a,))
        encoded = []
        def encode(texts, **kwargs):
            encoded.extend(texts)
            return np.array([[1.,0.,0.] if t.endswith(('A','D')) else [0.,1.,0.] if t.endswith('B') else [0.,0.,1.] for t in texts])
        factory = Mock(return_value=Mock(encode=encode))
        prepare(self.db)
        cluster(self.db, self.cache, factory)
        self.assertFalse(needs_processing(self.db))
        before = self.db.read_bytes()
        cluster(self.db, self.cache, factory)
        prepare(self.db)
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(factory.call_count, 1)
        new = self.add('D', source='DW Arabic')
        self.assertTrue(needs_processing(self.db))
        prepare(self.db)
        encoded.clear()
        cluster(self.db, self.cache, factory)
        self.assertEqual(encoded, ['query: D'])
        with connect(self.db) as c:
            assignments = dict(c.execute('SELECT id,cluster_id FROM articles'))
            self.assertEqual(assignments[a], 7)
            self.assertEqual(assignments[b], 9)
            self.assertEqual(assignments[new], 7)
            self.assertEqual(c.execute('SELECT article_count,source_count FROM story_groups WHERE cluster_id=7').fetchone(), (2,2))
            self.assertEqual(c.execute('SELECT short_reason FROM article_orientation').fetchone(), ('original',))
        self.assertFalse(needs_processing(self.db))
        from backend import story_service
        with patch.object(story_service, 'DATABASE_PATH', str(self.db)):
            rendered = next(article for article in story_service.get_story_articles(7) if article['article_id'] == new)
            self.assertEqual((rendered['orientation_level'], rendered['political_alignment'], rendered['confidence']), ('source','independent','medium'))

    def test_pending_pipeline_and_repeated_collection_stage(self):
        self.add('A')
        factory = Mock(return_value=Mock(encode=lambda texts, **kwargs:np.array([[1.,0.] for _ in texts])))
        with patch('sys.argv', ['pipeline.py','--process-only']), patch('pipeline.logical_digest', side_effect=lambda:logical_digest(self.db)), patch('pipeline.needs_processing', side_effect=lambda:needs_processing(self.db)), patch('processing.prepare_text.prepare', side_effect=lambda:prepare(self.db)) as prep, patch('analysis.create_clusters.cluster', side_effect=lambda:cluster(self.db,self.cache,factory)) as clustering:
            pipeline.main()
            prep.assert_called_once()
            clustering.assert_called_once()
        before = self.db.read_bytes()
        with patch('sys.argv', ['pipeline.py']), patch('pipeline.logical_digest', side_effect=lambda:logical_digest(self.db)), patch('pipeline.needs_processing', side_effect=lambda:needs_processing(self.db)), patch('pipeline.subprocess.run'), patch('collection.rss_collector.collect', return_value=0), patch('processing.prepare_text.prepare') as prep, patch('analysis.create_clusters.cluster') as clustering:
            pipeline.main()
            prep.assert_not_called()
            clustering.assert_not_called()
        self.assertEqual(before,self.db.read_bytes())

    def test_url_and_hash_duplicates_no_repeated_page_requests(self):
        source = SOURCES[0]
        urls = ['https://www.aljazeera.net/a', 'https://www.aljazeera.net/b']
        session = Mock(headers={})
        response = Mock(status_code=200, content=b'feed', text='User-agent: *\nAllow: /', url=urls[0])
        session.get.return_value = response
        feed = Mock(entries=[{'link':u,'title':'عنوان'} for u in urls], bozo=False)
        with patch('collection.rss_collector.SOURCES', [source]), patch('collection.rss_collector.feedparser.parse', return_value=feed), patch('collection.rss_collector.trafilatura.extract', return_value='محتوى متطابق'):
            self.assertEqual(collect(self.db, session, sleep=lambda _:None), 1)
            session.get.reset_mock()
            # The hash-duplicate URL remains unrecorded and is checked again; known URLs are never downloaded.
            self.assertEqual(collect(self.db, session, sleep=lambda _:None), 0)
            calls = [c.args[0] for c in session.get.call_args_list]
            self.assertNotIn(urls[0], calls)
            self.assertIn(urls[1], calls)
        with connect(self.db) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM articles').fetchone()[0], 1)

    def test_restrictions_preserve_rss_and_feed_failures_do_not_write(self):
        session = Mock(headers={})
        response = Mock(status_code=200, content=b'feed', text='User-agent: *\nDisallow: /')
        session.get.return_value = response
        feed = Mock(entries=[{'link':'https://www.aljazeera.net/a'}], bozo=False)
        before = self.db.read_bytes()
        with patch('collection.rss_collector.SOURCES', [SOURCES[0]]), patch('collection.rss_collector.feedparser.parse', return_value=feed):
            self.assertEqual(collect(self.db, session, sleep=lambda _:None), 1)
        self.assertNotIn('https://www.aljazeera.net/a', [c.args[0] for c in session.get.call_args_list])
        with connect(self.db) as c:
            self.assertEqual(c.execute('SELECT body_ar FROM articles').fetchone(), ('',))
        before = self.db.read_bytes()
        session.get.side_effect = requests.HTTPError('429')
        self.assertEqual(collect(self.db, session), 0)
        self.assertEqual(before, self.db.read_bytes())

    def test_no_work_pipeline_and_logical_digest(self):
        self.add('A')
        prepare(self.db)
        with connect(self.db) as c: checkpoint(c)
        before = self.db.read_bytes()
        with patch('sys.argv', ['pipeline.py','--process-only']), patch('pipeline.logical_digest', side_effect=lambda:logical_digest(self.db)), patch('pipeline.needs_processing', side_effect=lambda:needs_processing(self.db)), patch('processing.prepare_text.prepare') as prep, patch('analysis.create_clusters.cluster') as clustering:
            pipeline.main()
            prep.assert_not_called()
            clustering.assert_not_called()
        self.assertEqual(before, self.db.read_bytes())
        digest = logical_digest(self.db)
        with connect(self.db) as c: c.execute('VACUUM')
        self.assertEqual(digest, logical_digest(self.db))
        self.add('B')
        self.assertNotEqual(digest, logical_digest(self.db))

    def test_workflow_and_cron(self):
        # BaseLoader treats GitHub's `on` key as a string rather than YAML 1.1 boolean.
        workflow = yaml.load((ROOT/'.github/workflows/update_news.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(workflow['on']['schedule'][0]['cron'], '2-59/5 * * * *')
        minutes = list(range(2,60,5))
        self.assertEqual(len(minutes),12)
        self.assertTrue(all((minutes[(i+1)%12]-minutes[i])%60==5 for i in range(12)))
        self.assertIn('workflow_dispatch', workflow['on'])
        self.assertEqual(workflow['concurrency']['cancel-in-progress'], 'false')
        self.assertIn('default_branch', workflow['jobs']['update-news']['if'])
        self.assertNotIn('--force', (ROOT/'scripts/publish_news.py').read_text())

    def test_no_commit_on_unchanged_and_conflicting_remote_database(self):
        with patch('scripts.publish_news.logical_digest', return_value='same'), patch('scripts.publish_news.git') as git:
            publish('main','same')
            git.assert_not_called()
        with patch('scripts.publish_news.logical_digest', return_value='new'), patch('scripts.publish_news.git', side_effect=['old','', 'different']) as git:
            with self.assertRaisesRegex(RuntimeError,'Remote database changed'):
                publish('main','old')
            self.assertFalse(any(c.args[0] in ('commit','push') for c in git.call_args_list))


if __name__ == '__main__':
    unittest.main()
