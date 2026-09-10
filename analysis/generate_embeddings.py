import sqlite3
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

DATABASE_PATH = "data/articles.db"

# Similarity threshold
THRESHOLD = 0.85


# Load the multilingual E5 model
model = SentenceTransformer(
    "intfloat/multilingual-e5-base"
)


# Connect to the database
connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()


# Get article IDs and Arabic titles
cursor.execute("""
SELECT id, title_ar
FROM articles
WHERE title_ar IS NOT NULL
""")

articles = cursor.fetchall()


# Lists for article information
article_ids = []
titles = []
texts = []


# Prepare article titles for the E5 model
for article_id, title in articles:

    article_ids.append(article_id)
    titles.append(title)

    # E5 works better when a task prefix is added
    texts.append("query: " + title)


# Generate embeddings
embeddings = model.encode(
    texts,
    normalize_embeddings=True
)


# Calculate cosine similarity
similarity_matrix = cosine_similarity(embeddings)


# Store all article pairs and their similarity scores
similar_pairs = []


for i in range(len(articles)):

    for j in range(i + 1, len(articles)):

        score = similarity_matrix[i][j]

        similar_pairs.append((
            float(score),
            article_ids[i],
            titles[i],
            article_ids[j],
            titles[j]
        ))


# Sort results from highest similarity to lowest
similar_pairs.sort(
    reverse=True,
    key=lambda x: x[0]
)


# Print only article pairs above the threshold
result_count = 0

for score, id1, title1, id2, title2 in similar_pairs:

    if score >= THRESHOLD:

        result_count += 1

        print("\n------------------------------")

        print("Article 1 ID:", id1)
        print(title1)

        print()

        print("Article 2 ID:", id2)
        print(title2)

        print()

        print("Similarity:", round(score, 3))


# Close database connection
connection.close()

# Final summary
print("\n==============================")
print("Similarity analysis completed.")
print("Threshold:", THRESHOLD)
print("Matching pairs:", result_count)