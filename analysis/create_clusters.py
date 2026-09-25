import sqlite3
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

DATABASE_PATH = "data/articles.db"
THRESHOLD = 0.865


# Load embedding model
model = SentenceTransformer("intfloat/multilingual-e5-base")


# Connect to database
connection = sqlite3.connect(DATABASE_PATH)
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
titles = []
texts = []
existing_clusters = {}


for article_id, title, source_name, cluster_id in articles:

    article_ids.append(article_id)
    titles.append(title)
    texts.append("query: " + title)

    # Keep existing cluster IDs
    if cluster_id is not None:
        existing_clusters[article_id] = cluster_id


# Generate embeddings
embeddings = model.encode(
    texts,
    normalize_embeddings=True
)


# Calculate similarity
similarity_matrix = cosine_similarity(embeddings)


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
    WHERE id = ?
    """, (
        cluster_id,
        article_id
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
    """, (
        cluster_id,
        representative_title,
        article_count,
        source_count
    ))


connection.commit()


# Print story groups
cursor.execute("""
SELECT
    cluster_id,
    representative_title,
    article_count,
    source_count
FROM story_groups
ORDER BY cluster_id
""")

story_groups = cursor.fetchall()


print("\nSTORY GROUPS")
print("========================================")

for cluster_id, title, article_count, source_count in story_groups:

    print("\nCluster ID:", cluster_id)
    print("Title:", title)
    print("Articles:", article_count)
    print("Sources:", source_count)


connection.close()

print("\nClustering completed successfully.")