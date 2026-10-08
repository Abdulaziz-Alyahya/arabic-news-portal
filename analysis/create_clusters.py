import sqlite3
from contextlib import closing
from pathlib import Path
import hashlib
import numpy as np
import sys
import zipfile
import zlib
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.pipeline_state import checkpoint, needs_processing

DATABASE_PATH = "data/articles.db"
THRESHOLD = 0.865
MODEL_DIMENSION = 768
MODEL_REVISION = "d128750597153bb5987e10b1c3493a34e5a4502a"
CACHE_VERSION = "e5-base-query-v1-" + MODEL_REVISION

def cached_embeddings(texts, cache_path, model_factory=None):
    """Reuse exact title vectors; still compare every pair in the original order."""
    keys = [hashlib.sha256(text.encode()).hexdigest() for text in texts]
    cached = {}
    if cache_path.exists():
        try:
            with cache_path.open('rb') as file:
                with np.load(file, allow_pickle=False) as saved:
                    if not isinstance(saved, np.lib.npyio.NpzFile):
                        raise ValueError('Expected an NPZ embedding cache')
                    version, saved_keys, vectors = saved['version'], saved['keys'], saved['vectors']
                    if version.shape != () or str(version) != CACHE_VERSION:
                        raise ValueError('Incompatible embedding cache version')
                    if saved_keys.ndim != 1 or saved_keys.dtype.kind != 'U':
                        raise ValueError('Invalid embedding cache keys')
                    key_list = saved_keys.tolist()
                    if any(len(key) != 64 or any(c not in '0123456789abcdef' for c in key) for key in key_list):
                        raise ValueError('Invalid title hashes')
                    if vectors.ndim != 2 or len(vectors) != len(key_list) or not vectors.shape[1]:
                        raise ValueError('Invalid embedding cache dimensions')
                    if model_factory is None and vectors.shape[1] != MODEL_DIMENSION:
                        raise ValueError('Wrong vector dimension for multilingual-e5-base')
                    if not np.issubdtype(vectors.dtype, np.floating) or not np.isfinite(vectors).all():
                        raise ValueError('Invalid embedding cache values')
                    if not np.allclose(np.linalg.norm(vectors, axis=1), 1, rtol=1e-3, atol=1e-3):
                        raise ValueError('Expected normalized embeddings')
                    cached = dict(zip(key_list, vectors))
        except (EOFError, ValueError, TypeError, OSError, KeyError, zipfile.BadZipFile, zlib.error) as error:
            print(f'Embedding cache discarded in memory: {type(error).__name__}; regenerating.')
            cached = {}
            # Replace only this cache atomically after successful regeneration.
            # Other cache/model files are never deleted.
    missing = list(dict.fromkeys(key for key in keys if key not in cached))
    if missing:
        if model_factory is None:
            from sentence_transformers import SentenceTransformer
            model_factory = lambda: SentenceTransformer('intfloat/multilingual-e5-base', revision=MODEL_REVISION)
        by_key = dict(zip(keys, texts))
        vectors = model_factory().encode([by_key[key] for key in missing], normalize_embeddings=True)
        cached.update(zip(missing, vectors))
    result = np.stack([cached[key] for key in keys])
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp = cache_path.with_suffix('.tmp.npz')
    np.savez(temp, version=CACHE_VERSION, keys=np.array(keys), vectors=result)
    temp.replace(cache_path)
    return result

def cluster(database=DATABASE_PATH, cache_path=Path('.cache/news-embeddings/titles.npz'), model_factory=None):
    if not needs_processing(database):
        print('Clustering already current; skipping.')
        return
    from sklearn.metrics.pairwise import cosine_similarity

    # Connect to database
    with closing(sqlite3.connect(database)) as connection, connection:
        cursor = connection.cursor()

        # Get all articles
        cursor.execute("""
        SELECT id, title_ar, source_name, cluster_id
        FROM articles
        WHERE title_ar IS NOT NULL
        ORDER BY id
        """)

        articles = cursor.fetchall()

        article_ids = []
        texts = []
        existing_clusters = {}

        for article_id, title, source_name, cluster_id in articles:

            article_ids.append(article_id)
            texts.append("query: " + title)

            # Keep existing cluster IDs
            if cluster_id is not None:
                existing_clusters[article_id] = cluster_id

        # Generate embeddings
        embeddings = cached_embeddings(texts, cache_path, model_factory) if texts else np.empty((0, 0))

        # Calculate similarity
        similarity_matrix = cosine_similarity(embeddings) if texts else []

        # Start with the existing cluster assignments
        article_clusters = existing_clusters.copy()

        # Find the highest existing cluster ID
        cursor.execute("""
        SELECT COALESCE(MAX(cluster_id), 0)
        FROM story_groups
        """)

        max_cluster_id = cursor.fetchone()[0]
        next_cluster_id = max_cluster_id + 1

        # Compare articles
        for i in range(len(articles)):

            for j in range(i + 1, len(articles)):

                score = similarity_matrix[i][j]

                if score < THRESHOLD:
                    continue

                id1 = article_ids[i]
                id2 = article_ids[j]

                cluster1 = article_clusters.get(id1)
                cluster2 = article_clusters.get(id2)

                # Neither article has a cluster
                if cluster1 is None and cluster2 is None:

                    article_clusters[id1] = next_cluster_id
                    article_clusters[id2] = next_cluster_id

                    next_cluster_id += 1

                # Article 1 already belongs to a cluster
                elif cluster1 is not None and cluster2 is None:

                    article_clusters[id2] = cluster1

                # Article 2 already belongs to a cluster
                elif cluster1 is None and cluster2 is not None:

                    article_clusters[id1] = cluster2

                # Both already have clusters.
                # Keep existing cluster IDs stable instead of renumbering them.
                elif cluster1 != cluster2:

                    continue

        # Save cluster assignments
        for article_id, cluster_id in article_clusters.items():

            cursor.execute("""
            UPDATE articles
            SET cluster_id = ?
            WHERE id = ? AND (cluster_id IS NULL OR cluster_id != ?)
            """, (
                cluster_id,
                article_id,
                cluster_id
            ))

        # Create/update story group information
        cluster_ids = sorted(set(article_clusters.values()))

        for cluster_id in cluster_ids:

            cursor.execute("""
            SELECT
                id,
                title_ar,
                source_name
            FROM articles
            WHERE cluster_id = ?
            ORDER BY id
            """, (cluster_id,))

            cluster_articles = cursor.fetchall()

            if not cluster_articles:
                continue

            # Use the first article headline as the representative title
            representative_title = cluster_articles[0][1]

            article_count = len(cluster_articles)

            source_count = len(
                set(article[2] for article in cluster_articles)
            )

            cursor.execute("""
            INSERT INTO story_groups (
                cluster_id,
                representative_title,
                article_count,
                source_count
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(cluster_id) DO UPDATE SET
                representative_title = excluded.representative_title,
                article_count = excluded.article_count,
                source_count = excluded.source_count
            WHERE representative_title != excluded.representative_title
               OR article_count != excluded.article_count
               OR source_count != excluded.source_count
            """, (
                cluster_id,
                representative_title,
                article_count,
                source_count
            ))

        checkpoint(connection)

    print(f'Clustering complete: {len(articles)} articles, {len(cluster_ids)} story groups.')

if __name__ == '__main__':
    cluster()
