from contextlib import closing
import re
import sqlite3

DATABASE_PATH = 'data/articles.db'


def prepare(database=DATABASE_PATH):
    with closing(sqlite3.connect(database)) as connection, connection:
        articles = connection.execute('SELECT id, title_ar, body_ar FROM articles WHERE processed_text IS NULL').fetchall()
        for article_id, title, body in articles:
            title = re.sub(r'\s+', ' ', title or '').strip()
            body = re.sub(r'\s+', ' ', body or '').strip()
            while title and body.startswith(title):
                body = body[len(title):].strip()
            connection.execute('UPDATE articles SET processed_text=? WHERE id=?', ((title + ' ' + body).strip(), article_id))
    print(f'Arabic text prepared: {len(articles)} articles')
    return len(articles)


if __name__ == '__main__':
    prepare()
