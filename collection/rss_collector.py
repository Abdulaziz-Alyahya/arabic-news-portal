"""Collect RSS articles without requesting already stored URLs."""
from contextlib import closing
import hashlib
import json
import math
import os
import sqlite3
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import requests
import trafilatura

DATABASE_PATH = 'data/articles.db'
USER_AGENT = 'ArabicNewsComparison/1.0 (+https://github.com/Abdulaziz-Alyahya/arabic-news-portal)'
SOURCES = [
    {'name': 'Al Jazeera', 'country': 'Qatar', 'rss_url': 'https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9', 'hosts': {'www.aljazeera.net', 'aljazeera.net'}},
    {'name': 'DW Arabic', 'country': 'Germany', 'rss_url': 'https://rss.dw.com/rdf/rss-ar-all', 'hosts': {'www.dw.com', 'dw.com'}},
]


COOLDOWN_PATH = Path('.cache/news-collection/cooldowns.json')
DEFAULT_COOLDOWN_SECONDS = 300


def retry_deadline(value, now):
    """Retry-After accepts integer seconds or an HTTP date; UTC survives fresh runners."""
    try:
        value = str(value).strip()
        if value.isascii() and value.isdigit():
            deadline = now + max(1, int(value))
        else:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            deadline = max(now + 1, date.timestamp())
        if math.isfinite(deadline):
            return deadline
    except (TypeError, ValueError, OverflowError):
        pass
    return now + DEFAULT_COOLDOWN_SECONDS


class SourceCooldowns:
    """Private, disposable state: never modify the published news database for backoff."""
    def __init__(self, path, now):
        self.path, self.now = Path(path), now
        try:
            loaded = json.loads(self.path.read_text())
            if not isinstance(loaded, dict):
                raise ValueError('Cooldown state must be an object')
            self.original = {
                name: float(until) for name, until in loaded.items()
                if isinstance(name, str) and isinstance(until, (int, float))
                and not isinstance(until, bool) and math.isfinite(until)
            }
        except FileNotFoundError:
            self.original = {}
        except (ValueError, TypeError, OverflowError, OSError):
            print('Cooldown cache unavailable or invalid; using in-run backoff.')
            self.original = {}
        self.deadlines = {name: until for name, until in self.original.items() if until > now()}

    def active(self, name):
        return self.deadlines.get(name, 0) > self.now()

    def rate_limited(self, name, response):
        if response.status_code != 429:
            return
        until = retry_deadline(response.headers.get('Retry-After'), self.now())
        self.deadlines[name] = max(self.deadlines.get(name, 0), until)
        print(f'{name}: rate limited; stopping source requests during cooldown.')

    def save(self):
        changed = self.deadlines != self.original
        if changed:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps(self.deadlines, sort_keys=True))
            temp.replace(self.path)
        if os.environ.get('GITHUB_OUTPUT'):
            with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
                output.write(f'cooldown_changed={str(changed).lower()}\n')
        return changed


def collect(database=DATABASE_PATH, session=None, sleep=time.sleep, cooldown_path=None, now=time.time):
    owns_session = session is None
    session = session or requests.Session()
    cooldowns = SourceCooldowns(cooldown_path or COOLDOWN_PATH, now)
    session.headers.update({'User-Agent': USER_AGENT})
    saved = duplicates = 0
    robots = {}
    last_request = {}

    def allowed(url, source_name):
        if cooldowns.active(source_name):
            return False
        parsed = urlparse(url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        if origin not in robots:
            try:
                response = session.get(origin + '/robots.txt', timeout=(10, 20))
                cooldowns.rate_limited(source_name, response)
                if response.status_code == 404:
                    robots[origin] = None
                else:
                    response.raise_for_status()
                    parser = RobotFileParser()
                    parser.parse(response.text.splitlines())
                    robots[origin] = parser
            except requests.RequestException:
                # Do not bypass restrictions if the site's policy cannot be read.
                robots[origin] = False
        policy = robots[origin]
        if cooldowns.active(source_name) or policy is False or (policy and not policy.can_fetch(USER_AGENT, url)):
            return False
        delay = max(1, (policy.crawl_delay(USER_AGENT) or 0) if policy else 0)
        sleep(max(0, delay - (time.monotonic() - last_request.get(origin, 0))))
        last_request[origin] = time.monotonic()
        return True

    try:
        with closing(sqlite3.connect(database)) as connection, connection:
            for source in SOURCES:
                saved_before, duplicates_before, restricted = saved, duplicates, 0
                if cooldowns.active(source['name']):
                    print(f"{source['name']}: cooldown active; skipping source requests.")
                    continue
                try:
                    response = session.get(source['rss_url'], timeout=(10, 30))
                    cooldowns.rate_limited(source['name'], response)
                    response.raise_for_status()
                    feed = feedparser.parse(response.content)
                    if feed.bozo and not feed.entries:
                        raise ValueError('Invalid or empty RSS response')
                except (requests.RequestException, ValueError) as error:
                    print(f"RSS unavailable for {source['name']}: {error}")
                    continue
                for article in feed.entries[:50]:
                    url = article.get('link', '')
                    parsed = urlparse(url)
                    if parsed.scheme not in ('http', 'https') or parsed.hostname not in source['hosts']:
                        continue
                    if connection.execute('SELECT 1 FROM articles WHERE url=?', (url,)).fetchone():
                        duplicates += 1
                        continue
                    body = ''
                    if allowed(url, source['name']):
                        try:
                            response = session.get(url, timeout=(10, 30))
                            cooldowns.rate_limited(source['name'], response)
                            response.raise_for_status()
                            if urlparse(response.url).hostname in source['hosts']:
                                body = trafilatura.extract(response.text) or ''
                        except requests.RequestException as error:
                            print(f"Extraction unavailable; retaining RSS metadata: {error}")
                    else:
                        # The existing pipeline can store RSS articles without a body.
                        # Never request a prohibited page; grouping still uses its RSS title.
                        restricted += 1
                    content_hash = hashlib.sha256(body.encode()).hexdigest() if body else ''
                    if content_hash and connection.execute('SELECT 1 FROM articles WHERE content_hash=?', (content_hash,)).fetchone():
                        duplicates += 1
                        continue
                    tags = article.get('tags', [])
                    cursor = connection.execute('''INSERT OR IGNORE INTO articles
                        (source_name, source_country, title_ar, body_ar, url, published_at,
                         collected_at, author, section, language, content_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                        source['name'], source['country'], article.get('title', ''), body, url,
                        article.get('published', ''), datetime.now(timezone.utc).isoformat(),
                        article.get('author', ''), tags[0].get('term', '') if tags else '', 'ar', content_hash))
                    saved += cursor.rowcount
                    duplicates += 1 - cursor.rowcount
                print(f"{source['name']}: saved {saved - saved_before}, duplicates {duplicates - duplicates_before}, policy skips {restricted}")
    finally:
        try:
            cooldowns.save()
        finally:
            if owns_session:
                session.close()
    print(f'Collection finished. New articles: {saved}; duplicates skipped: {duplicates}')
    return saved


if __name__ == '__main__':
    collect()
