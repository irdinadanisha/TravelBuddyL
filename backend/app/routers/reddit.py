from fastapi import APIRouter, HTTPException, Query

from app.services.reddit_ingestion import (
    DATA_PATH,
    RAW_SNIPPETS_PATH,
    refresh_reddit_dataset,
    refresh_reddit_places,
)

router = APIRouter(tags=["reddit"])


@router.get("/reddit/status")
def reddit_status() -> dict:
    return {
        "cache_exists": DATA_PATH.exists(),
        "cache_path": str(DATA_PATH),
        "raw_cache_exists": RAW_SNIPPETS_PATH.exists(),
        "raw_cache_path": str(RAW_SNIPPETS_PATH),
    }


@router.post("/reddit/refresh")
def reddit_refresh() -> dict:
    try:
        return refresh_reddit_places()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reddit/refresh-dataset")
def reddit_refresh_dataset(
    max_snippets: int = Query(default=500, ge=1, le=2000),
    posts_per_query: int = Query(default=25, ge=1, le=100),
    comments_per_post: int = Query(default=15, ge=1, le=100),
    time_filter: str = "all",
) -> dict:
    try:
        return refresh_reddit_dataset(
            max_snippets=max_snippets,
            posts_per_query=posts_per_query,
            comments_per_post=comments_per_post,
            time_filter=time_filter,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
