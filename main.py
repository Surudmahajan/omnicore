"""
OmniCore — FastAPI Application Entry Point
Registers all routers, applies middleware, CORS, security headers,
initialises the database, seeds datasets, and starts the sync scheduler.
"""
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import init_db, db_session
from models import Dataset

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("omnicore")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("OmniCore v%s starting (%s)…", settings.APP_VERSION, settings.ENVIRONMENT)

    # Create tables
    init_db()
    logger.info("Database initialised at: %s", settings.DATABASE_PATH)

    # Ensure storage directories exist
    os.makedirs(settings.DATASET_STORAGE_PATH, exist_ok=True)
    os.makedirs(os.path.dirname(settings.DATABASE_PATH), exist_ok=True)

    # Initialize HF Repository
    from hf_storage import hf_storage
    try:
        hf_storage.initialize_repository()
    except Exception as e:
        logger.error(f"Failed to initialize HF repository: {e}")

    # Seed dataset catalog
    from datasets import seed_datasets
    with db_session() as db:
        seed_datasets(db)
    count = 0
    with db_session() as db:
        count = db.query(Dataset).filter_by(is_active=True).count()
    logger.info("Dataset registry ready: %d datasets.", count)

    # Ensure storage directories exist
    os.makedirs(settings.DATASET_STORAGE_PATH, exist_ok=True)

    # Start sync scheduler
    from sync import scheduler
    scheduler.start()
    logger.info("Sync scheduler started.")

    logger.info("OmniCore is ready.")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("OmniCore shutting down…")
    from sync import scheduler
    scheduler.stop()
    logger.info("Sync scheduler stopped.")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="OmniCore API",
    description="Developer Data Infrastructure Platform — The Core of Developer Data.",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ── CORS Middleware ────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
    max_age=600,
)


# ── Security Headers Middleware ────────────────────────────────────────────────

@app.middleware("http")
async def security_headers(request: Request, call_next):
    start_time = time.perf_counter()
    response: Response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["X-Response-Time"] = f"{elapsed_ms}ms"

    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com;"
        )

    return response


# ── Rate Limiting ──────────────────────────────────────────────────────────────
# Simple in-memory rate limiter using slowapi

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiting enabled.")
except ImportError:
    logger.warning("slowapi not installed — rate limiting disabled.")


# ── Global Exception Handler ───────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An internal server error occurred.",
            "detail": str(exc) if settings.DEBUG else "Please try again later.",
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────────

from auth import router as auth_router
from datasets import router as datasets_router
from sync import router as sync_router
from ai import router as ai_router, console_router, dashboard_router

API_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(datasets_router, prefix=API_PREFIX)
app.include_router(sync_router, prefix=API_PREFIX)
app.include_router(ai_router, prefix=API_PREFIX)
app.include_router(console_router, prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)


# ── Health & Info Endpoints ────────────────────────────────────────────────────

# ── Health & Info Endpoints ────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    """Health check endpoint for load balancers and HuggingFace Space probes."""
    try:
        with db_session() as db:
            dataset_count = db.query(Dataset).filter_by(is_active=True).count()
        db_healthy = True
    except Exception:
        dataset_count = 0
        db_healthy = False

    return {
        "status": "healthy" if db_healthy else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected" if db_healthy else "error",
        "datasets": dataset_count,
        "ai_configured": bool(settings.OPENROUTER_API_KEY),
    }


@app.get(f"{API_PREFIX}/stats", tags=["Health"])
def platform_stats():
    """Public platform statistics."""
    with db_session() as db:
        from sqlalchemy import func
        total_datasets = db.query(Dataset).filter_by(is_active=True).count()
        domain_counts = (
            db.query(Dataset.domain, func.count(Dataset.id))
            .filter_by(is_active=True)
            .group_by(Dataset.domain)
            .all()
        )
        total_records = db.query(func.sum(Dataset.record_count)).filter_by(is_active=True).scalar() or 0
        avg_quality = db.query(func.avg(Dataset.quality_score)).filter_by(is_active=True).scalar() or 0.0

    return {
        "success": True,
        "data": {
            "total_datasets": total_datasets,
            "total_records_indexed": int(total_records),
            "average_quality_score": round(float(avg_quality), 2),
            "domains": {row[0]: row[1] for row in domain_counts},
            "solution_packs": 8,
            "connectors_supported": 8,
            "api_version": "v1",
        },
    }

# ── Static Files (React Frontend) ─────────────────────────────────────────────

from fastapi.responses import FileResponse

static_dir = os.path.join(os.path.dirname(__file__), "static")

# Mount the inner /static folder (JS/CSS assets) for efficient caching
inner_static = os.path.join(static_dir, "static")
if os.path.exists(inner_static):
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=inner_static), name="static")

@app.get("/{full_path:path}", tags=["Frontend"], include_in_schema=False)
async def serve_react_app(full_path: str):
    """Catch-all route to serve the React SPA and static files."""
    # If it's an API route that fell through, return 404 JSON
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"success": False, "message": "API endpoint not found."})
        
    # Try to serve a specific file if it exists (e.g., /favicon.ico)
    if full_path:
        file_path = os.path.join(static_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
            
    # Otherwise, return index.html for React Router to handle
    index_file = os.path.join(static_dir, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
        
    return JSONResponse(status_code=404, content={"error": "Frontend build not found. Please build React and place it in the static/ folder."})


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
