import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

DATABASE_PATH = "data/articles.db"
SNAPSHOT_STORE = None


def database_connection():
    if SNAPSHOT_STORE is not None:
        return SNAPSHOT_STORE.connection()
    from data.news_snapshot import readonly
    return closing(readonly(DATABASE_PATH))


def parse_publication_date(value):
    """Accept ISO and RFC RSS dates; interpret timezone-less values as UTC."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    try:
        try:
            date = datetime.fromisoformat(value)
        except ValueError:
            date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def get_story_groups():
    with database_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT sg.cluster_id, sg.representative_title, sg.article_count,
                   sg.source_count, GROUP_CONCAT(DISTINCT a.source_name) AS sources
            FROM story_groups sg
            LEFT JOIN articles a ON sg.cluster_id = a.cluster_id
            GROUP BY sg.cluster_id, sg.representative_title,
                     sg.article_count, sg.source_count
            ORDER BY sg.cluster_id
        """).fetchall()
        bounds = {}
        for article in connection.execute(
            'SELECT cluster_id, published_at FROM articles WHERE cluster_id IS NOT NULL'
        ):
            date = parse_publication_date(article['published_at'])
            if date is None:
                continue
            cluster_id = article['cluster_id']
            earliest, latest = bounds.get(cluster_id, (date, date))
            bounds[cluster_id] = (min(earliest, date), max(latest, date))

    stories = []
    for row in rows:
        story = dict(row)
        story['sources'] = story['sources'].split(',') if story['sources'] else []
        earliest, latest = bounds.get(story['cluster_id'], (None, None))
        # Canonical timezone-aware strings keep browser parsing consistent.
        story['first_published_at'] = earliest.isoformat() if earliest else None
        story['last_published_at'] = latest.isoformat() if latest else None
        stories.append(story)
    return stories


def get_story_articles(cluster_id):

    with database_connection() as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        cursor.execute("""
        SELECT
            a.id AS article_id,
            a.source_name AS source,
            a.title_ar AS headline,
            a.published_at AS date,
            a.url,

            CASE
                WHEN ao.article_id IS NOT NULL THEN 'article'
                WHEN sp.source_name IS NOT NULL THEN 'source'
                ELSE 'none'
            END AS orientation_level,

            COALESCE(
        ao.political_alignment,
        sp.political_alignment,
        'unclear'
        ) AS political_alignment,

           COALESCE(
            ao.ideological_tendency,
            sp.ideological_tendency,
            'unclear'
        ) AS ideological_tendency,

           COALESCE(
            ao.confidence,
            sp.confidence,
            'low'
        ) AS confidence
        FROM articles a

        LEFT JOIN article_orientation ao
            ON a.id = ao.article_id

        LEFT JOIN source_profiles sp
            ON a.source_name = sp.source_name

        WHERE a.cluster_id = ?

        ORDER BY a.published_at
        """, (cluster_id,))

        rows = cursor.fetchall()

    articles = [dict(row) for row in rows]
    articles.sort(key=lambda article: (
        parse_publication_date(article['date']) or datetime.max.replace(tzinfo=timezone.utc),
        article['article_id']
    ))
    return articles