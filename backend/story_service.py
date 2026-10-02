import sqlite3

DATABASE_PATH = "data/articles.db"


def get_story_groups():

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("""
    SELECT
        sg.cluster_id,
        sg.representative_title,
        sg.article_count,
        sg.source_count,
        GROUP_CONCAT(DISTINCT a.source_name) AS sources,
        MIN(NULLIF(a.published_at, '')) AS first_published_at,
        MAX(NULLIF(a.published_at, '')) AS last_published_at

    FROM story_groups sg

    LEFT JOIN articles a
        ON sg.cluster_id = a.cluster_id

    GROUP BY
        sg.cluster_id,
        sg.representative_title,
        sg.article_count,
        sg.source_count

    ORDER BY sg.cluster_id
    """)

    rows = cursor.fetchall()
    connection.close()

    story_groups = []

    for row in rows:

        story = dict(row)

        if story["sources"]:
            story["sources"] = story["sources"].split(",")
        else:
            story["sources"] = []

        story_groups.append(story)

    return story_groups


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
    connection.close()

    return [dict(row) for row in rows]