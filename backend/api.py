from fastapi import FastAPI, HTTPException

from backend.story_service import (
    get_story_groups,
    get_story_articles
)


app = FastAPI(
    title="Arabic News Comparison API",
    description="Backend API for comparing Arabic news stories",
    version="1.0"
)


@app.get("/")
def home():
    return {
        "message": "Arabic News Comparison API is running"
    }


@app.get("/stories")
def stories():
    return get_story_groups()


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
