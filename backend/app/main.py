import sys
import io
import os
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="LoL Match Coach")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — configurable via env var, defaults to localhost for dev
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:4200").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# Simple API key auth for production (optional, set APP_API_KEY env var to enable)
APP_API_KEY = os.getenv("APP_API_KEY", "")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Skip auth if no APP_API_KEY is configured (dev mode)
    if not APP_API_KEY:
        return await call_next(request)

    # Skip auth for docs, health check, and static files
    path = request.url.path
    if path in ("/docs", "/openapi.json", "/health") or not path.startswith("/api"):
        return await call_next(request)

    # Check API key header
    provided_key = request.headers.get("X-API-Key", "")
    if provided_key != APP_API_KEY:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok"}


from app.routers.match import router
app.include_router(router)

# Serve Angular static files in production
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "frontend" / "browser"
if STATIC_DIR.exists():
    from fastapi.responses import FileResponse

    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets") if (STATIC_DIR / "assets").exists() else None

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve Angular SPA — return index.html for all non-API routes."""
        # Don't intercept API routes
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))
