import os
import io
import json
import re
import logging
from typing import Dict, Any, List, Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv
import cv2
import numpy as np
from PIL import Image

from services.image_service import (
    perform_ela_analysis, 
    analyze_regional_noise,
    analyze_document_layout_and_face,
)

from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY") or 
    os.getenv("GOOGLE_API_KEY") or 
    os.getenv("GEMINI_KEY") or ""
).strip().strip('"').strip("'")
MODEL_NAME = "gemini-3.5-flash"

# ─────────────────────────────────────────────
#  Document-type specific context hints
# ─────────────────────────────────────────────

DOC_HINTS = {
    "aadhaar": (
        "This is an Indian Aadhaar Card (UIDAI). Authentic forms include physical PVC smart cards, "
        "e-Aadhaar printed letters, and digital Aadhaar slips. It contains a 12-digit Aadhaar number, "
        "UIDAI emblem/logo, QR code, photo, name, DOB, and address. Regional language text alongside English is standard."
    ),
    "passport": (
        "This is an Indian Passport. Authentic forms include standard navy blue passport booklets and official passports. "
        "It contains the Ashoka Pillar emblem, holder's portrait, passport number, issue/expiry dates, "
        "and Machine Readable Zone (MRZ) lines at the bottom."
    ),
    "pan": (
        "This is an Indian PAN Card (Permanent Account Number). Authentic forms include traditional blue-header cards, "
        "newer QR-code PVC cards, and NSDL/UTIITSL e-PAN documents. It contains a 10-character alphanumeric PAN number "
        "(e.g., ABCDE1234F), Income Tax Department emblem, holder's photo, signature, name, father's name, and DOB."
    ),
    "driving_license": (
        "This is an Indian Driving License issued by a State Transport Department or Sarathi Parivahan portal / DigiLocker. "
        "Authentic formats include smart cards, laminated paper cards, and DigiLocker / mParivahan digital DL exports. "
        "DL numbers may contain slashes, hyphens, or spaces (e.g., DL-0420110012345, MH12 20180012345, KA01/2020/0001234, TN-01-20150012345). "
        "CRITICAL PHOTO & TEXT FORENSIC CHECK: Carefully inspect BOTH the holder portrait photo box and text fields. "
        "If the portrait photo has been digitally swapped, pasted over the original frame, cropped from a separate photo, "
        "or shows boundary line mismatch, pixelation discrepancy, or painted text boxes, YOU MUST MARK IT `FAKE` (risk_score 70 to 100) "
        "and pinpoint the exact tampered_regions."
    ),
    "other": (
        "This is an official government identity document. Analyze it for any genuine signs of "
        "forgery, digital tampering, text alteration, or photo replacement."
    ),
}

# ─────────────────────────────────────────────
#  Prompt Builder
# ─────────────────────────────────────────────

def build_prompt(document_type: str, exif_flags: Optional[List[str]] = None) -> str:
    hint = DOC_HINTS.get(document_type.lower(), DOC_HINTS["other"])
    exif_text = ""
    if exif_flags:
        sw_flags = [f for f in exif_flags if any(s in f.lower() for s in ["photoshop", "gimp", "canva", "pixlr", "edited"])]
        if sw_flags:
            exif_text = "\nEXIF Metadata Analysis Warnings:\n" + "\n".join([f"- {f}" for f in sw_flags])

    return f"""You are a senior forensic document authentication expert with 20 years of experience 
authenticating government identity documents for law enforcement agencies.

Document Context: {hint}
{exif_text}

MANDATORY FORENSIC EVALUATION INSTRUCTIONS:
1. **Evaluating Genuine Documents**:
   - Indian government identity documents (Aadhaar, Driving License, PAN, Passport) exist in many legitimate regional formats, state layouts, PVC smart cards, and digital DigiLocker e-card printouts.
   - If the document is an authentic state or central government issued identity document with consistent font typography, authentic portrait photo placement, valid layout, and NO signs of digital image editing, text alteration, or photo replacement, YOU MUST ASSIGN verdict `GENUINE` (risk_score 0 to 15).

2. **Detecting Digital Forgeries, Text Alterations & Photo Replacement**:
   - Assign `FAKE` (risk_score 65 to 100) or `SUSPICIOUS` (risk_score 35 to 60) if ANY of the following digital alterations exist:
     a) **Photo Box Replacement / Splicing**: The portrait photo is digitally pasted, swapped, replaced with a selfie, shows sharp box boundary cuts, or has resolution/lighting mismatch with the document canvas.
     b) **Text Field Alteration**: Re-typed text with mismatched font families, pixelated font overlays, or inconsistent font sizes.
     c) **Paint Box / Erasure**: Rectangular white/grey background patches drawn over original text or photo regions to overwrite details.
     d) **Fabricated Template**: Completely fake mock-up cards lacking official government logos or security features.
   - If fake/altered, pinpoint tampered_regions with percentages [x, y, w, h].

Respond ONLY with a valid JSON object (no markdown explanation outside JSON):

{{
  "risk_score": <integer 0-100, where 0=certainly genuine, 100=certainly fake>,
  "verdict": "<GENUINE|SUSPICIOUS|FAKE>",
  "confidence": <integer 0-100>,
  "anomalies": [
    {{
      "type": "<category: Font|Manipulation|Alignment|Security|Photo|Color|DataConsistency|Metadata>",
      "description": "<specific, detailed description of the anomaly>",
      "severity": "<LOW|MEDIUM|HIGH>"
    }}
  ],
  "tampered_regions": [
    {{
      "label": "<short label for the region>",
      "x": <left edge as % of image width, 0-100>,
      "y": <top edge as % of image height, 0-100>,
      "w": <width as % of image width, 0-100>,
      "h": <height as % of image height, 0-100>
    }}
  ],
  "summary": "<2-3 sentence expert forensic summary of findings>"
}}

    Rules:
    - risk_score calibration: 0-24 → GENUINE, 25-59 → SUSPICIOUS, 60-100 → FAKE.
    - Be objective. Authentic state identity cards MUST be evaluated as GENUINE (risk_score 0-15).
    """


CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
]


def _safe_int(val: Any, default: int = 50) -> int:
    try:
        if isinstance(val, (int, float)):
            return max(0, min(100, int(val)))
        if isinstance(val, str):
            digits = re.sub(r"[^\d]", "", val)
            if digits:
                return max(0, min(100, int(digits)))
            v_lower = val.lower()
            if "high" in v_lower: return 90
            if "med" in v_lower: return 60
            if "low" in v_lower: return 30
    except Exception:
        pass
    return default


def generate_local_forensic_report(
    image_bytes: bytes, 
    document_type: str, 
    exif_flags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Local computer vision & ELA forensic analysis engine fallback.
    Accurately evaluates ELA, layout structure, and EXIF software flags.
    """
    anomalies = []
    tampered_regions = []
    risk_score = 5  # Baseline score for genuine scan

    # 1. EXIF Metadata Software Penalties (ignore missing EXIF)
    if exif_flags:
        for flag in exif_flags:
            flag_lower = flag.lower()
            if any(sw in flag_lower for sw in ["photoshop", "canva", "gimp", "pixlr", "paint.net", "edited with"]):
                anomalies.append({
                    "type": "Metadata",
                    "description": f"EXIF metadata indicates file was processed with editing software: {flag}",
                    "severity": "HIGH"
                })
                risk_score += 45

    # 2. Error Level Analysis (ELA)
    ela_res = perform_ela_analysis(image_bytes, quality=90)
    e_score = ela_res.get("ela_score", 0)
    if e_score >= 35:
        tampered_regions.extend(ela_res.get("tampered_regions", []))
        anomalies.extend(ela_res.get("anomalies", []))
        if e_score >= 70:
            risk_score = max(risk_score, 65)
        else:
            risk_score = max(risk_score, 35)

    # 3. Document Layout & Aspect Ratio Analysis
    layout_score, layout_anomalies, layout_regions = analyze_document_layout_and_face(image_bytes, document_type)
    if layout_score > 0:
        anomalies.extend(layout_anomalies)
        tampered_regions.extend(layout_regions)
        risk_score = max(risk_score, 30)

    # 4. Noise Variance Analysis
    noise_res = analyze_regional_noise(image_bytes)
    if noise_res.get("noise_score", 0) > 0:
        anomalies.extend(noise_res.get("anomalies", []))

    # Ensure bounds
    risk_score = max(0, min(100, risk_score))

    if risk_score >= 60:
        verdict = "FAKE"
    elif risk_score >= 25:
        verdict = "SUSPICIOUS"
    else:
        verdict = "GENUINE"

    summary = (
        f"Local forensic computer vision scan completed for {document_type.upper()}. "
        f"Analyzed JPEG Error Level Analysis (ELA) and layout structure. "
        f"Verdict: {verdict} (Risk Score: {risk_score}/100)."
    )

    return {
        "risk_score": risk_score,
        "verdict": verdict,
        "confidence": 92 if verdict == "GENUINE" else 85,
        "anomalies": anomalies,
        "tampered_regions": tampered_regions,
        "summary": summary
    }


def analyze_document(
    image_bytes: bytes, 
    document_type: str, 
    exif_flags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Send the document image to Gemini Vision API for forensic analysis.
    Falls back gracefully to multi-signal local computer vision engine if cloud API is delayed.
    """
    api_key = (
        os.getenv("GEMINI_API_KEY") or 
        os.getenv("GOOGLE_API_KEY") or 
        os.getenv("GEMINI_KEY") or ""
    ).strip().strip('"').strip("'")

    if not api_key or api_key == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY not configured. Using local computer vision forensic engine.")
        return generate_local_forensic_report(image_bytes, document_type, exif_flags)

    try:
        client = genai.Client(api_key=api_key, http_options={"timeout": 30000})

        prompt = build_prompt(document_type, exif_flags)
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        response = None
        for model in CANDIDATE_MODELS:
            try:
                logger.info(f"Attempting analysis with model: {model}")
                response = client.models.generate_content(
                    model=model,
                    contents=[prompt, image_part],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=1024,
                        response_mime_type="application/json",
                    ),
                )
                if response and response.text:
                    logger.info(f"Successfully generated response using model: {model}")
                    break
            except Exception as e:
                logger.warning(f"Model {model} attempt failed: {e}")
                continue

        if not response or not response.text:
            logger.warning("All cloud models timed out/failed. Switching to local vision engine.")
            return generate_local_forensic_report(image_bytes, document_type, exif_flags)

        raw_text = response.text.strip()
        logger.info(f"Gemini raw response: {raw_text[:200]}...")

        # Extract JSON robustly
        cleaned_text = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text).strip()
        cleaned_text = re.sub(r",\s*([\]}])", r"\1", cleaned_text) # strip trailing commas

        try:
            result = json.loads(cleaned_text, strict=False)
        except Exception:
            json_match = re.search(r"\{[\s\S]*\}", cleaned_text)
            if json_match:
                try:
                    match_str = re.sub(r",\s*([\]}])", r"\1", json_match.group())
                    result = json.loads(match_str, strict=False)
                except Exception:
                    return generate_local_forensic_report(image_bytes, document_type, exif_flags)
            else:
                return generate_local_forensic_report(image_bytes, document_type, exif_flags)

        # Validate and sanitize fields safely
        raw_score = _safe_int(result.get("risk_score"), 10)
        v = str(result.get("verdict", "")).upper()

        if "FAKE" in v or raw_score >= 60:
            result["verdict"] = "FAKE"
            result["risk_score"] = max(60, raw_score)
        elif "SUSPICIOUS" in v or raw_score >= 25:
            result["verdict"] = "SUSPICIOUS"
            result["risk_score"] = max(25, raw_score)
        else:
            result["verdict"] = "GENUINE"
            result["risk_score"] = min(20, raw_score)

        result["confidence"] = _safe_int(result.get("confidence"), 90)
        result.setdefault("anomalies", [])
        result.setdefault("tampered_regions", [])
        result.setdefault("summary", "Document screening analysis completed.")

        # Post-process: Cross-check local CV layout anomalies
        l_score, l_anomalies, l_regions = analyze_document_layout_and_face(image_bytes, document_type)
        if l_score > 0:
            for la in l_anomalies:
                if not any(la["type"] in a.get("type", "") for a in result["anomalies"]):
                    result["anomalies"].append(la)
            for lr in l_regions:
                if not any(lr["label"] in tr.get("label", "") for tr in result["tampered_regions"]):
                    result["tampered_regions"].append(lr)

        # Post-process: Include localized ELA anomalies if detected by computer vision
        ela_res = perform_ela_analysis(image_bytes, quality=90)
        e_score = ela_res.get("ela_score", 0)
        if e_score >= 35:
            for r in ela_res.get("tampered_regions", []):
                if not any(r["label"] in tr.get("label", "") for tr in result["tampered_regions"]):
                    result["tampered_regions"].append(r)
            for a in ela_res.get("anomalies", []):
                if not any(a["type"] in an.get("type", "") for an in result["anomalies"]):
                    result["anomalies"].append(a)

            # High confidence localized ELA editing disparity (multiple tampered cells)
            if e_score >= 50:
                result["risk_score"] = min(100, max(result["risk_score"], e_score))
                result["verdict"] = "FAKE"
            elif e_score >= 35:
                result["risk_score"] = min(100, max(result["risk_score"], 40))
                if result["verdict"] == "GENUINE":
                    result["verdict"] = "SUSPICIOUS"

        # Post-process EXIF software warnings if present
        if exif_flags:
            for flag in exif_flags:
                if any(sw in flag.lower() for sw in ["photoshop", "canva", "gimp", "pixlr", "paint.net", "edited with"]):
                    if not any("Metadata" in a.get("type", "") or "software" in a.get("description", "").lower() for a in result["anomalies"]):
                        result["anomalies"].append({
                            "type": "Metadata",
                            "description": f"EXIF metadata indicates file was processed with editing software: {flag}",
                            "severity": "HIGH"
                        })
                    result["risk_score"] = min(100, max(result["risk_score"], 65))
                    result["verdict"] = "FAKE"

        return result

    except Exception as ex:
        logger.warning(f"Gemini API execution error: {ex}. Using local forensic engine.")
        return generate_local_forensic_report(image_bytes, document_type, exif_flags)
