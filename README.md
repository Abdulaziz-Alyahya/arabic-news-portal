# Arabic News Comparison Portal

A prototype for collecting and comparing Arabic-language news articles from different news sources.

## Project Goal

The goal of this project is to help users understand how different Arabic news sources cover the same story.

The project focuses on two main analysis components:

1. Story similarity
2. Ideological orientation

## Project Structure

- `collection/` - Collect Arabic news articles from different sources
- `processing/` - Clean and preprocess Arabic text
- `analysis/` - Story similarity and ideological orientation analysis
- `web/` - Backend and web portal code
- `data/` - SQLite database and database setup files

## Week 1 - News Collection

During Week 1, the project setup and initial news collection pipeline were completed.

### News Sources

The current working Arabic news sources are:

- Al Jazeera
- DW Arabic

Both sources provide RSS feeds that can be read using `feedparser`.

### Collection Process

The collector:

1. Reads RSS feeds using `feedparser`
2. Extracts article metadata such as title, URL, publication date, author, and section
3. Downloads article pages
4. Extracts the Arabic article body using `trafilatura`
5. Stores the articles in SQLite

### Stored Article Fields

The database currently stores:

- id
- source_name
- source_country
- title_ar
- body_ar
- url
- published_at
- collected_at
- author
- section
- language
- content_hash

### Duplicate Detection

Two duplicate checks are used:

- Duplicate URL detection using a UNIQUE URL field
- Duplicate article content detection using SHA-256 content hashes

### Missing Fields

Missing fields such as author or section are stored as empty values instead of causing the collector to crash.

## Technologies

- Python
- feedparser
- trafilatura
- SQLite
- hashlib

## Run the Project

Activate the virtual environment:

```bash
source .venv/bin/activate