from fastapi import APIRouter, HTTPException

from app.services.osm_places import DATA_PATH, refresh_osm_places

router = APIRouter(tags=["openstreetmap-places"])


@router.get("/osm-places/status")
def osm_places_status() -> dict:
    return {
        "cache_exists": DATA_PATH.exists(),
        "cache_path": str(DATA_PATH),
    }


@router.post("/osm-places/refresh")
def osm_places_refresh() -> dict:
    try:
        return refresh_osm_places()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
