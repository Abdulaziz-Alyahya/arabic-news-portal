import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from backend import story_service
from backend.snapshot_store import SnapshotStore

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.story_service import (
    get_story_groups,
    get_story_articles
)


@asynccontextmanager
async def lifespan(app):
    # Local review remains offline unless explicitly enabled. Render sets PORT.
    enabled = os.environ.get('NEWS_SNAPSHOT_REFRESH', '1' if 'PORT' in os.environ else '0') == '1'
    task = None
    stop = asyncio.Event()
    if enabled:
        store = SnapshotStore(Path(__file__).resolve().parent.parent / 'data/articles.db')
        story_service.SNAPSHOT_STORE = store
        async def refresh_loop():
            while not stop.is_set():
                await asyncio.to_thread(store.refresh)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=store.next_delay)
                except asyncio.TimeoutError:
                    pass
        task = asyncio.create_task(refresh_loop())
    try:
        yield
    finally:
        stop.set()
        if task:
            await task
        story_service.SNAPSHOT_STORE = None


app = FastAPI(
    lifespan=lifespan,
    title="Arabic News Comparison API",
    description="Backend API for comparing Arabic news stories",
    version="1.0"
)


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"


# Serve CSS and JavaScript files
app.mount(
    "/static",
    StaticFiles(directory=WEB_DIR),
    name="static"
)


@app.middleware("http")
async def fresh_news_responses(request, call_next):
    response = await call_next(request)
    if request.url.path == "/stories" or request.url.path.startswith("/stories/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# Home page
@app.get("/")
def home():
    return FileResponse(
        WEB_DIR / "index.html"
    )


# Story comparison page
@app.get("/compare")
def compare_page():
    return FileResponse(
        WEB_DIR / "story.html"
    )


# API: all story groups
@app.get("/stories")
def stories():
    return get_story_groups()


# API: articles inside one story
@app.get("/stories/{cluster_id}")
def story(cluster_id: int):

    articles = get_story_articles(cluster_id)

    if not articles:
        raise HTTPException(
            status_code=404,
            detail="Story group not found"
        )

    return {
        "cluster_id": cluster_id,
        "articles": articles
    }
