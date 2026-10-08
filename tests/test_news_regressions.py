"""Fixtures for publication bounds, cross-run backoff, and disposable vector caches."""
import hashlib
import json
import sqlite3
import tempfile
import types
import unittest
from contextlib import closing
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import requests
import yaml

from analysis.create_clusters import CACHE_VERSION, cached_embeddings, cluster
from backend import story_service
from collection.rss_collector import SOURCES, collect, retry_deadline
from data.pipeline_state import needs_processing
from processing.prepare_text import prepare

ROOT = Path(__file__).resolve().parents[1]


class RegressionFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = self.folder / 'articles.db'
        self.cooldowns = self.folder / 'cooldowns.json'
        with closing(sqlite3.connect(f'file:{ROOT / "data/articles.db"}?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(self.db)) as target, target:
                for sql, in source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'"):
                    target.execute(sql)

    def add(self, title, date=None, group=7):
        with closing(sqlite3.connect(self.db)) as connection, connection:
            article_id = connection.execute('''INSERT INTO articles
                (title_ar, body_ar, url, published_at, cluster_id, source_name)
                VALUES (?, ?, ?, ?, ?, 'DW Arabic')''',
                (title, title + ' محتوى', 'https://www.dw.com/ar/' + title, date, group)).lastrowid
            if group is not None:
                connection.execute('INSERT OR IGNORE INTO story_groups(cluster_id,representative_title) VALUES (?,?)', (group,title))
        return article_id


class PublicationDates(RegressionFixtures):
    def test_actual_september_october_regressions(self):
        cases = [
            (7, 'Wed, 09 Sep 2026 21:01:54 +0300', 'Tue, 06 Oct 2026 15:32:47 +0300', '2026-10-06T12:32:47+00:00'),
            (9, 'Wed, 23 Sep 2026 15:15:27 +0300', 'Tue, 06 Oct 2026 17:04:45 +0300', '2026-10-06T14:04:45+00:00'),
        ]
        for group, old, new, expected in cases:
            self.add(f'old-{group}',old,group)
            self.add(f'new-{group}',new,group)
        before = self.db.read_bytes()
        with patch.object(story_service,'DATABASE_PATH',str(self.db)):
            stories = {story['cluster_id']:story for story in story_service.get_story_groups()}
        for group, old, new, expected in cases:
            with self.subTest(group=group):
                self.assertEqual(stories[group]['last_published_at'],expected)
                self.assertEqual(stories[group]['first_published_at'],story_service.parse_publication_date(old).isoformat())
        self.assertEqual(before,self.db.read_bytes())

    def test_mixed_formats_timezone_offsets_and_invalid_values(self):
        for i,value in enumerate(['2026-10-01T00:30:00+03:00','Wed, 30 Sep 2026 23:00:00 GMT','2026-09-30T22:00:00Z','2026-09-30 21:00:00',None,'','malformed','2026-02-30T00:00:00Z']):
            self.add(str(i),value)
        with patch.object(story_service,'DATABASE_PATH',str(self.db)):
            story = story_service.get_story_groups()[0]
        self.assertEqual(story['first_published_at'],'2026-09-30T21:00:00+00:00')
        self.assertEqual(story['last_published_at'],'2026-09-30T23:00:00+00:00')
        self.assertEqual(set(story),{'cluster_id','representative_title','article_count','source_count','sources','first_published_at','last_published_at'})
        self.assertIsNone(story_service.parse_publication_date(123))
        self.assertIsNone(story_service.parse_publication_date('9999-12-31T23:59:59-12:00'))

    def test_missing_dates_and_chronological_comparison_order(self):
        late = self.add('late','Tue, 06 Oct 2026 17:04:45 +0300')
        early = self.add('early','Wed, 23 Sep 2026 15:15:27 +0300')
        invalid = self.add('bad','invalid')
        self.add('only-invalid','invalid',9)
        with patch.object(story_service,'DATABASE_PATH',str(self.db)):
            stories = {story['cluster_id']:story for story in story_service.get_story_groups()}
            articles = story_service.get_story_articles(7)
        self.assertIsNone(stories[9]['first_published_at'])
        self.assertIsNone(stories[9]['last_published_at'])
        self.assertEqual([a['article_id'] for a in articles],[early,late,invalid])
        self.assertEqual(articles[1]['date'],'Tue, 06 Oct 2026 17:04:45 +0300')


class RateLimits(RegressionFixtures):
    def mock_sources(self, limited='article', header='3600'):
        self.clock = [1791500000.0]
        self.calls = []
        self.feeds = {source['name']:Mock(bozo=False,entries=[
            {'title':source['name']+str(i),'link':f'https://{sorted(source["hosts"])[0]}/ar/{i}'}
            for i in range(2 if index==0 else 1)
        ]) for index,source in enumerate(SOURCES)}
        def get(url,**kwargs):
            self.calls.append(url)
            response = requests.Response()
            response.url=url;response.status_code=200
            response._content=b'User-agent: *\nAllow: /' if url.endswith('/robots.txt') else url.encode()
            if url==SOURCES[0]['rss_url'] and limited=='feed':
                response.status_code=429
            elif 'aljazeera.net' in url and url.endswith('/robots.txt') and limited=='robots':
                response.status_code=429
            elif 'aljazeera.net/ar/0' in url and limited=='article':
                response.status_code=429
            if response.status_code==429 and header is not None:
                response.headers['Retry-After']=header
            return response
        self.session=Mock(headers={},get=get)
        def parse(content):
            name=next(source['name'] for source in SOURCES if source['rss_url']==content.decode())
            return self.feeds[name]
        self.parser=patch('collection.rss_collector.feedparser.parse',side_effect=parse)
        self.extractor=patch('collection.rss_collector.trafilatura.extract',side_effect=lambda text:text)
        self.parser.start();self.extractor.start()
        self.addCleanup(self.parser.stop);self.addCleanup(self.extractor.stop)

    def run_collect(self):
        return collect(self.db,self.session,sleep=lambda _:None,cooldown_path=self.cooldowns,now=lambda:self.clock[0])

    def test_numeric_backoff_stops_pages_and_survives_fresh_run(self):
        self.mock_sources()
        self.assertEqual(self.run_collect(),3)
        self.assertIn(self.feeds['Al Jazeera'].entries[0]['link'],self.calls)
        self.assertNotIn(self.feeds['Al Jazeera'].entries[1]['link'],self.calls)
        self.assertIn(self.feeds['DW Arabic'].entries[0]['link'],self.calls)
        self.assertEqual(json.loads(self.cooldowns.read_text())['Al Jazeera'],self.clock[0]+3600)
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("SELECT body_ar FROM articles WHERE source_name='Al Jazeera'").fetchall(),[('',),('',)])
        before=self.db.read_bytes()
        self.calls.clear()
        # Every collect() constructs a fresh cooldown object, like the next runner.
        self.assertEqual(self.run_collect(),0)
        self.assertEqual(self.calls,[SOURCES[1]['rss_url']])
        self.assertEqual(before,self.db.read_bytes())
        self.clock[0]+=3601
        self.feeds['Al Jazeera'].entries.append({'title':'after cooldown','link':'https://aljazeera.net/ar/3'})
        self.calls.clear()
        self.assertEqual(self.run_collect(),1)
        self.assertIn('https://aljazeera.net/ar/3',self.calls)
        self.assertEqual(json.loads(self.cooldowns.read_text()),{})

    def test_http_date_backoff(self):
        now=1791500000.0
        header=format_datetime(datetime.fromtimestamp(now+1800,timezone.utc),usegmt=True)
        self.mock_sources(header=header)
        self.assertEqual(self.run_collect(),3)
        self.assertEqual(json.loads(self.cooldowns.read_text())['Al Jazeera'],now+1800)
        self.calls.clear();self.clock[0]+=300
        self.run_collect()
        self.assertEqual(self.calls,[SOURCES[1]['rss_url']])

    def test_feed_rate_limit_does_not_block_other_source(self):
        self.mock_sources(limited='feed')
        self.assertEqual(self.run_collect(),1)
        self.assertFalse(any('aljazeera.net/ar/' in url for url in self.calls))
        self.assertIn(self.feeds['DW Arabic'].entries[0]['link'],self.calls)
        self.calls.clear();self.run_collect()
        self.assertEqual(self.calls,[SOURCES[1]['rss_url']])

    def test_robots_rate_limit_preserves_rss_without_page_requests(self):
        self.mock_sources(limited='robots',header=None)
        self.assertEqual(self.run_collect(),3)
        self.assertFalse(any('aljazeera.net/ar/' in url for url in self.calls))
        self.assertEqual(json.loads(self.cooldowns.read_text())['Al Jazeera'],self.clock[0]+300)

    def test_retry_after_fallbacks_and_no_database_only_backoff_commit(self):
        now=1791500000.0
        for value in (None,'garbage','-1','1.5'):
            self.assertEqual(retry_deadline(value,now),now+300)
        self.assertEqual(retry_deadline('120',now),now+120)
        self.assertEqual(retry_deadline('0',now),now+1)
        self.mock_sources(limited='feed')
        with patch('collection.rss_collector.SOURCES',[SOURCES[0]]):
            before=self.db.read_bytes()
            self.assertEqual(self.run_collect(),0)
            self.assertEqual(before,self.db.read_bytes())
        self.assertTrue(self.cooldowns.exists())

    def test_workflow_restores_and_saves_only_changed_cooldown_state(self):
        self.mock_sources(limited='feed')
        output=self.folder/'outputs.txt'
        with patch.dict('os.environ',{'GITHUB_OUTPUT':str(output)}):
            self.run_collect()
            self.run_collect()
        self.assertEqual(output.read_text().splitlines(),['cooldown_changed=true','cooldown_changed=false'])
        workflow=yaml.load((ROOT/'.github/workflows/update_news.yml').read_text(),Loader=yaml.BaseLoader)
        steps=workflow['jobs']['update-news']['steps']
        restore=next(s for s in steps if s.get('uses')=='actions/cache/restore@v4')
        save=next(s for s in steps if s.get('uses')=='actions/cache/save@v4')
        self.assertEqual(restore['with']['path'],'.cache/news-collection')
        self.assertEqual(save['with']['path'],restore['with']['path'])
        self.assertIn("cooldown_changed == 'true'",save['if'])
        self.assertLess(steps.index(save),next(i for i,s in enumerate(steps) if s['name']=='Process pending articles'))


class CacheRecovery(RegressionFixtures):
    def factory(self):
        return Mock(return_value=Mock(encode=lambda texts,**kwargs:np.array([[1.,0.] for _ in texts])))

    def test_empty_and_corrupt_files_are_replaced_without_touching_neighbors(self):
        cache=self.folder/'titles.npz'
        neighbor=self.folder/'other-cache.bin'
        neighbor.write_bytes(b'untouched')
        for raw in (b'',b'not an embedding cache',b'PK\x03\x04truncated zip'):
            with self.subTest(raw=raw):
                cache.write_bytes(raw)
                factory=self.factory()
                result=cached_embeddings(['query: A'],cache,factory)
                np.testing.assert_array_equal(result,[[1.,0.]])
                factory.assert_called_once()
                with np.load(cache,allow_pickle=False) as saved:
                    self.assertEqual(str(saved['version']),CACHE_VERSION)
                self.assertEqual(neighbor.read_bytes(),b'untouched')

    def test_invalid_shapes_values_missing_fields_and_npy_formats(self):
        cache=self.folder/'titles.npz'
        key=hashlib.sha256(b'query: A').hexdigest()
        cases=[
            {'version':CACHE_VERSION,'keys':np.array([key]),'vectors':np.array([[np.nan,0.]])},
            {'version':CACHE_VERSION,'keys':np.array([key]),'vectors':np.array([[0.,0.]])},
            {'version':CACHE_VERSION,'keys':np.array([key]),'vectors':np.array([1.,0.])},
            {'version':CACHE_VERSION,'keys':np.array([key]),'vectors':np.empty((0,2))},
            {'version':'incompatible','keys':np.array([key]),'vectors':np.array([[1.,0.]])},
            {'version':CACHE_VERSION},
        ]
        for fields in cases:
            with self.subTest(fields=list(fields)):
                np.savez(cache,**fields)
                cached_embeddings(['query: A'],cache,self.factory())
                with np.load(cache,allow_pickle=False) as saved:
                    np.testing.assert_array_equal(saved['vectors'],[[1.,0.]])
        with cache.open('wb') as file:np.save(file,np.array([1.,0.]))
        np.testing.assert_array_equal(cached_embeddings(['query: A'],cache,self.factory()),[[1.,0.]])

    def test_wrong_model_dimension_recovers_with_the_production_model_path(self):
        cache=self.folder/'titles.npz'
        key=hashlib.sha256(b'query: A').hexdigest()
        np.savez(cache,version=CACHE_VERSION,keys=np.array([key]),vectors=np.array([[1.,0.]]))
        expected=np.zeros((1,768));expected[0,0]=1
        factory=Mock(return_value=Mock(encode=Mock(return_value=expected)))
        fake_module=types.ModuleType('sentence_transformers')
        fake_module.SentenceTransformer=factory
        with patch.dict('sys.modules',{'sentence_transformers':fake_module}):
            result=cached_embeddings(['query: A'],cache)
        np.testing.assert_array_equal(result,expected)
        factory.assert_called_once()

    def test_valid_vectors_reused_and_failed_regeneration_keeps_old_file(self):
        cache=self.folder/'titles.npz'
        cached_embeddings(['query: A'],cache,self.factory())
        encode=Mock(return_value=np.array([[0.,1.]]))
        factory=Mock(return_value=Mock(encode=encode))
        result=cached_embeddings(['query: A','query: B'],cache,factory)
        encode.assert_called_once_with(['query: B'],normalize_embeddings=True)
        np.testing.assert_array_equal(result,[[1.,0.],[0.,1.]])
        cached_embeddings(['query: A','query: B'],cache,Mock(side_effect=AssertionError('Do not load model')))
        cache.write_bytes(b'broken')
        with self.assertRaisesRegex(RuntimeError,'model unavailable'):
            cached_embeddings(['query: A'],cache,Mock(side_effect=RuntimeError('model unavailable')))
        self.assertEqual(cache.read_bytes(),b'broken')

    def test_recovery_preserves_clusters_and_orientation_then_no_work(self):
        first=self.add('A',group=7)
        second=self.add('B',group=9)
        new=self.add('C',group=None)
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute('INSERT INTO article_orientation VALUES(?,"unclear","unclear","low","original")',(first,))
        cache=self.folder/'titles.npz';cache.write_bytes(b'')
        prepare(self.db)
        cluster(self.db,cache,self.factory())
        with closing(sqlite3.connect(self.db)) as connection:
            assignments=dict(connection.execute('SELECT id,cluster_id FROM articles'))
            self.assertEqual(assignments[first],7)
            self.assertEqual(assignments[second],9)
            self.assertEqual(assignments[new],7)
            self.assertEqual(connection.execute('SELECT short_reason FROM article_orientation').fetchone(),('original',))
            self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone(),('ok',))
        self.assertFalse(needs_processing(self.db))
        before=self.db.read_bytes()
        cluster(self.db,cache,Mock(side_effect=AssertionError('No model on idle run')))
        self.assertEqual(before,self.db.read_bytes())


if __name__=='__main__':
    unittest.main()
