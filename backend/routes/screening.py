"""
Document screening API route.
Handles file upload, AI analysis, image annotation, and audit logging.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import asyncio

from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse

from services.gemini_service import analyze_document
from services.image_service import (
    preprocess_image,
    extract_exif_flags,
    annotate_image,
    image_to_base64,
)
from utils.audit_log import append_entry

router = APIRouter(prefix="/api", tags=["screening"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/screen")
async def screen_document(
    file: UploadFile = File(...),
    document_type: str = Form("other"),
):
    """
    Upload a document image and receive a full forgery analysis report.
    """
    # ── Validate file ──────────────────────────────────────────────────
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Please upload JPG, PNG, or WebP.",
        )

    raw_bytes = await file.read()
    file_size_kb = round(len(raw_bytes) / 1024, 1)

    if file_size_kb > MAX_FILE_SIZE_MB * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file_size_kb} KB). Maximum allowed is {MAX_FILE_SIZE_MB} MB.",
        )

    scan_id = str(uuid.uuid4())[:8].upper()
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        # ── Preprocessing (offloaded to threadpool) ───────────────────
        original_b64 = image_to_base64(raw_bytes)
        exif_flags = await asyncio.to_thread(extract_exif_flags, raw_bytes)
        processed_bytes = await asyncio.to_thread(preprocess_image, raw_bytes)

        # ── AI Analysis (offloaded to threadpool) ─────────────────────
        logger.info(f"[{scan_id}] Sending to Gemini — doc_type={document_type}, size={file_size_kb}KB")
        ai_result = await asyncio.to_thread(analyze_document, processed_bytes, document_type, exif_flags)

        # ── Annotate Image (offloaded to threadpool) ──────────────────
        annotated_bytes = await asyncio.to_thread(
            annotate_image,
            processed_bytes,
            ai_result.get("tampered_regions", []),
            ai_result.get("anomalies", []),
            ai_result["verdict"],
            ai_result["risk_score"],
        )
        annotated_b64 = image_to_base64(annotated_bytes)

        # ── Build Response ─────────────────────────────────────────────
        result = {
            "scan_id": scan_id,
            "document_type": document_type,
            "timestamp": timestamp,
            "risk_score": ai_result["risk_score"],
            "verdict": ai_result["verdict"],
            "confidence": ai_result["confidence"],
            "anomalies": ai_result.get("anomalies", []),
            "tampered_regions": ai_result.get("tampered_regions", []),
            "summary": ai_result.get("summary", ""),
            "annotated_image_b64": annotated_b64,
            "original_image_b64": original_b64,
            "file_name": file.filename,
            "file_size_kb": file_size_kb,
            "exif_flags": exif_flags,
        }

        # ── Audit Log ──────────────────────────────────────────────────
        log_entry = {k: v for k, v in result.items()
                     if k not in ("annotated_image_b64", "original_image_b64")}
        append_entry(log_entry)

        logger.info(
            f"[{scan_id}] Done — verdict={result['verdict']}, risk={result['risk_score']}"
        )
        return JSONResponse(content=result)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(f"[{scan_id}] Unexpected error during analysis")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
