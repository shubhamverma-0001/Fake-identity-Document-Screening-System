"""
Audit logging utilities for document screening events.
Stores results in a local JSON file for dashboard history.
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any

AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_FILE", "audit_log.json")


def _load_log() -> List[Dict[str, Any]]:
    """Load existing audit log entries from disk."""
    if not os.path.exists(AUDIT_LOG_PATH):
        return []
    try:
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_log(entries: List[Dict[str, Any]]) -> None:
    """Persist audit log entries to disk."""
    with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, default=str)


def append_entry(entry: Dict[str, Any]) -> None:
    """Append a new screening result to the audit log."""
    entries = _load_log()
    entries.insert(0, entry)  # newest first
    # Keep only the last 500 entries to prevent unbounded growth
    _save_log(entries[:500])


def get_all_entries() -> List[Dict[str, Any]]:
    """Retrieve all audit log entries (newest first)."""
    return _load_log()


def get_stats() -> Dict[str, Any]:
    """Calculate dashboard statistics from the audit log."""
    entries = _load_log()
    total = len(entries)
    genuine = sum(1 for e in entries if e.get("verdict") == "GENUINE")
    suspicious = sum(1 for e in entries if e.get("verdict") == "SUSPICIOUS")
    fake = sum(1 for e in entries if e.get("verdict") == "FAKE")

    fraud_count = suspicious + fake
    fraud_rate = round((fraud_count / total * 100), 1) if total > 0 else 0.0

    recent = entries[:10]  # last 10 scans for dashboard table

    return {
        "total_scans": total,
        "genuine_count": genuine,
        "suspicious_count": suspicious,
        "fake_count": fake,
        "fraud_rate": fraud_rate,
        "recent_scans": recent,
    }
