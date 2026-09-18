import sqlite3

DATABASE_PATH = "data/articles.db"

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()

cursor.execute("""
SELECT
    a.id,
    a.source_name,
    a.title_ar,

    sp.political_alignment AS source_political_alignment,
    sp.ideological_tendency AS source_ideological_tendency,
    sp.confidence AS source_confidence,
    ao.political_alignment AS article_political_alignment,
    ao.ideological_tendency AS article_ideological_tendency,
    ao.confidence AS article_confidence,
    ao.short_reason

FROM articles a

JOIN article_orientation ao
    ON a.id = ao.article_id

LEFT JOIN source_profiles sp
    ON a.source_name = sp.source_name

ORDER BY a.id;
""")

results = cursor.fetchall()

for row in results:
    article_id = row[0]
    source_name = row[1]
    title = row[2]

    source_political = row[3]
    source_ideological = row[4]
    source_confidence = row[5]

    article_political = row[6]
    article_ideological = row[7]
    article_confidence = row[8]
    short_reason = row[9]

    print("\n==================================================")
    print("Article ID:", article_id)
    print("Source:", source_name)
    print("Title:", title)

    print("\nSOURCE-LEVEL")
    print("Political alignment:", source_political)
    print("Ideological tendency:", source_ideological)
    print("Confidence:", source_confidence)

    print("\nARTICLE-LEVEL")
    print("Political alignment:", article_political)
    print("Ideological tendency:", article_ideological)
    print("Confidence:", article_confidence)
    print("Reason:", short_reason)

print("\n==================================================")
print("Total compared articles:", len(results))

connection.close()