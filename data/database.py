import sqlite3

DATABASE_PATH = "data/articles.db"

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT,
    source_country TEXT,
    title_ar TEXT,
    body_ar TEXT,
    url TEXT UNIQUE,
    published_at TEXT,
    collected_at TEXT,
    author TEXT,
    section TEXT,
    language TEXT,
    content_hash TEXT,
    processed_text TEXT,
    cluster_id INTEGER
)
""")

connection.commit()
connection.close()

print("Database and articles table created successfully.")