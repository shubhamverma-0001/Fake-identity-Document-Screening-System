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
#  Error Level Analysis (ELA) & CV Forensics
# ─────────────────────────────────────────────

def perform_ela_analysis(image_bytes: bytes, quality: int = 90) -> Dict[str, Any]:
    """
    Perform Error Level Analysis (ELA) to identify localized JPEG compression anomalies.
    Digitally edited or pasted regions (text/photo edits) compress at different rates
    than the original document background.
    """
    try:
        orig_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = orig_pil.size
        if w < 50 or h < 50:
            return {"ela_score": 0, "tampered_regions": [], "anomalies": []}

        # Save to JPEG buffer at quality
        buf = io.BytesIO()
        orig_pil.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        recompressed_pil = Image.open(buf).convert("RGB")

        orig_np = np.array(orig_pil, dtype=np.float32)
        recomp_np = np.array(recompressed_pil, dtype=np.float32)

        # Calculate absolute difference per pixel
        diff = np.abs(orig_np - recomp_np)
        diff_grayscale = np.mean(diff, axis=2)  # (H, W)

        mean_diff = float(np.mean(diff_grayscale))
        std_diff = float(np.std(diff_grayscale))
        max_diff = float(np.max(diff_grayscale))

        tampered_regions = []
        anomalies = []
        ela_score = 0

        # Divide into grid (e.g. 10x10) to find localized anomalies
        grid_rows, grid_cols = 8, 8
        cell_h, cell_w = h / grid_rows, w / grid_cols

        cell_means = []
        cells_info = []

        for r in range(grid_rows):
            for c in range(grid_cols):
                y1, y2 = int(r * cell_h), int((r + 1) * cell_h)
                x1, x2 = int(c * cell_w), int((c + 1) * cell_w)
                cell_diff = diff_grayscale[y1:y2, x1:x2]
                c_mean = float(np.mean(cell_diff))
                cell_means.append(c_mean)
                cells_info.append((r, c, x1, y1, x2 - x1, y2 - y1, c_mean))

        overall_cell_mean = np.mean(cell_means)
        overall_cell_std = np.std(cell_means)

        # Outlier grid cells indicate localized editing / pasting
        for r, c, x1, y1, cw, ch, c_mean in cells_info:
            if overall_cell_std > 0.5 and (c_mean - overall_cell_mean) > (2.2 * overall_cell_std) and c_mean > 8.0:
                x_pct = round((x1 / w) * 100, 1)
                y_pct = round((y1 / h) * 100, 1)
                w_pct = round((cw / w) * 100, 1)
                h_pct = round((ch / h) * 100, 1)

                tampered_regions.append({
                    "label": "ELA Editing Disparity",
                    "x": x_pct,
                    "y": y_pct,
                    "w": w_pct,
                    "h": h_pct,
                })

        if tampered_regions:
            ela_score = min(85, 30 + len(tampered_regions) * 15)
            anomalies.append({
                "type": "Manipulation",
                "description": f"Error Level Analysis (ELA) detected {len(tampered_regions)} region(s) with anomalous re-compression levels typical of localized digital photo or text editing.",
                "severity": "HIGH" if len(tampered_regions) >= 2 else "MEDIUM"
            })
        elif max_diff > 45 and std_diff > 12:
            ela_score = 35
            anomalies.append({
                "type": "Manipulation",
                "description": "High global ELA variance detected across image layers.",
                "severity": "MEDIUM"
            })

        return {
            "ela_score": ela_score,
            "mean_diff": round(mean_diff, 2),
            "std_diff": round(std_diff, 2),
            "max_diff": round(max_diff, 2),
            "tampered_regions": tampered_regions,
            "anomalies": anomalies,
        }
    except Exception as ex:
        return {"ela_score": 0, "tampered_regions": [], "anomalies": []}


def analyze_regional_noise(image_bytes: bytes) -> Dict[str, Any]:
    """
    Analyze high-frequency noise variance across document sub-regions.
    Pasted text or photo elements exhibit inconsistent noise variance relative to document card background.
    """
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"noise_score": 0, "anomalies": []}

        h, w = img.shape
        # Compute local noise using Laplacian
        lap = cv2.Laplacian(img, cv2.CV_64F)
        var = lap.var()

        anomalies = []
        noise_score = 0

        # Extremely uniform / zero noise across image can indicate synthetic digital template creation
        if var < 15.0:
            noise_score = 25
            anomalies.append({
                "type": "ImageQuality",
                "description": "Artificially low image noise variance detected — signature of synthetic digital template or heavy blur filter.",
                "severity": "MEDIUM"
            })

        return {"noise_score": noise_score, "var": round(var, 2), "anomalies": anomalies}
    except Exception:
        return {"noise_score": 0, "anomalies": []}



def analyze_document_layout_and_face(image_bytes: bytes, document_type: str) -> Tuple[int, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Perform local computer vision analysis on document layout, aspect ratio,
    header color palette, and portrait photo boundary insertion.
    """
    anomalies = []
    tampered_regions = []
    score = 0

    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return score, anomalies, tampered_regions

        h, w = img.shape[:2]
        aspect_ratio = round(w / float(h), 2)

        # 1. Aspect Ratio Verification for ID Cards
        if document_type.lower() in ["aadhaar", "pan", "driving_license"]:
            if aspect_ratio < 1.3 or aspect_ratio > 2.1:
                score += 25
                anomalies.append({
                    "type": "Alignment",
                    "description": f"Non-standard document aspect ratio ({aspect_ratio}:1). Standard Indian ID card aspect ratio is ~1.58:1.",
                    "severity": "MEDIUM"
                })

        # 2. Aadhaar Header Banner Color & Background Palette Check
        if document_type.lower() == "aadhaar":
            header = img[0:int(h * 0.25), :]
            if header.size > 0:
                h_hsv = cv2.cvtColor(header, cv2.COLOR_BGR2HSV)
                blue_mask = cv2.inRange(h_hsv, np.array([85, 30, 30]), np.array([135, 255, 255]))
                blue_pct = (np.count_nonzero(blue_mask) / float(header.shape[0] * header.shape[1])) * 100

                red_mask1 = cv2.inRange(h_hsv, np.array([0, 40, 40]), np.array([10, 255, 255]))
                red_mask2 = cv2.inRange(h_hsv, np.array([170, 40, 40]), np.array([180, 255, 255]))
                red_pct = ((np.count_nonzero(red_mask1) + np.count_nonzero(red_mask2)) / float(header.shape[0] * header.shape[1])) * 100

                if blue_pct < 1.5 and red_pct < 1.5:
                    score += 30
                    anomalies.append({
                        "type": "Security",
                        "description": "Mandatory UIDAI blue/cyan header banner background is missing or unverified.",
                        "severity": "HIGH"
                    })

        # 3. Face Detection & Portrait Photo Insertion Analysis
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if not os.path.exists(cascade_path):
            import site
            for sp in site.getsitepackages():
                candidate = os.path.join(sp, "cv2", "data", "haarcascade_frontalface_default.xml")
                if os.path.exists(candidate):
                    cascade_path = candidate
                    break

        if os.path.exists(cascade_path):
            face_cascade = cv2.CascadeClassifier(cascade_path)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)

            if len(faces) > 0:
                for (fx, fy, fw, fh) in faces:
                    x_pct = (fx / w) * 100
                    y_pct = (fy / h) * 100
                    w_pct = (fw / w) * 100
                    h_pct = (fh / h) * 100

                    y1, y2 = max(0, fy - 5), min(h, fy + fh + 5)
                    x1, x2 = max(0, fx - 5), min(w, fx + fw + 5)
                    face_roi = gray[y1:y2, x1:x2]
                    if face_roi.size > 0:
                        lap_face = cv2.Laplacian(face_roi, cv2.CV_64F).var()
                        if lap_face > 800:
                            score += 25
                            anomalies.append({
                                "type": "Photo",
                                "description": "High digital contrast/edge variance detected around portrait photo region (indicative of inserted photo).",
                                "severity": "HIGH"
                            })
                            tampered_regions.append({
                                "label": "Inserted Portrait Photo",
                                "x": round(x_pct, 1),
                                "y": round(y_pct, 1),
                                "w": round(w_pct, 1),
                                "h": round(h_pct, 1)
                            })

    except Exception:
        pass


    return score, anomalies, tampered_regions


# ─────────────────────────────────────────────
#  Image Preprocessing
# ─────────────────────────────────────────────


def preprocess_image(image_bytes: bytes, max_size: int = 1024) -> bytes:
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
    img.save(buf, format="JPEG", quality=85)
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
