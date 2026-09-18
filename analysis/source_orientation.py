import sqlite3

DATABASE_PATH = "data/articles.db"

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()

cursor.execute("""
SELECT
    articles.id,
    articles.source_name,
    articles.title_ar,
    source_profiles.political_alignment,
    source_profiles.ideological_tendency,
    source_profiles.confidence
FROM articles
LEFT JOIN source_profiles
ON articles.source_name = source_profiles.source_name
""")

articles = cursor.fetchall()

for article in articles:
    article_id = article[0]
    source_name = article[1]
    title = article[2]
    political_alignment = article[3]
    ideological_tendency = article[4]
    confidence = article[5]

    print("\n------------------------------")
    print("Article ID:", article_id)
    print("Source:", source_name)
    print("Title:", title)
    print("Political alignment:", political_alignment)
    print("Ideological tendency:", ideological_tendency)
    print("Confidence:", confidence)

connection.close()

print("\nSource-level orientation attached successfully.")