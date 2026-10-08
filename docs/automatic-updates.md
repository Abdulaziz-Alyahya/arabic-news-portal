# Automatic news updates

The workflow checks RSS at minutes **02, 07, 12, …, 57 of every hour (UTC)**:

```yaml
on:
  schedule:
    - cron: "2-59/5 * * * *"
  workflow_dispatch:
```

This is a five-minute scheduling target, not a publication guarantee. The default
branch is `main`; the current work is on `ui-redesign`. Scheduled runs activate
only after the workflow reaches the default branch. Manual runs on a feature
branch are intentionally skipped so they cannot publish its data to `main`.

## Collection and processing

1. Restore the small collection pip cache; install `requirements-collection.txt`.
2. Restore private source cooldown state from Actions cache; fetch supported RSS
   feeds with connection/read timeouts only when their cooldown has expired.
3. Skip stored URLs before visiting article pages. Check the source's robots
   policy, honor a declared crawl delay (at least one second between new pages),
   and retain RSS-only metadata for restricted/unavailable pages without bypassing
   access controls. Grouping already uses titles, so it still works without a body.
4. On HTTP 429 from a feed, robots policy, or article page, honor Retry-After
   seconds or HTTP-date headers and stop all requests for that source until the
   UTC deadline. Use five minutes when the header is absent or malformed. Already
   available RSS metadata is retained, and other sources continue. Save changed
   cooldown state before ML processing, even if subsequent processing fails.
   Keep the original unique URL and SHA-256 body-hash duplicate checks.
5. Compare article IDs/titles with the last successful clustering checkpoint.
   A singleton without a cluster does not cause perpetual reprocessing.
6. Only if processing is pending, restore ML downloads, model files and title
   vectors; install CPU ML dependencies and process previously unprepared rows.
   Validate vector-cache format, version, hashes, dimensions, finite values and
   normalization. Empty, truncated or incompatible caches are regenerated; only
   their own file is atomically replaced after successful regeneration. Valid
   cached vectors and neighboring files are preserved.
7. Encode only titles absent from the private vector cache. On a cache miss,
   safely regenerate the necessary vectors. Keep the E5 `query:` prefix,
   normalized embeddings, cosine similarity, `0.865` threshold, original pair
   traversal, and refusal to merge different established clusters.
8. Update assignments and story metadata only where values change. Save the
   checkpoint in the same transaction as successful clustering. The first run
   after this upgrade creates a durable checkpoint; this is a one-time change.
9. Compare logical table contents before and after, ignoring SQLite page-layout
   differences. No meaningful change means no commit and no Render rebuild.
10. Serialize workflow runs. Before publication, check whether the remote
    database changed since checkout. Refuse a binary database merge/overwrite;
    the next run retries against the newest database. Safely rebase over code
    changes and retry a normal push up to three times. Never force-push.

`pipeline.py` supports normal collection-plus-processing, `--collect-only`, and
`--process-only`. Do not run it against the production database just to test.
Clustering retains all-pairs comparison to avoid changing existing semantics;
this remains O(n²) and will eventually need a separate, carefully validated
scalability change. The vector cache is disposable, gitignored, and not stored in
the SQLite database or exposed by the API. The model revision is pinned to the
same snapshot used in the existing local model cache.

No orientation values are generated or modified. New articles use the existing
source-profile fallback. Missing source policies or disallowed pages prevent full-body extraction; RSS
headlines, publication dates and original links remain available. The log reports
policy skips. A content-duplicate URL with
a different URL is not inserted, so a later run may fetch that alias again to
confirm its content hash. Known stored URLs never require page extraction again.

## Publication dates and cooldown persistence

Story-group date bounds now come from parsed ISO/RFC timestamps rather than SQL
text MIN/MAX. Valid timezone-less dates are treated as UTC; malformed or missing
values are ignored. Bounds are returned as UTC ISO strings (or null if no valid
publication date exists), preserving the same response keys and value types.
Comparison articles are ordered by parsed time, with unavailable dates last;
their original date fields and orientation values remain intact.

Cooldown deadlines are stored in `.cache/news-collection/cooldowns.json`, excluded
from Git and the published database. Actions restores the latest cooldown cache
and saves a new snapshot only when the state changes. Numeric and HTTP-date
Retry-After values survive a fresh runner because deadlines use UTC epoch time.
The minimum wait for a zero/past deadline is one second. Expired deadlines are
removed on the next run. Pausing a source also pauses its RSS checks; already
fetched RSS metadata remains available for that run.

Actions caching is best effort: cache eviction, corruption or upload failures can
lose a cross-run cooldown. In-run backoff is always enforced after an observed
429. A new 429 on a cache miss establishes a new cooldown; requests are not retried
during that deadline. No cooldown-only SQLite commit or Render deploy is created.

## Browser refresh

Both pages fetch initially and schedule another check 60 seconds after completion.
There is one refresh in flight, a 20-second request timeout, `cache: 'no-store'`,
and server `Cache-Control: no-store` headers. Hidden tabs pause scheduling; visible
tabs check immediately. Page exit aborts work, and back/forward-cache restoration
restarts polling. A browser-hidden initial page loads when it becomes visible.

Only displayed fields contribute to the comparison signature. Source names are
normalized and stories remain newest-first, with invalid/missing dates last.
Unchanged responses do not touch the card DOM. Changed responses retain unchanged
card nodes; added/changed cards suppress entrance animations during background
refresh. Scroll position and focused article/story links are restored. The existing
RTL design, reduced-motion settings and saved light/dark preference remain intact.
Transient failures keep already displayed content and show a small retry status.
Initial failures offer a retry button, and automatic polling continues.

The comparison also checks its article data and representative title; failure to
refresh a title does not hide successfully loaded articles.

## Free-tier practicality and limits

The repository was confirmed public with `main` as its default branch. Standard
GitHub-hosted runners for public repositories are free, unlike larger runners:
https://docs.github.com/en/actions/reference/runners/github-hosted-runners

Five minutes is GitHub's minimum scheduled interval. Busy-period delays, dropped
scheduled jobs, concurrency, and 60-day repository inactivity can affect schedules:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

This design avoids repeated ML work on idle runs and unnecessary article-page
requests. Caches can be evicted; their absence increases processing time without
changing results. Keep Actions cache storage within its included allocation;
immutable vector snapshots are subject to eviction. Git database history grows
with meaningful publications, even though unchanged runs create no commits.

Routine news commits now skip Render builds and are delivered through runtime
snapshot refresh (see the rollout section below). Hobby includes 500 Starter build
minutes per month; these remain available for approved code/configuration deployments:
https://render.com/docs/build-pipeline
Build filters and data-only skip messages must be verified during rollout. They
remove news-driven builds, but do not remove bandwidth or repository-size limits.

No paid feature or paid API is introduced. To keep bills at zero, verify Render
has **no payment method** or configure its documented spend limit, and use only
standard Actions runners without paid cache/storage allowance increases. With no
payment method, exhausted Render build minutes disable new builds for the rest of
the month while the existing site remains active. This is a service limitation,
not automatic free capacity expansion:
https://render.com/docs/free#monthly-usage-limits

Collection frequency, ML processing duration, server snapshot refresh,
and the browser's 60-second check are separate delays. They add together. A free
Render service can also take time to wake after inactivity. Browser polling only
reads data that has already reached the deployed service; it does not run collection.
The site URL remains https://arabic-news-portal.onrender.com.

## Data exposure

No secrets, authentication tokens or additional article fields were added to API
responses. Hugging Face caching is limited to model files, excluding its token
file. Title vectors stay private to local/Actions caches. The repository already
contains extracted article bodies in its public SQLite database; this existing
exposure remains. Robots permission is an access policy, not a license to republish
full text. Review source permission before publishing full extracted content.

## Local verification

Run focused fixtures in the existing environment (tests require NumPy, sklearn,
PyYAML and the existing collection dependencies; no additions to Render):

```bash
.venv-test/bin/python -m unittest discover -s tests -v
.venv-test/bin/python -m uvicorn backend.api:app --reload
```

Open http://127.0.0.1:8000. Toggle the theme, open a comparison, scroll through
stories, and inspect network requests over a minute. Background errors should keep
existing content. The only production database reads during tests are schema/data
copies; fixtures use temporary databases.

Automated browser checks use the Chrome DevTools protocol without another package:
launch an isolated Chrome with `--headless --remote-debugging-port=9222
--remote-allow-origins=http://localhost:9222 --user-data-dir=/tmp/news-refresh-review`
while FastAPI is running, then run `python3 scripts/check_frontend.py`.
The script simulates firing the actual registered 60-second callback, mocks new
and unchanged API responses, and checks overlap, visibility, lifecycle, scroll,
focus, themes, comparison updates, RTL, reduced motion and mobile widths. It does
not wait for actual news to change or write to the database.

Local results after the final fixes: 21 backend/workflow tests passed (the original
seven plus 14 regression tests for date bounds, rate-limit backoff and vector-cache
recovery). Both browser suites passed, including system-theme selection, keyboard
toggling, reload/navigation persistence and polling. Polling tests simulate the
registered 60-second timer rather than waiting for new news. All 17 current story
bounds matched parsed timestamps, and SQLite integrity returned `ok`.
Both real RSS feeds returned HTTP 200 with 25 and 49 entries during the check.
A final bounded real-source test saved two articles to a temporary database:
Al Jazeera RSS metadata (its tested article path was disallowed by robots policy)
and permitted DW article content. The repeated run saved none. Real cached E5
processing of 229 articles took about eight seconds locally; existing cluster IDs
and article-orientation rows remained unchanged. A no-work rerun was byte-identical.
Runner performance can differ.
The production database SHA-256 remained
`508d14d299690d0bcf71c4a3327f4704b3deaaa32ccff1a7cc78125b771d9109`.

The Actions workflow has been parsed and checked locally, but has not been run
on GitHub. Render dashboard settings, allowance, build command, deployment branch,
and a new deployment have not been verified. External publisher page availability
and full screen-reader behavior still require manual review.

## Publishing after explicit approval

1. Review `git diff` plus new files. Keep this work on `ui-redesign`; do not replace
   the live database with a fixture. Include the earlier redesign's `theme.js`,
   `ui.js`, HTML and stylesheet changes in the reviewed changeset.
2. Check Render's existing service before merging: repository is this repository,
   deployed branch is `main`, build command remains
   `pip install -r requirements-web.txt`, start command is
   `uvicorn backend.api:app --host 0.0.0.0 --port $PORT`, and the plan is Free.
   Verify zero-spend controls and remaining monthly build allowance. Do not change
   these settings without approval. There is no Render configuration in the repo
   with which to independently verify the current dashboard settings.
3. After approval, stage the reviewed files, commit on `ui-redesign`, push that
   branch, and open a pull request targeting `main`. Merge only after approval.
   After approval, these commands stage the intended combined changeset:

   ```bash
   git add .github/workflows/update_news.yml .gitignore pipeline.py \
     collection/rss_collector.py processing/prepare_text.py analysis/create_clusters.py \
     data/pipeline_state.py backend/api.py backend/story_service.py requirements-collection.txt \
     scripts/publish_news.py scripts/check_frontend.py tests/test_news_updates.py \
     tests/test_news_regressions.py tests/test_snapshots.py \
     data/news_snapshot.py data/news-snapshot.sqlite data/news-manifest.json \
     backend/snapshot_store.py \
     docs/automatic-updates.md web/index.html web/story.html web/style.css \
     web/app.js web/story.js web/theme.js web/ui.js
   git diff --cached --stat
   git commit -m "Add efficient automatic news updates and refined Arabic interface"
   git push -u origin ui-redesign
   ```

   Open the pull request on GitHub and review it before merging. The five-minute
   schedule becomes active on `main`, not on this feature branch.
4. In GitHub Actions, select **Update Arabic News → Run workflow → main**.
   Confirm caches, the collection count, conditional processing, and a meaningful
   data commit. A second unchanged run should skip ML and create no commit. A
   protected default branch must allow the authorized bot update; otherwise the
   normal push will fail safely. Do not weaken protections without approval.
5. Follow the snapshot rollout and Build Filter settings below. Check that the
   initial code deployment uses lightweight web dependencies and inspect
   `/stories` and a comparison on the unchanged site URL. Then leave the browser
   open for a minute and confirm it checks the deployed data automatically.
6. Monitor Render build allowance, runner duration, cache usage and repository
   size. Slow the cron if measured usage cannot fit the free allowance.

Nothing was committed, pushed, merged, or deployed during this local implementation.

## News delivery without Render builds

GitHub remains authoritative. After successful pipeline writes, publication uses SQLite's online backup API to generate `data/news-snapshot.sqlite` and `data/news-manifest.json`. The backup includes committed WAL pages without checkpointing or modifying the source database. The exported database uses DELETE journal mode and needs no sidecar files. The manifest contains schema version 1, a content-derived version (SHA-256), the SHA-256 checksum, and byte size. All three data files are committed together, only on meaningful changes, with `Update Arabic news data [skip render]`. The publisher refuses pre-existing staged changes; ordinary code commits do not receive a skip phrase.

FastAPI runs a single refresh loop per server process. Runtime refresh is enabled on Render when `PORT` is present; set `NEWS_SNAPSHOT_REFRESH=1` explicitly in Render to make this unambiguous. Local review remains offline by default; setting that variable enables downloads from the public default branch (`main`). No credentials are required. Do not enable it against the old remote branch until the new snapshots have been published.

The loop checks immediately on startup, then approximately every 60 seconds after completion. Unchanged versions download only the small manifest. Each refresh allows at most two attempts, with 10-second network timeouts and transfer deadline checks. Failures back off to 120, 240, 480, then at most 600 seconds. Responses are size-limited (manifest 4 KiB, database 64 MiB). Snapshots must match the manifest checksum and size, pass SQLite integrity/foreign-key checks, have the required tables and compatible column types, and use a standalone journal mode. A manifest/database race across a GitHub commit fails validation and retries; it never activates mixed data.

Validated files are renamed into immutable versioned cache paths and the active pointer is switched under a lock. Requests open read-only connections under the same lock; existing readers retain their original file until they close. Retired files are removed only when no readers remain. The bundled database is never replaced or written by runtime refresh. Failed refreshes preserve the active snapshot. After a restart or sleep the service uses its bundled database until it can fetch the current snapshot again; local storage is only a disposable cache. Refresh shutdown waits for the bounded in-flight operation. Multiple Uvicorn workers would each maintain their own cache/loop; retain the existing single-process start command.

The frontend, API response contracts, original links, orientation fallbacks, theme selection, and browser polling remain unchanged. Browser requests continue using relative `/stories` paths. GitHub schedules, GitHub raw response caching/throttling, processing duration, server refresh, browser refresh, and Render cold starts all add latency. This is not a real-time guarantee. Database commits and repository history still grow; monitor that separately. Raw GitHub delivery has no application-specific availability guarantee. No paid provider or ML dependency was added to the web service.

### Manual Render settings after approval

Keep the existing service and URL. In **Settings → Build & Deploy → Build Filters → Edit**, leave Included Paths empty and add exactly these **Ignored Paths**:

- `data/articles.db`
- `data/news-snapshot.sqlite`
- `data/news-manifest.json`

Do not ignore `data/**`: Python code under `data/` must still deploy. Code changes still deploy even when accompanied by these ignored data files. Manual deploys and configuration changes bypass build filters. Preserve build command `pip install -r requirements-web.txt` and the existing Uvicorn start command. Set `NEWS_SNAPSHOT_REFRESH=1` under Environment. Set the workspace Build Pipeline spend limit to zero to prevent purchasing additional build minutes; review bandwidth usage separately.

### Controlled rollout

1. Review and approve the local changes; run the full test suite. Confirm the three ignored paths above in Render (no settings have been changed by this implementation).
2. Merge/push the approved code and initial snapshot/manifest together to `main` with a **normal code commit**, without `[skip render]`. This first deployment must build the runtime reader. Confirm the lightweight build command and enable `NEWS_SNAPSHOT_REFRESH=1`.
3. Check the same live URL, both API routes, source links, theme persistence, and server logs. Confirm the running code can fetch and validate the published snapshot.
4. Manually run the workflow on `main`. If news changes, verify its data-only commit includes `[skip render]` and the matching manifest/snapshot. Confirm Render records a skipped deployment, yet the API and browser show new data after their refresh intervals. An unchanged workflow should create no commit.
5. Monitor Render build usage, bandwidth, Actions duration, repository size, and refresh errors. Do not claim this remote verification passed until it is performed.

Rollback the runtime feature with `NEWS_SNAPSHOT_REFRESH=0` and an approved deployment if necessary; the service uses its bundled database. To restore fresh data in that mode requires a normal deployment. Incompatible future schema changes need a coordinated code deployment and manifest schema-version change; old readers reject incompatible snapshots and keep their working data.
