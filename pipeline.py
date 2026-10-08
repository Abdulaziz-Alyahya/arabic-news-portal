"""Collection is lightweight; ML imports and processing occur only when needed."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from data.pipeline_state import logical_digest, needs_processing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--process-only', action='store_true')
    args = parser.parse_args()
    if args.collect_only and args.process_only:
        parser.error('Choose one stage or neither')
    before = logical_digest()
    if not args.process_only:
        subprocess.run([sys.executable, 'data/database.py'], check=True)
        from collection.rss_collector import collect
        collect()
    pending = needs_processing()
    if pending and not args.collect_only:
        from processing.prepare_text import prepare
        from analysis.create_clusters import cluster
        prepare()
        cluster()
    elif not pending:
        print('No pending articles: skipping preprocessing, model loading, and clustering.')
    changed = before != logical_digest()
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
            output.write(f'pending={str(pending).lower()}\nchanged={str(changed).lower()}\n')
    print(f'Meaningful data changes: {changed}')


if __name__ == '__main__':
    main()
