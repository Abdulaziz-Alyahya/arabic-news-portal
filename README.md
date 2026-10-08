# Arabic News Comparison Portal | مقارنة الأخبار العربية

An internship prototype for comparing how Arabic news outlets cover the same story. The portal collects real news, groups related headlines, and presents source and experimental article-level orientation estimates in a readable Arabic right-to-left interface.

**Online demo:** [arabic-news-portal.onrender.com](https://arabic-news-portal.onrender.com)

**Repository:** [Abdulaziz-Alyahya/arabic-news-portal](https://github.com/Abdulaziz-Alyahya/arabic-news-portal)

The repository implements the features below. The demo URL alone does not confirm that its deployed version includes the latest changes; runtime snapshot delivery and Render settings require verification during rollout.

## Goal and workflow

Help readers compare coverage of a shared event without treating similarity or ideological estimates as verified facts.

```text
Arabic RSS feeds
  → article collection and duplicate detection
  → SQLite storage
  → Arabic text preparation
  → multilingual headline embeddings and cosine similarity
  → story grouping and metadata
  → existing article orientation or source-profile fallback
  → validated SQLite snapshot published to GitHub
  → FastAPI runtime snapshot refresh
  → Arabic comparison portal with browser polling
```

Text preparation stores a cleaned title/body combination, but the current clustering model uses **article headlines**, not that combined text. Orientation results are read from existing records; the automatic pipeline does not generate new ideological classifications.

## Supported sources

| Source | RSS feed |
| --- | --- |
| Al Jazeera | [Arabic RSS](https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9) |
| DW Arabic | [Arabic RSS](https://rss.dw.com/rdf/rss-ar-all) |

The collector uses `feedparser`, `requests`, and `trafilatura`. It considers up to 50 feed entries per source per run, stores available metadata, and extracts article bodies when access is permitted. It respects robots rules, crawl delays, host allowlists, and HTTP 429 cooldowns. When extraction is restricted or unavailable, RSS headlines, dates, and original links can still be retained; full text is not guaranteed.

Stored URLs are skipped before article-page requests. `url` has a SQLite UNIQUE constraint. Nonempty extracted bodies are hashed with SHA-256 and checked against existing content hashes before insertion. Empty bodies are not all treated as duplicate content; `content_hash` is not a database UNIQUE constraint. A content duplicate at a different URL can be requested again on a later run because that alternate URL is not stored.

## Project structure

```text
collection/rss_collector.py       RSS collection, access policies, duplicate checks
processing/prepare_text.py       Title/body text preparation
analysis/create_clusters.py      Cached embeddings, similarity, stable grouping
analysis/generate_embeddings.py  Standalone diagnostic similarity report
analysis/save_article_orientation.py  Saved manual experiment, tied to specific IDs
analysis/*validation.md          Earlier manual analysis and validation
analysis/week6_evaluation.md     Week 6 qualitative evaluation
backend/api.py                  FastAPI routes and refresh lifecycle
backend/story_service.py        Story queries, parsed dates, orientation fallback
backend/snapshot_store.py       Validated runtime snapshot downloads and activation
web/index.html, web/story.html   Home and comparison pages
web/style.css                   Shared responsive RTL design and theme variables
web/app.js, web/story.js         Dynamic story/article rendering
web/theme.js, web/ui.js          Theme persistence, DOM helpers, browser polling
data/database.py                Initial database schema
data/source_profiles.py         Seed source-level estimates
data/articles.db                Pipeline database, included in the repository
data/pipeline_state.py          Logical changes and successful-clustering checkpoint
data/news_snapshot.py           Standalone SQLite snapshot creation/validation
data/news-snapshot.sqlite       Published, self-contained database snapshot
data/news-manifest.json         Snapshot version, checksum, size, schema version
scripts/publish_news.py          Actions publication; may commit/push when invoked
scripts/check_frontend.py        Local Chrome DevTools browser checks
tests/                          Backend, workflow, and snapshot regression tests
docs/automatic-updates.md        Operational details, limits, and controlled rollout
.github/workflows/update_news.yml  Scheduled collection and processing
pipeline.py                     Full pipeline or separate collection/processing stages
requirements.txt                Full pipeline and web dependencies, including ML
requirements-collection.txt     Lightweight RSS-stage dependencies
requirements-web.txt            Lightweight FastAPI/Uvicorn dependencies for Render
```

## SQLite schema

`data/database.py` creates the following `articles` fields. Column order may differ in the bundled database; queries use names.

| Field | SQLite type / purpose |
| --- | --- |
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT |
| `source_name`, `source_country` | TEXT; source identity |
| `title_ar`, `body_ar` | TEXT; original headline and extracted body |
| `url` | TEXT UNIQUE; original article link |
| `published_at`, `collected_at` | TEXT; RSS publication value and collection timestamp |
| `author`, `section`, `language` | TEXT; available metadata (`language` is set to `ar`) |
| `content_hash` | TEXT; SHA-256 of a nonempty extracted body |
| `processed_text` | TEXT; prepared title/body combination |
| `cluster_id` | INTEGER; story assignment, nullable for unmatched articles |

Other tables:

- `story_groups`: `cluster_id` (primary key), `representative_title`, `article_count`, `source_count`.
- `source_profiles`: `source_name` (primary key), `political_alignment`, `ideological_tendency`, `confidence`, `short_note`.
- `article_orientation`: `article_id` (primary key, declared reference to `articles.id`), `political_alignment`, `ideological_tendency`, `confidence`, `short_reason`.
- `pipeline_state`: `key`, `value`; created during successful clustering to store the title fingerprint checkpoint.

The bundled database inspected for this review contains **227 articles, 17 story groups, two source profiles, and 20 article-orientation records**. These are review-time counts, not fixed application statistics.

## Text preprocessing and story grouping

`processing/prepare_text.py` processes only rows where `processed_text` is NULL. It normalizes whitespace, removes repeated headline text from the start of the body, and combines the headline and body. Original fields are preserved. It does not currently implement stemming, stop-word removal, or extensive Arabic character normalization.

`analysis/create_clusters.py` uses `intfloat/multilingual-e5-base` with a pinned revision, prefixes headlines with `query: `, generates normalized sentence embeddings, and calculates cosine similarity with scikit-learn. The experimental matching threshold is **0.865**, selected through manual examples rather than a comprehensive benchmark.

New pairs can create groups or join existing ones. Existing IDs are retained, and different established clusters are not automatically merged. Unmatched articles may remain without a group. Group metadata is updated from assigned articles; matching does not require different sources, so a group can contain only one source.

Title embeddings are cached locally and reused; invalid caches are regenerated safely. A title fingerprint and pending-text check skip processing when no work is required. **This is incremental embedding reuse, not a fully incremental similarity algorithm:** processing still compares all headline pairs, with quadratic time/memory cost. Stable grouping can preserve earlier incorrect assignments.

## Ideological orientation

Source profiles store conservative project estimates. The supplied Al Jazeera profile uses `unclear` political alignment and ideological tendency with `low` confidence. DW Arabic uses `independent` political alignment, `unclear` ideological tendency, and `medium` confidence. These are stored labels, not independently established facts or measures of accuracy/reliability.

A separate **20-article manual ChatGPT experiment** used headline/body text and a structured prompt, without an API integration. Saved results include alignment, tendency, numeric confidence, and a short reason. See [article-level validation](analysis/article_orientation_validation.md) and [the prompt](analysis/article_orientation_prompt.txt).

The API prefers an available article-level record and otherwise uses the source profile, with an `unclear`/low fallback if neither is available. The interface translates uncertainty to **غير واضح** and displays confidence. New articles are not automatically given experimental article-level labels. Do not run `analysis/save_article_orientation.py` against a clean database: its hardcoded IDs refer to the original evaluated articles.

## FastAPI and frontend

| Route | Behavior |
| --- | --- |
| `GET /` | Home page |
| `GET /compare?id=15` | Comparison HTML; JavaScript reads the selected group ID |
| `GET /stories` | Story-group list |
| `GET /stories/{cluster_id}` | `{cluster_id, articles}`; HTTP 404 if no articles are found |
| `/static/...` | Shared HTML/CSS/JavaScript assets |
| `GET /docs` | FastAPI's generated interactive API documentation |

Story-group responses include `cluster_id`, `representative_title`, counts, `sources`, and earliest/latest publication timestamps. Bounds are calculated from parsed ISO/RFC dates and returned as UTC ISO strings or null. Article responses retain source, headline, original date, URL, orientation level, alignment, tendency, and confidence. The frontend sorts groups newest-first using `last_published_at`, placing invalid/missing dates last.

The frontend uses HTML, CSS, and vanilla JavaScript with relative API URLs and safe DOM rendering. Its premium editorial design includes IBM Plex Sans Arabic with fallback fonts, responsive comparison cards, RTL layout, keyboard focus states, and subtle entrances/hover interactions. Reduced-motion preferences disable animations.

Both pages share Light/Dark Mode. A script applied before styles selects the system theme on first visit; manual choices persist in `localStorage` across navigation and visits, preventing a flash of the wrong theme. Theme switching also works by keyboard.

## Automatic updates

The GitHub Actions workflow uses `2-59/5 * * * *` (UTC minutes 02, 07, …, 57) plus `workflow_dispatch`. Default-branch checks and concurrency protection prevent feature-branch publication and concurrent database pushes. Only pending work loads the ML dependencies, and meaningful-data checks prevent idle commits.

After writes finish, SQLite's backup API creates a standalone snapshot, including committed WAL data. The manifest records a content-derived version, SHA-256 checksum, byte size, and schema version. Automatic data-only commits include `[skip render]`; ordinary code commits must still deploy.

FastAPI can check GitHub for a new manifest approximately every 60 seconds. Changed snapshots are downloaded with limits/timeouts, validated for checksum, integrity, and schema, then activated without disrupting existing readers. Failures keep working data; restarts use the bundled database as a fallback. GitHub is authoritative, while Render's local snapshot files are disposable caches. Local runtime refresh defaults off unless `PORT` is set; `NEWS_SNAPSHOT_REFRESH=0` explicitly disables it and `NEWS_SNAPSHOT_REFRESH=1` enables it.

Both browser pages also poll approximately **60 seconds after a completed fetch**, independently of server refresh. Unchanged data leaves cards untouched; updates preserve scroll/focus and avoid replaying entrances. Hidden tabs pause polling, active tabs resume, requests do not overlap, and errors retain existing content.

Collection scheduling, processing, GitHub delivery, server refresh, browser refresh, and Render cold starts each add latency. This is not an exact five-minute publication promise. See [automatic updates and deployment guide](docs/automatic-updates.md) for caching, cooldowns, free-tier limits, the three exact Render ignored paths, and controlled rollout. Skipping a deployment alone cannot refresh the running database; runtime delivery must be enabled and verified.

## Installation and local use

Use **Python 3.13**, matching the workflow. Run commands from the repository root; pipeline database paths are relative to it. No frontend build, Node.js, paid API, or API key is required. Initial pipeline installation/model download needs internet and substantially more storage/memory than web-only use.

```bash
git clone https://github.com/Abdulaziz-Alyahya/arabic-news-portal.git
cd arabic-news-portal
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

On Windows activate with `.venv\Scripts\Activate.ps1` in PowerShell instead of `source`.

### Website only, using the bundled data

```bash
python -m pip install -r requirements-web.txt
NEWS_SNAPSHOT_REFRESH=0 uvicorn backend.api:app --reload
```

The environment assignment above is for macOS/Linux. In PowerShell use `$env:NEWS_SNAPSHOT_REFRESH="0"`, then run `uvicorn backend.api:app --reload`.

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Choose a story through the home page so the ID corresponds to available data. Keep Render installing **`requirements-web.txt`**, not the heavy pipeline requirements.

### Full collection and processing

```bash
python -m pip install -r requirements.txt
python pipeline.py
```

The pipeline initializes tables, collects news, and processes/clusters when needed. It writes to `data/articles.db`; use a disposable checkout for experiments. It preserves existing orientation records but does not seed source profiles automatically.

Available stages and individual commands:

```bash
python pipeline.py --collect-only
python pipeline.py --process-only
python processing/prepare_text.py
python analysis/create_clusters.py
```

The two stage flags are mutually exclusive. Collection-only needs `requirements-collection.txt`; processing needs the full ML dependencies. `analysis/generate_embeddings.py` is an optional diagnostic report and is not the pipeline's clustering step. Do not invoke `scripts/publish_news.py` during local review: it is an Actions publication tool that can commit and push.

### Clean start without changing the existing project database

Use a **separate disposable checkout**, not the deployed project or the checkout containing your working changes. In that checkout, install the full dependencies as above, then retain the seed database under a backup name:

```bash
mv data/articles.db data/articles.seed.db
python data/database.py
python data/source_profiles.py
python pipeline.py
NEWS_SNAPSHOT_REFRESH=0 uvicorn backend.api:app --reload
```

`mv` is a macOS/Linux command; Windows users can rename the file with their file manager. The source-profile script seeds/replaces its two profiles, so run it deliberately. Do not restore the ID-bound article experiment onto newly collected articles. The tracked snapshot/manifest still represent the original data until regenerated; they are not used by this offline local server. Do not publish this experimental checkout or its seed backup.

## Testing

In a full-pipeline environment, install the additional YAML parser used by the workflow tests:

```bash
python -m pip install PyYAML
python -m unittest discover -s tests -v
```

Tests cover collection fixtures, URL/body duplicates, no-work processing, stable IDs, orientation preservation, parsed publication dates, HTTP 429 cooldowns, embedding-cache recovery, workflow configuration, and snapshot validation/recovery/concurrent readers. Tests use temporary databases; the bundled database is only read/copied. A successful fixture run does not prove the live feeds, GitHub workflow, or Render deployment succeeded.

For automated browser checks, keep the local web server running and launch an isolated Chrome. On macOS, in another terminal:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --remote-debugging-port=9222 \
  --remote-allow-origins=http://localhost:9222 \
  --user-data-dir=/tmp/arabic-news-browser-check about:blank
```

Then, from the repository root:

```bash
python scripts/check_frontend.py
```

Use your platform's Chrome executable and an isolated temporary profile on other systems. The script requires FastAPI on port 8000 and Chrome on 9222. It simulates the registered 60-second timer and changed/unchanged API responses; it does not wait for actual news publication. It checks polling, ordering, comparison updates, theme persistence, responsive RTL layout, reduced motion, and JavaScript errors. Manually review extended reading, screen-reader behavior, and external article availability.

**Last verified implementation results:** 35 automated tests passed; browser polling and theme/layout checks passed; SQLite integrity checks passed and the production database checksum remained unchanged. These results were obtained during the preceding implementation verification, not a new test execution for this README-only update. The operational guide's earlier 21-test result predates the snapshot tests. Fresh dependency installation and remote rollout have not been verified by this documentation review.

## Adding another Arabic source

1. Add a dictionary to `SOURCES` in `collection/rss_collector.py` with `name`, `country`, `rss_url`, and a `hosts` set containing the permitted article domains. Include legitimate redirect destinations; do not broaden it to unrelated hosts.
2. Verify an Arabic feed, metadata, article extraction, robots permissions, and rate limits. Retain RSS-only data when extraction is unavailable; do not bypass restrictions.
3. If appropriate, add a conservative profile to `data/source_profiles.py` with the exact same source name. Run the profile seed in your test checkout, understanding that it also replaces the existing seeded profiles. Without a profile, the API still supports the source with uncertain orientation fallback. Do not invent labels.
4. Add fixtures for feed collection, duplicate handling, unavailable bodies, and 429 behavior, then review grouping manually using a temporary database.
5. Check the UI's source display. Unrecognized names use the existing generic display; optional source-specific styling must not change orientation results.

There is no separate source-registration API. New source coverage and rights to republish extracted content must be reviewed before publication.

## Evaluation and limitations

[Week 6 evaluation](analysis/week6_evaluation.md) records a small qualitative review:

| Reviewed sample | Observed result |
| --- | --- |
| Messi / Argentina international career | Correct grouping |
| Artificial intelligence | False positive: shared topic, different events |
| Iran news | Correct grouping in the reviewed sample |
| Houthi escalation | Correct grouping in the reviewed sample |

Orientation and uncertainty presentation were reviewed, but article ideology was not independently established. These examples are not a comprehensive accuracy measurement; no precision/recall claim follows from them. Earlier [manual clustering checks](analysis/manual_validation.md), [Week 4 validation](analysis/week4_validation.md), and the [one-person Week 5 usability check](analysis/week5_usability.md) provide additional context.

Current limitations include topic-versus-event false positives, headline-only comparisons, an experimental threshold, quadratic pairwise processing, persistent earlier grouping errors, two-source coverage, incomplete article bodies, and experimental orientation estimates. Stored URLs with missing bodies are skipped on later runs rather than automatically backfilled. Numeric confidence from the manual experiment is not calibrated.

Scheduling/cache failures, source restrictions, GitHub delivery, repository growth, and free-hosting limits affect freshness and sustainability. Runtime downloads reject incompatible schemas and snapshots larger than 64 MiB; coordinated upgrades are required as the project grows. Extracted bodies already exist in the public database: access permission is not a redistribution license. No embeddings, internal prompts, or debugging identifiers are exposed as page content.

Refer to [the operational guide](docs/automatic-updates.md) before publishing. Commit, push, merge, deployment, and Render settings changes require explicit approval.
