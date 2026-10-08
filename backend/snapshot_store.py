"""GitHub is authoritative; local files are disposable validated read caches."""
import json
import logging
import os
import tempfile
import threading
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from data.news_snapshot import digest, readonly, validate_database, validate_manifest

logger = logging.getLogger(__name__)
DEFAULT_BASE = 'https://raw.githubusercontent.com/Abdulaziz-Alyahya/arabic-news-portal/main/data/'


class SnapshotStore:
    def __init__(self, bundled, cache_dir=None, base_url=DEFAULT_BASE):
        self.bundled = Path(bundled).resolve()
        self.cache = Path(cache_dir or tempfile.mkdtemp(prefix='news-snapshots-'))
        self.cache.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url
        self.active = self.bundled
        self.version = None
        self.lock = threading.Lock()
        self.refresh_lock = threading.Lock()
        self.readers = {}
        self.retired = set()
        self.failures = 0

    @contextmanager
    def connection(self):
        with self.lock:
            path = self.active
            connection = readonly(path, immutable=path != self.bundled)
            self.readers[path] = self.readers.get(path, 0) + 1
        try:
            yield connection
        finally:
            connection.close()
            with self.lock:
                self.readers[path] -= 1
                self._cleanup()

    def _cleanup(self):
        for path in list(self.retired):
            if not self.readers.get(path):
                path.unlink(missing_ok=True)
                self.retired.remove(path)
                self.readers.pop(path, None)

    def _fetch(self, name, limit, destination=None):
        request = urllib.request.Request(self.base_url + name, headers={'Cache-Control': 'no-cache', 'User-Agent': 'ArabicNewsPortal/1.0'})
        deadline = time.monotonic() + 20
        with urllib.request.urlopen(request, timeout=10) as response:
            data = bytearray() if destination is None else None
            total = 0
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError('Snapshot transfer deadline exceeded')
                chunk = response.read(min(65536, limit + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise ValueError('Snapshot response exceeds size limit')
                if destination is None:
                    data.extend(chunk)
                else:
                    destination.write(chunk)
            return bytes(data) if data is not None else total

    def refresh(self):
        if not self.refresh_lock.acquire(blocking=False):
            return False
        try:
            # Two bounded attempts. A mismatched branch snapshot is never activated.
            for attempt in range(2):
                temporary = None
                try:
                    manifest = validate_manifest(json.loads(self._fetch('news-manifest.json', 4096)))
                    if manifest['version'] == self.version:
                        self.failures = 0
                        return False
                    fd, temporary = tempfile.mkstemp(dir=self.cache, suffix='.download')
                    with os.fdopen(fd, 'wb') as output:
                        size = self._fetch('news-snapshot.sqlite', manifest['size_bytes'], output)
                    if size != manifest['size_bytes'] or digest(temporary) != manifest['sha256']:
                        raise ValueError('Snapshot checksum/size mismatch')
                    validate_database(temporary)
                    target = self.cache / (manifest['version'] + '.sqlite')
                    os.replace(temporary, target)
                    temporary = None
                    with self.lock:
                        previous = self.active
                        self.active, self.version = target, manifest['version']
                        self.retired.discard(target)
                        if previous != self.bundled and previous != target:
                            self.retired.add(previous)
                        self._cleanup()
                    self.failures = 0
                    return True
                except Exception as error:
                    logger.warning('News snapshot refresh failed (%s); keeping working data', type(error).__name__)
                finally:
                    if temporary:
                        Path(temporary).unlink(missing_ok=True)
            self.failures += 1
            return False
        finally:
            self.refresh_lock.release()

    @property
    def next_delay(self):
        return min(600, 60 * 2 ** min(self.failures, 4))
