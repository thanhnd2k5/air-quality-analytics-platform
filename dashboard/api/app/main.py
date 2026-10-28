from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.cache import ResponseCache
from app.config import get_settings
from app.errors import EmptyMartError
from app.routers import (
    alerts,
    clusters,
    compare,
    episodes,
    health,
    map_view,
    olap,
    overview,
    predictions,
    stations,
    weather,
)

settings = get_settings()

app = FastAPI(
    title="Air Quality Dashboard API",
    description="Read-only API for Phase 11 dashboard (DWH / marts).",
    version="0.1.0",
)

# Added before CORS so it sits inside it: cached bodies never carry per-origin headers.
if settings.response_cache_mb > 0:
    app.add_middleware(
        ResponseCache,
        max_mb=settings.response_cache_mb,
        check_seconds=settings.response_cache_check_seconds,
        # Slow parameter-free calls made when a page opens (olap/meta scans the fact 11×).
        warm_paths=(
            "/api/olap/meta",
            "/api/predictions/meta",
            "/api/alerts/meta",
            "/api/alerts/summary?split=test",
        ),
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(EmptyMartError)
async def empty_mart_handler(_request: Request, exc: EmptyMartError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": exc.message})


app.include_router(health.router, prefix="/api")
app.include_router(overview.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(episodes.router, prefix="/api")
app.include_router(weather.router, prefix="/api")
app.include_router(predictions.router, prefix="/api")
app.include_router(map_view.router, prefix="/api")
app.include_router(stations.router, prefix="/api")
app.include_router(clusters.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(olap.router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"service": "dashboard-api", "docs": "/docs"}
