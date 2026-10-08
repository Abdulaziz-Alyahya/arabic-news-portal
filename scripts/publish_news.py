"""Actions-only publication: logical changes, safe rebases, never force-push."""
import argparse
import subprocess
import time
from pathlib import Path

from data.pipeline_state import logical_digest
from data.news_snapshot import create_snapshot


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def publish(branch, before):
    if logical_digest() == before:
        print('No meaningful database changes; no commit or deployment.')
        return
    # Compare remote database to the version on which this pipeline started.
    base_blob = git('rev-parse', 'HEAD:data/articles.db')
    git('fetch', 'origin', branch)
    if git('rev-parse', f'origin/{branch}:data/articles.db') != base_blob:
        raise RuntimeError('Remote database changed during collection; leaving it untouched. Retry the workflow.')
    # The pipeline subprocess has exited; backup captures all committed WAL pages.
    create_snapshot('data/articles.db', 'data/news-snapshot.sqlite', 'data/news-manifest.json')
    if git('diff', '--cached', '--name-only'):
        raise RuntimeError('Unexpected staged changes; refusing a data-only publication.')
    git('config', 'user.name', 'github-actions[bot]')
    git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    git('add', 'data/articles.db', 'data/news-snapshot.sqlite', 'data/news-manifest.json')
    if not git('diff', '--cached', '--name-only'):
        return
    git('commit', '-m', 'Update Arabic news data [skip render]')
    for attempt in range(3):
        git('fetch', 'origin', branch)
        if git('rev-parse', f'origin/{branch}:data/articles.db') != base_blob:
            raise RuntimeError('Remote database changed; refusing a binary merge or overwrite. Retry the workflow.')
        try:
            git('rebase', f'origin/{branch}')
        except subprocess.CalledProcessError:
            git('rebase', '--abort')
            raise
        result = subprocess.run(['git', 'push', 'origin', f'HEAD:refs/heads/{branch}'])
        if result.returncode == 0:
            return
        time.sleep(attempt + 1)
    raise RuntimeError('Push rejected after three attempts; no force-push was attempted.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--branch', required=True)
    parser.add_argument('--before-file', required=True)
    args = parser.parse_args()
    publish(args.branch, Path(args.before_file).read_text().strip())
