from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class AnomalyItem(BaseModel):
    type: str
    description: str
    severity: str  # LOW | MEDIUM | HIGH


class TamperedRegion(BaseModel):
    label: str
    x: float  # percentage (0-100)
    y: float
    w: float
    h: float


class ScreeningResult(BaseModel):
    scan_id: str
    document_type: str
    timestamp: str
    risk_score: int           # 0–100
    verdict: str              # GENUINE | SUSPICIOUS | FAKE
    confidence: int           # 0–100
    anomalies: List[AnomalyItem]
    tampered_regions: List[TamperedRegion]
    summary: str
    annotated_image_b64: Optional[str] = None   # base64 annotated image
    original_image_b64: Optional[str] = None    # base64 original image
    file_name: str
    file_size_kb: float
    exif_flags: List[str] = []


class ScreeningRequest(BaseModel):
    document_type: str


class DashboardStats(BaseModel):
    total_scans: int
    genuine_count: int
    suspicious_count: int
    fake_count: int
    fraud_rate: float
    recent_scans: List[dict]
