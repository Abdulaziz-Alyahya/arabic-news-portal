import sqlite3
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

DATABASE_PATH = "data/articles.db"

# Final similarity threshold from our manual testing
THRESHOLD = 0.865


# Load the multilingual E5 model
model = SentenceTransformer(
    "intfloat/multilingual-e5-base"
)


# Connect to the database
connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()


# Get article IDs and titles
cursor.execute("""
SELECT id, title_ar
FROM articles
WHERE title_ar IS NOT NULL
""")

articles = cursor.fetchall()


article_ids = []
titles = []
texts = []


# Prepare titles for the E5 model
for article_id, title in articles:

    article_ids.append(article_id)
    titles.append(title)

    texts.append("query: " + title)


# Generate normalized embeddings
embeddings = model.encode(
    texts,
    normalize_embeddings=True
)


# Calculate similarity
similarity_matrix = cosine_similarity(embeddings)


# Reset old cluster IDs before creating new clusters
cursor.execute("""
UPDATE articles
SET cluster_id = NULL
""")


# Keep track of which cluster each article belongs to
article_clusters = {}

next_cluster_id = 1


# Compare every article with every other article
for i in range(len(articles)):

    for j in range(i + 1, len(articles)):

        score = similarity_matrix[i][j]

        if score >= THRESHOLD:

            id1 = article_ids[i]
            id2 = article_ids[j]

            cluster1 = article_clusters.get(id1)
            cluster2 = article_clusters.get(id2)


            # Neither article has a cluster yet
            if cluster1 is None and cluster2 is None:

                article_clusters[id1] = next_cluster_id
                article_clusters[id2] = next_cluster_id

                next_cluster_id += 1


            # Article 1 already has a cluster
            elif cluster1 is not None and cluster2 is None:

                article_clusters[id2] = cluster1


            # Article 2 already has a cluster
            elif cluster1 is None and cluster2 is not None:

                article_clusters[id1] = cluster2


            # Both have different clusters -> merge them
            elif cluster1 != cluster2:

                old_cluster = cluster2
                new_cluster = cluster1

                for article_id in article_clusters:

                    if article_clusters[article_id] == old_cluster:
                        article_clusters[article_id] = new_cluster


# Save cluster IDs to the database
for article_id, cluster_id in article_clusters.items():

    cursor.execute("""
    UPDATE articles
    SET cluster_id = ?
    WHERE id = ?
    """, (
        cluster_id,
        article_id
    ))


connection.commit()


# Print the created clusters
cursor.execute("""
SELECT cluster_id, id, title_ar
FROM articles
WHERE cluster_id IS NOT NULL
ORDER BY cluster_id, id
""")

clustered_articles = cursor.fetchall()


current_cluster = None

for cluster_id, article_id, title in clustered_articles:

    if cluster_id != current_cluster:

        print("\n==============================")
        print("CLUSTER", cluster_id)
        print("==============================")

        current_cluster = cluster_id

    print("Article ID:", article_id)
    print(title)
    print()


connection.close()

print("Clustering completed successfully.")