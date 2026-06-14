from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.routers import (
    export,
    google_places,
    health,
    open_data,
    osm_places,
    osm_poi,
    reddit,
    sessions,
    travel,
)

app = FastAPI(
    title="TravelBuddy France API",
    version="0.1.0",
    description="AI travel buddy backend focused on local-style recommendations in France.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|\[::1\]):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(travel.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(reddit.router, prefix="/api")
app.include_router(google_places.router, prefix="/api")
app.include_router(osm_places.router, prefix="/api")
app.include_router(osm_poi.router, prefix="/api")
app.include_router(open_data.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
