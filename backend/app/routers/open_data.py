from fastapi import APIRouter, Query

from app.services.open_data_sources import DATA_PATH, refresh_open_data_places

router = APIRouter(tags=["open-data"])


@router.get("/open-data/status")
def open_data_status() -> dict:
    return {
        "cache_exists": DATA_PATH.exists(),
        "cache_path": str(DATA_PATH),
    }


@router.post("/open-data/refresh")
def open_data_refresh(
    limit: int = Query(default=50, ge=1, le=200),
    search: str = "",
) -> dict:
    return refresh_open_data_places(limit=limit, search=search)
