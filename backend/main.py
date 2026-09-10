"""
FastAPI application entry point.
Configures CORS, static file serving, and includes all API routers.
"""
import logging
import os
import sys
from pathlib import Path

# Add backend directory to python path for module imports
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from routes.screening import router as screening_router
from routes.dashboard import router as dashboard_router

# ── Load environment variables ─────────────────────────────────────────
load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── FastAPI App ────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Document Screening System",
    description="Forensic AI-powered fake identity and document tamper detection — SIH Project",
    version="1.0.0",
)

# ── CORS ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ────────────────────────────────────────────────────────
app.include_router(screening_router)
app.include_router(dashboard_router)

# ── Health Check ───────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "AI Document Screening System"}

# ── Serve Frontend Static Files ────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    # Serve CSS, JS assets
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js",  StaticFiles(directory=str(FRONTEND_DIR / "js")),  name="js")

    @app.get("/")
    async def serve_dashboard():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/screen")
    async def serve_screen():
        return FileResponse(str(FRONTEND_DIR / "screen.html"))

    @app.get("/report")
    async def serve_report():
        return FileResponse(str(FRONTEND_DIR / "report.html"))
else:
    logger.warning(f"Frontend directory not found at {FRONTEND_DIR}. Skipping static file serving.")


# ── Startup Event ──────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    os.makedirs(os.getenv("UPLOAD_DIR", "uploads"), exist_ok=True)
    logger.info("=" * 60)
    logger.info("  AI Document Screening System — Started")
    logger.info("  Dashboard:   http://localhost:8000")
    logger.info("  API Docs:    http://localhost:8000/docs")
    logger.info("=" * 60)
