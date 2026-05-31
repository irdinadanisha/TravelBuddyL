from fastapi import APIRouter, HTTPException

from app.services.google_places import DATA_PATH, refresh_google_places

router = APIRouter(tags=["google-places"])


@router.get("/google-places/status")
def google_places_status() -> dict:
    return {
        "cache_exists": DATA_PATH.exists(),
        "cache_path": str(DATA_PATH),
    }


@router.post("/google-places/refresh")
def google_places_refresh() -> dict:
    try:
        return refresh_google_places()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
