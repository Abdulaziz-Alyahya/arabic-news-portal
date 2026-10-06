# Arabic News Comparison Portal

A prototype for collecting, grouping, and comparing Arabic-language news articles from different news sources.

The portal helps users see how different Arabic news outlets cover the same story in one Arabic right-to-left interface.

## Project Goal

The main workflow of the project is:

Arabic news sources → collect articles → preprocess Arabic text → group similar stories → attach ideological orientation → display the results in an Arabic comparison portal.

The project focuses on two main analysis components:

1. Story similarity
2. Ideological orientation

---

## Current News Sources

The current working Arabic news sources are:

- Al Jazeera
- DW Arabic

Articles are collected from RSS feeds and the full article text is extracted from the original article page.

---

## Project Structure

- `collection/` - Collect Arabic news articles from RSS feeds
- `processing/` - Clean and prepare Arabic text
- `analysis/` - Story similarity, clustering, orientation, and validation
- `backend/` - FastAPI backend and story services
- `web/` - HTML, CSS, and JavaScript frontend
- `data/` - SQLite database and database setup files
- `pipeline.py` - Runs the main backend processing pipeline

---

## Article Collection

The collector:

1. Reads Arabic RSS feeds using `feedparser`
2. Extracts metadata such as title, URL, publication date, author, and section
3. Downloads the original article page
4. Extracts the full Arabic article text using `trafilatura`
5. Generates a SHA-256 hash for duplicate detection
6. Stores the article in SQLite

---

## Article Data Structure

The main article data includes:

- `id`
- `source_name`
- `source_country`
- `title_ar`
- `body_ar`
- `url`
- `published_at`
- `collected_at`
- `author`
- `section`
- `language`
- `content_hash`
- `processed_text`
- `cluster_id`

The original Arabic title and article body are preserved separately from the processed text.

---

## Duplicate Handling

The project uses two duplicate checks:

1. URL duplicate detection using a UNIQUE URL field
2. Article content duplicate detection using SHA-256 hashes

This prevents the same article from being stored multiple times.

---

## Arabic Text Preprocessing

Arabic text is prepared in:

`processing/prepare_text.py`

The preprocessing step:

- normalizes whitespace;
- removes unnecessary repeated title text from the beginning of the article body;
- combines the title and article text into a processed version;
- preserves the original Arabic text in the database.

The processed version is used for later analysis.

---

## Story Similarity and Grouping

Story similarity is implemented using multilingual sentence embeddings.

The model used is:

`intfloat/multilingual-e5-base`

The system creates embeddings from Arabic article titles and compares them using cosine similarity.

The current similarity threshold is:

`0.865`

This threshold was selected after manual testing on real Arabic news examples.

Articles with sufficient similarity are grouped into story clusters.

The clustering system stores:

- `cluster_id`
- representative title
- number of articles
- number of represented sources

Cluster IDs are kept stable when the pipeline is run again.

---

## Ideological Orientation

The project supports two levels of ideological information.

### Source-level orientation

Each supported source can have a profile containing:

- `political_alignment`
- `ideological_tendency`
- `confidence`
- explanatory note

### Article-level orientation

A small experiment was also completed on 20 Arabic articles using ChatGPT as the language model.

A structured prompt was used to estimate:

- political alignment;
- ideological tendency;
- confidence;
- short reason.

This initial experiment was completed manually without an API.

Orientation labels are estimates and should not be treated as objective facts.

When the available evidence is insufficient, the portal displays:

`غير واضح`

rather than hiding the uncertainty.

---

## Backend

The backend is implemented using FastAPI.

Main endpoints:

- `GET /stories`
  - returns the available story groups

- `GET /stories/{cluster_id}`
  - returns the articles inside a selected story group

The backend also serves the frontend files so that the portal and API can run from the same application.

---

## Frontend

The frontend is built using:

- HTML
- CSS
- JavaScript

The portal supports Arabic right-to-left layout.

### Home page

The home page displays:

- representative story headline;
- number of articles;
- number of sources;
- represented sources;
- publication information.

### Story comparison page

The comparison page displays:

- news source;
- Arabic headline;
- publication date;
- political alignment;
- ideological tendency;
- confidence;
- link to the original article.

The layout is responsive and adapts to desktop and mobile screens.

---

## Installation

Python 3.13 is recommended.

Clone the repository:

```bash
git clone https://github.com/Abdulaziz-Alyahya/arabic-news-portal.git