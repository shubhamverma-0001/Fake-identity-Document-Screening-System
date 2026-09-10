"""
Dashboard API routes.
Provides statistics and audit history for the admin dashboard.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from utils.audit_log import get_all_entries, get_stats

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats():
    """Return aggregate statistics for the dashboard overview cards."""
    return JSONResponse(content=get_stats())


@router.get("/history")
async def get_scan_history():
    """Return the full screening history (newest first, max 500 entries)."""
    return JSONResponse(content={"history": get_all_entries()})


