"""
Document screening API route.
Handles file upload, AI analysis, image annotation, face liveness & identity matching, and audit logging.
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
from services.face_service import verify_liveness_and_identity
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
    live_file: Optional[UploadFile] = File(None),
    document_type: str = Form("other"),
):
    """
    Upload a document image and receive a full forgery analysis report.
    Optionally include a live camera selfie (`live_file`) for Face Liveness & Identity Verification.
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

    # Validate live selfie file if provided
    live_bytes = None
    if live_file and live_file.filename:
        if live_file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported live selfie type: {live_file.content_type}. Upload JPG, PNG, or WebP.",
            )
        live_bytes = await live_file.read()

    scan_id = str(uuid.uuid4())[:8].upper()
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        # ── Preprocessing (offloaded to threadpool) ───────────────────
        original_b64 = image_to_base64(raw_bytes)
        exif_flags = await asyncio.to_thread(extract_exif_flags, raw_bytes)
        processed_bytes = await asyncio.to_thread(preprocess_image, raw_bytes)

        # ── AI Document Analysis (offloaded to threadpool) ─────────────
        logger.info(f"[{scan_id}] Sending to Gemini — doc_type={document_type}, size={file_size_kb}KB")
        ai_result = await asyncio.to_thread(analyze_document, processed_bytes, document_type, exif_flags)

        # ── Face Liveness & Identity Matching (if selfie provided) ──────
        face_verification = None
        if live_bytes:
            logger.info(f"[{scan_id}] Running Face Liveness & Identity Matching...")
            face_verification = await asyncio.to_thread(
                verify_liveness_and_identity,
                raw_bytes,
                live_bytes,
                document_type
            )
            # Factor face liveness and identity match into document risk score if suspicious
            if face_verification:
                if not face_verification.get("is_live", True):
                    ai_result["anomalies"].append({
                        "type": "FaceLiveness",
                        "description": f"Face Anti-Spoofing Failure: {face_verification.get('liveness_details')}",
                        "severity": "HIGH"
                    })
                    ai_result["risk_score"] = min(100, ai_result["risk_score"] + 35)
                if face_verification.get("match_verdict") == "MISMATCH":
                    ai_result["anomalies"].append({
                        "type": "IdentityMatch",
                        "description": f"Face Identity Mismatch: Live selfie does not match document photo ({face_verification.get('match_score')}% similarity)",
                        "severity": "HIGH"
                    })
                    ai_result["risk_score"] = min(100, ai_result["risk_score"] + 45)

                if ai_result["risk_score"] >= 60:
                    ai_result["verdict"] = "FAKE"
                elif ai_result["risk_score"] >= 25 and ai_result["verdict"] == "GENUINE":
                    ai_result["verdict"] = "SUSPICIOUS"

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
            "face_verification": face_verification,
        }

        # ── Audit Log ──────────────────────────────────────────────────
        log_entry = {
            k: v for k, v in result.items()
            if k not in ("annotated_image_b64", "original_image_b64")
        }
        if log_entry.get("face_verification"):
            # Strip base64 face crops from persistent audit log file to keep log compact
            fv = dict(log_entry["face_verification"])
            fv.pop("doc_face_b64", None)
            fv.pop("live_face_b64", None)
            log_entry["face_verification"] = fv

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


@router.post("/liveness-match")
async def standalone_liveness_match(
    document_file: UploadFile = File(...),
    live_file: UploadFile = File(...),
    document_type: str = Form("other"),
):
    """
    Standalone API endpoint to verify Face Liveness and Identity Match between an ID document and a live selfie.
    """
    if document_file.content_type not in ALLOWED_TYPES or live_file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Images must be JPG, PNG, or WebP format.")

    doc_bytes = await document_file.read()
    live_bytes = await live_file.read()

    try:
        verification = await asyncio.to_thread(
            verify_liveness_and_identity,
            doc_bytes,
            live_bytes,
            document_type
        )
        return JSONResponse(content=verification)
    except Exception as e:
        logger.exception("Error in standalone liveness match")
        raise HTTPException(status_code=500, detail=f"Face verification failed: {str(e)}")

