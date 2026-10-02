from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.story_service import (
    get_story_groups,
    get_story_articles
)


app = FastAPI(
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