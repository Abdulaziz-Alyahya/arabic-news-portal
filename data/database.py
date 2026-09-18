import sqlite3

DATABASE_PATH = "data/articles.db"

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()


# Articles table
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


# Source ideological profiles table
cursor.execute("""
CREATE TABLE IF NOT EXISTS source_profiles (
    source_name TEXT PRIMARY KEY,
    political_alignment TEXT,
    ideological_tendency TEXT,
    confidence TEXT,
    short_note TEXT
)
""")

# Article-level ideological orientation table
cursor.execute("""
CREATE TABLE IF NOT EXISTS article_orientation (
    article_id INTEGER PRIMARY KEY,
    political_alignment TEXT,
    ideological_tendency TEXT,
    confidence TEXT,
    short_reason TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
)
""")



connection.commit()
connection.close()

print("Database tables created successfully.")