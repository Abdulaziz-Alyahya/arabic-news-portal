import sqlite3
import re

DATABASE_PATH = "data/articles.db"

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()

cursor.execute("""
SELECT id, title_ar, body_ar
FROM articles
""")

articles = cursor.fetchall()

for article_id, title, body in articles:

    title = title or ""
    body = body or ""

    # Normalize spaces
    clean_title = re.sub(r"\s+", " ", title).strip()
    clean_body = re.sub(r"\s+", " ", body).strip()

    # Remove repeated title from the beginning of the article body
    while clean_title and clean_body.startswith(clean_title):
        clean_body = clean_body[len(clean_title):].strip()

    # Keep the title once, followed by the article body
    processed_text = clean_title + " " + clean_body
    processed_text = processed_text.strip()

    cursor.execute("""
    UPDATE articles
    SET processed_text = ?
    WHERE id = ?
    """, (
        processed_text,
        article_id
    ))

connection.commit()
connection.close()

print("Arabic text preparation completed successfully.")