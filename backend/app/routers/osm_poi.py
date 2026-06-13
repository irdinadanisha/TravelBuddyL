from fastapi import APIRouter, Query

from app.services.osm_poi_ingestion import DATA_PATH, refresh_osm_poi_places

router = APIRouter(tags=["openstreetmap-poi"])


@router.get("/osm-poi/status")
def osm_poi_status() -> dict:
    return {
        "cache_exists": DATA_PATH.exists(),
        "cache_path": str(DATA_PATH),
    }


@router.post("/osm-poi/refresh")
def osm_poi_refresh(
    cities: str = "Paris,Lyon,Marseille,Nice,Bordeaux,Strasbourg,Lille",
    city_limit: int = Query(default=150, ge=1, le=500),
) -> dict:
    return refresh_osm_poi_places(
        cities=[city.strip() for city in cities.split(",") if city.strip()],
        city_limit=city_limit,
    )
