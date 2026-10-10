from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import compare, episodes, health, map, overview, predictions, stations, weather

settings = get_settings()

app = FastAPI(
    title="Air Quality Dashboard API",
    description="Read-only API for Phase 11 dashboard (DWH / marts).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(overview.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(episodes.router, prefix="/api")
app.include_router(weather.router, prefix="/api")
app.include_router(predictions.router, prefix="/api")
app.include_router(map.router, prefix="/api")
app.include_router(stations.router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"service": "dashboard-api", "docs": "/docs"}
