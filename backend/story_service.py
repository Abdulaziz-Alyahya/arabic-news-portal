import sqlite3

DATABASE_PATH = "data/articles.db"


def get_story_groups():

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("""
    SELECT
        cluster_id,
        representative_title,
        article_count,
        source_count
    FROM story_groups
    ORDER BY cluster_id
    """)

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


def get_story_articles(cluster_id):

    connection = sqlite3.connect(DATABASE_PATH)
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
        ) AS ideological_tendency

    FROM articles a

    LEFT JOIN article_orientation ao
        ON a.id = ao.article_id

    LEFT JOIN source_profiles sp
        ON a.source_name = sp.source_name

    WHERE a.cluster_id = ?

    ORDER BY a.published_at
    """, (cluster_id,))

    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]