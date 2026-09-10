"""
Google Gemini Vision API service for document forgery detection.
Uses the new google-genai SDK (google.genai).
"""
import os
import json
import re
import logging
from typing import Dict, Any

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash"

# ─────────────────────────────────────────────
#  Document-type specific context hints
# ─────────────────────────────────────────────

DOC_HINTS = {
    "aadhaar": (
        "This is an Indian Aadhaar Card. It should have: a 12-digit Aadhaar number, "
        "the UIDAI hologram/logo, the Indian government emblem, a QR code, the citizen's "
        "photo, name, DOB, and address in English and one regional language. "
        "The card has a standard blue-white gradient design."
    ),
    "passport": (
        "This is an Indian Passport. It should have: a navy blue cover, the Ashoka Pillar "
        "emblem, MRZ (Machine Readable Zone) lines at the bottom, the holder's photo, "
        "passport number, issue/expiry dates, and personal details."
    ),
    "pan": (
        "This is an Indian PAN Card (Permanent Account Number). It should have: "
        "a 10-character alphanumeric PAN number, the Income Tax Department logo, "
        "the holder's photo and signature, name, father's name, and date of birth."
    ),
    "driving_license": (
        "This is an Indian Driving License. It should have: the transport department logo, "
        "license number, holder's photo, name, address, DOB, blood group, "
        "vehicle categories, and validity dates."
    ),
    "other": (
        "This is an official government identity document. Analyze it for any signs of "
        "forgery, tampering, or inconsistencies with genuine government-issued documents."
    ),
}

# ─────────────────────────────────────────────
#  Prompt Builder
# ─────────────────────────────────────────────

def build_prompt(document_type: str) -> str:
    hint = DOC_HINTS.get(document_type.lower(), DOC_HINTS["other"])
    return f"""You are a senior forensic document authentication expert with 20 years of experience 
detecting forged and tampered identity documents for law enforcement agencies.

Document Context: {hint}

Carefully analyze this document image for ALL of the following:

1. **Font Analysis**: Look for inconsistent fonts, mixed typefaces, incorrect character spacing, 
   pixelation around text edges, or fonts that don't match genuine templates.

2. **Image Manipulation**: Detect clone stamp artifacts, healing brush marks, blur/sharpen halos, 
   JPEG compression artifacts in localized areas, inconsistent noise patterns.

3. **Alignment & Layout**: Check for misaligned text, incorrect margins, skewed elements, 
   off-center logos, or spacing that doesn't match genuine templates.

4. **Security Features**: Assess the authenticity of holograms, watermarks, seals, QR codes, 
   MRZ lines, and government emblems.

5. **Photo Integrity**: Check if the face photo appears genuine, consistent background, 
   no digital insertion artifacts, correct aspect ratio for the document type.

6. **Color & Lighting**: Identify unnatural color gradients, inconsistent lighting, 
   shadows that don't match, or color bleeding between elements.

7. **Data Consistency**: Cross-check visible dates, numbers, and codes for logical consistency 
   (e.g., issue date before expiry, age matching DOB).

Based on your analysis, respond ONLY with a valid JSON object (no markdown, no explanation outside JSON):

{{
  "risk_score": <integer 0-100, where 0=certainly genuine, 100=certainly fake>,
  "verdict": "<GENUINE|SUSPICIOUS|FAKE>",
  "confidence": <integer 0-100>,
  "anomalies": [
    {{
      "type": "<category: Font|Manipulation|Alignment|Security|Photo|Color|DataConsistency>",
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
  "summary": "<2-3 sentence expert summary of findings>"
}}

    Rules:
    - Standard photographs, mobile camera uploads, scans, and compressed images are NORMAL for genuine documents.
    - Do NOT mark a document as FAKE or SUSPICIOUS simply due to JPEG compression, camera angle, glare, or scan resolution.
    - Only declare FAKE if there is clear, undeniable visual evidence of deliberate text editing (e.g., altered digits, mismatched typefaces, digitally pasted text/photo).
    - If the document looks authentic and consistent with a real government ID, assign risk_score 0-15 and verdict GENUINE.
    - risk_score 0-20 → GENUINE, 21-60 → SUSPICIOUS, 61-100 → FAKE
    - tampered_regions should only include areas with clear HIGH or MEDIUM severity anomalies.
    """


CANDIDATE_MODELS = [
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
]


def analyze_document(image_bytes: bytes, document_type: str) -> Dict[str, Any]:
    """
    Send the document image to Gemini Vision API for forensic analysis.
    Returns a parsed dict with risk_score, verdict, anomalies, etc.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        raise ValueError(
            "GEMINI_API_KEY is not set. Please add your API key to backend/.env"
        )

    # Initialize the new google-genai client
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = build_prompt(document_type)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

    last_error = None
    response = None

    for model in CANDIDATE_MODELS:
        try:
            logger.info(f"Attempting analysis with model: {model}")
            response = client.models.generate_content(
                model=model,
                contents=[prompt, image_part],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                ),
            )
            if response and response.text:
                logger.info(f"Successfully generated response using model: {model}")
                break
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
            last_error = e

    if not response or not response.text:
        raise ValueError(f"All Gemini models failed. Last error: {last_error}")

    raw_text = response.text.strip()
    logger.info(f"Gemini raw response: {raw_text[:300]}...")

    # Extract JSON — strip any accidental markdown fences
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if not json_match:
        raise ValueError(f"Gemini did not return valid JSON. Response: {raw_text[:200]}")

    result = json.loads(json_match.group())

    # Validate and sanitize fields
    result["risk_score"] = max(0, min(100, int(result.get("risk_score", 50))))
    result["confidence"]  = max(0, min(100, int(result.get("confidence", 70))))
    result["verdict"]     = result.get("verdict", "SUSPICIOUS").upper()
    if result["verdict"] not in ("GENUINE", "SUSPICIOUS", "FAKE"):
        result["verdict"] = "SUSPICIOUS"
    result.setdefault("anomalies", [])
    result.setdefault("tampered_regions", [])
    result.setdefault("summary", "Analysis complete.")

    return result
