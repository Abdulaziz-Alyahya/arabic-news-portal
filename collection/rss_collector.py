import feedparser
import trafilatura
import sqlite3
import hashlib

from datetime import datetime, timezone

DATABASE_PATH = "data/articles.db"

SOURCES = [
    {
        "name": "Al Jazeera",
        "country": "Qatar",
        "rss_url": "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9"
    },
    {
        "name": "DW Arabic",
        "country": "Germany",
        "rss_url": "https://rss.dw.com/rdf/rss-ar-all"
    }
]

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()

saved_count = 0
duplicate_count = 0

for source in SOURCES:

    feed = feedparser.parse(source["rss_url"])

    for article in feed.entries[:50]:

        title = article.get("title", "")
        url = article.get("link", "")
        published = article.get("published", "")
        author = article.get("author", "")
        tags = article.get("tags", [])

        section = ""

        if tags:
            section = tags[0].get("term", "")

        body = ""

        if url:
            downloaded = trafilatura.fetch_url(url)

            if downloaded:
                extracted_text = trafilatura.extract(downloaded)

                if extracted_text:
                    body = extracted_text

        content_hash = ""

        if body:
            content_hash = hashlib.sha256(
                body.encode("utf-8")
            ).hexdigest()

        if content_hash:
            cursor.execute(
                "SELECT id FROM articles WHERE content_hash = ?",
                (content_hash,)
            )

            existing_article = cursor.fetchone()

            if existing_article:
                duplicate_count += 1
                continue

        collected_at = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
        INSERT OR IGNORE INTO articles (
            source_name,
            source_country,
            title_ar,
            body_ar,
            url,
            published_at,
            collected_at,
            author,
            section,
            language,
            content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source["name"],
            source["country"],
            title,
            body,
            url,
            published,
            collected_at,
            author,
            section,
            "ar",
            content_hash
        ))

        if cursor.rowcount == 1:
            saved_count += 1
        else:
            duplicate_count += 1

connection.commit()
connection.close()

print("Collection finished.")
print("New articles saved:", saved_count)
print("Duplicates skipped:", duplicate_count)