# AI-Based Fake Identity & Document Screening System

A full-stack web application for the Smart India Hackathon (SIH) that uses Google Gemini Vision API to detect document forgery, tampering, and fake identities — with a premium admin dashboard UI.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python + FastAPI |
| Frontend | HTML5 + CSS3 (Vanilla, premium design) + JavaScript |
| AI Engine | Google Gemini Vision API (`gemini-1.5-pro-vision`) |
| Image Analysis | Pillow (PIL) + OpenCV for preprocessing |
| OCR | pytesseract (optional local extraction) |
| Storage | Local file system + JSON-based audit log |
| Config | `.env` file with `python-dotenv` |

---

## Project Structure

```
SIH/
├── backend/
│   ├── main.py               # FastAPI app entry point
│   ├── routes/
│   │   ├── screening.py      # Document upload & analysis endpoint
│   │   └── dashboard.py      # Dashboard data/audit log endpoints
│   ├── services/
│   │   ├── gemini_service.py # Gemini Vision API integration
│   │   └── image_service.py  # Preprocessing, highlight regions
│   ├── models/
│   │   └── schemas.py        # Pydantic models for request/response
│   ├── utils/
│   │   └── audit_log.py      # JSON-based audit logging
│   └── .env                  # GEMINI_API_KEY=...
├── frontend/
│   ├── index.html            # Main dashboard
│   ├── screen.html           # Document screening page
│   ├── report.html           # Detailed report view
│   ├── css/
│   │   └── styles.css        # Premium dark-mode design system
│   └── js/
│       ├── app.js            # Navigation, state management
│       ├── upload.js         # File upload, preview
│       └── results.js        # Render fraud score, highlights
└── uploads/                  # Temporary storage for uploaded docs
```

---

## Key Features & Pages

### 1. 📊 Admin Dashboard (`index.html`)
- Real-time stats: Total scans, fraud detected, pending reviews
- Recent screening history table with status badges
- Animated fraud rate gauge
- Navigation to screening and report pages

### 2. 🔍 Document Screening Page (`screen.html`)
- Drag-and-drop document upload (supports JPG, PNG, PDF)
- Document type selector (Aadhaar, Passport, PAN, DL)
- Live preview of uploaded document
- "Analyze Document" button → calls FastAPI backend

### 3. 📈 Results & Report View (`report.html`)
- **Fraud Risk Score**: Animated gauge (0–100%)
- **Side-by-side view**: Original image + highlighted anomaly regions
- **Anomaly breakdown**: Font inconsistency, pixel manipulation, alignment issues, metadata flags
- **Verdict**: GENUINE / SUSPICIOUS / FAKE with confidence level
- **Audit log entry**: Auto-saved with timestamp

---

## AI Analysis Flow

```
User Uploads Document
        ↓
Backend receives file (FastAPI)
        ↓
Image Preprocessing (Pillow/OpenCV)
  - Normalize, resize
  - Extract EXIF metadata
        ↓
Gemini Vision API Call
  - Structured prompt: detect forgery, font anomalies,
    pixel tampering, data inconsistency, alignment issues
  - Returns JSON: { risk_score, anomalies[], verdict, regions[] }
        ↓
Highlight Regions (OpenCV bounding boxes)
        ↓
Return to Frontend:
  - Risk score + verdict
  - Annotated image
  - Detailed anomaly list
        ↓
Display in Dashboard + Save to Audit Log
```

---

## Gemini Vision Prompt Strategy

The backend sends a carefully crafted structured prompt to Gemini:

```
You are a forensic document authentication expert. Analyze this [document_type] image for signs of forgery or tampering. 

Check for:
1. Font inconsistencies (mixed fonts, different sizes, pixel artifacts around text)
2. Image manipulation (clone stamp, healing brush, blur artifacts)  
3. Alignment and spacing irregularities
4. Watermark/security feature anomalies
5. Color and brightness inconsistencies
6. Text-background blending artifacts

Respond ONLY with valid JSON:
{
  "risk_score": 0-100,
  "verdict": "GENUINE|SUSPICIOUS|FAKE",
  "confidence": 0-100,
  "anomalies": [{"type": "...", "description": "...", "severity": "LOW|MEDIUM|HIGH"}],
  "tampered_regions": [{"label": "...", "x": %, "y": %, "w": %, "h": %}],
  "summary": "..."
}
```

---

## Proposed Changes

### Backend

#### [NEW] `backend/main.py`
FastAPI app, CORS setup, serve static files, include routers.

#### [NEW] `backend/routes/screening.py`
- `POST /api/screen` — accepts multipart file + doc_type, runs analysis, returns results
- `GET /api/history` — returns audit log entries

#### [NEW] `backend/services/gemini_service.py`
- Loads Gemini API key from `.env`
- Builds structured prompt based on document type
- Calls `google-generativeai` SDK
- Parses and validates JSON response

#### [NEW] `backend/services/image_service.py`
- Preprocesses image (resize, normalize)
- Extracts EXIF metadata for manipulation flags
- Draws bounding boxes on tampered regions (OpenCV)
- Returns base64-encoded annotated image

#### [NEW] `backend/.env`
```
GEMINI_API_KEY=your_key_here
```

#### [NEW] `backend/requirements.txt`
```
fastapi, uvicorn, python-dotenv, google-generativeai,
Pillow, opencv-python, pytesseract, python-multipart
```

### Frontend

#### [NEW] `frontend/index.html`
Premium dark-mode admin dashboard with stats cards, recent scans table, animated charts.

#### [NEW] `frontend/screen.html`
Document upload page with drag-and-drop, doc type selector, live preview.

#### [NEW] `frontend/report.html`
Results page: animated fraud score gauge, side-by-side image comparison, anomaly breakdown cards.

#### [NEW] `frontend/css/styles.css`
Full design system: dark theme, glassmorphism cards, gradient accents, smooth animations.

#### [NEW] `frontend/js/app.js`, `upload.js`, `results.js`
Frontend logic for upload, API calls, result rendering.

---

## Verification Plan

### Automated
- Run `uvicorn main:app --reload` and test `/api/screen` with sample documents via browser

### Manual Verification
- Upload a real vs. obviously tampered document and verify differing risk scores
- Check audit log is saved correctly
- Verify highlighted regions appear on the annotated image
- Test on multiple document types (Aadhaar, Passport, PAN, DL)

---

## Open Questions

> [!IMPORTANT]
> **Gemini API Key**: Please have your `GEMINI_API_KEY` ready to place in `backend/.env`. The system will not function without it.

> [!NOTE]
> **PDF Support**: For PDF documents, the first page will be extracted as an image for analysis. Full multi-page PDF analysis can be added as a follow-up feature.

> [!NOTE]
> **Tampered Region Highlighting**: Gemini returns percentage-based coordinates. OpenCV will draw colored bounding boxes on the uploaded image — exact pixel-level segmentation would require a dedicated fine-tuned model.
