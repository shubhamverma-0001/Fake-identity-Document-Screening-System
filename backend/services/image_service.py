"""
Image preprocessing and annotation service.
Handles EXIF metadata extraction, image normalization,
and drawing bounding boxes on tampered regions.
"""
import io
import base64
import os
from typing import List, Dict, Any, Tuple

import cv2
import numpy as np
from PIL import Image, ExifTags


# ─────────────────────────────────────────────
#  EXIF Metadata Analysis
# ─────────────────────────────────────────────

SUSPICIOUS_SOFTWARE = [
    "photoshop", "gimp", "affinity", "pixlr", "canva",
    "lightroom", "paint.net", "snapseed", "facetune",
]


def extract_exif_flags(image_bytes: bytes) -> List[str]:
    """Extract EXIF metadata and return a list of suspicious flags."""
    flags = []
    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif_data = img._getexif()
        if exif_data is None:
            flags.append("No EXIF metadata found — possible re-save or screenshot")
            return flags

        tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif_data.items()}

        # Check for editing software
        software = str(tag_map.get("Software", "")).lower()
        for s in SUSPICIOUS_SOFTWARE:
            if s in software:
                flags.append(f"Edited with image software: {tag_map.get('Software')}")
                break

        # Check for mismatched make/model
        make = tag_map.get("Make", "")
        model = tag_map.get("Model", "")
        if not make and not model:
            flags.append("Camera make/model missing — possible digital creation")

        # Check for unusual DateTime
        dt_orig = tag_map.get("DateTimeOriginal")
        dt_mod = tag_map.get("DateTime")
        if dt_orig and dt_mod and dt_orig != dt_mod:
            flags.append(f"Modification date differs from capture date ({dt_orig} vs {dt_mod})")

    except Exception:
        flags.append("Could not parse EXIF data — file may be manipulated")

    return flags


# ─────────────────────────────────────────────
#  Image Preprocessing
# ─────────────────────────────────────────────

def preprocess_image(image_bytes: bytes, max_size: int = 2048) -> bytes:
    """
    Resize image to max_size on the longest dimension while preserving aspect ratio.
    Returns JPEG bytes suitable for Gemini API.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def image_to_base64(image_bytes: bytes) -> str:
    """Convert raw image bytes to base64 string (data URI ready)."""
    return base64.b64encode(image_bytes).decode("utf-8")


# ─────────────────────────────────────────────
#  Annotated Image — Draw Tampered Regions
# ─────────────────────────────────────────────

SEVERITY_COLORS = {
    "HIGH":   (0,   50,  255),   # Red (BGR)
    "MEDIUM": (0,   165, 255),   # Orange
    "LOW":    (0,   255, 200),   # Teal/Green
}

VERDICT_OVERLAY = {
    "FAKE":       (0,   0,   200),
    "SUSPICIOUS": (0,   140, 255),
    "GENUINE":    (0,   200, 80),
}


def annotate_image(
    image_bytes: bytes,
    tampered_regions: List[Dict[str, Any]],
    anomalies: List[Dict[str, Any]],
    verdict: str,
    risk_score: int,
) -> bytes:
    """
    Draw colored bounding boxes on tampered regions.
    Returns annotated image as JPEG bytes.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes

    h, w = img.shape[:2]

    # Draw semi-transparent dark overlay for header
    overlay = img.copy()

    # Draw bounding boxes for each tampered region
    for i, region in enumerate(tampered_regions):
        try:
            x = int(region.get("x", 0) / 100 * w)
            y = int(region.get("y", 0) / 100 * h)
            bw = int(region.get("w", 0) / 100 * w)
            bh = int(region.get("h", 0) / 100 * h)

            # Get severity color if available
            severity = "HIGH"
            if i < len(anomalies):
                severity = anomalies[i].get("severity", "HIGH")
            color = SEVERITY_COLORS.get(severity, (0, 50, 255))

            # Filled transparent rect
            sub = overlay[max(0,y):min(h,y+bh), max(0,x):min(w,x+bw)]
            colored_rect = np.zeros_like(sub)
            colored_rect[:] = color
            cv2.addWeighted(colored_rect, 0.3, sub, 0.7, 0, sub)
            overlay[max(0,y):min(h,y+bh), max(0,x):min(w,x+bw)] = sub

            # Border
            cv2.rectangle(img, (x, y), (x + bw, y + bh), color, 2)
            # Label
            label = region.get("label", f"Region {i+1}")
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(img, (x, y - lh - 8), (x + lw + 6, y), color, -1)
            cv2.putText(img, label, (x + 3, y - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        except Exception:
            continue

    # Blend overlay
    cv2.addWeighted(overlay, 0.25, img, 0.75, 0, img)

    # Verdict banner at bottom
    banner_h = 48
    verdict_color = VERDICT_OVERLAY.get(verdict, (100, 100, 100))
    banner = np.zeros((banner_h, w, 3), dtype=np.uint8)
    banner[:] = verdict_color
    banner_text = f"  VERDICT: {verdict}   |   RISK SCORE: {risk_score}/100"
    cv2.putText(banner, banner_text, (10, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    img = np.vstack([img, banner])

    # Encode
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()
