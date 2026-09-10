"""
DocShield AI — Portable App Launcher
Launches the local FastAPI server and opens the browser automatically.
"""
import os
import sys
import time
import webbrowser
import threading
import uvicorn

# Add backend directory to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Set working directory to backend
os.chdir(backend_dir)

from main import app


def open_browser():
    time.sleep(1.8)
    print("\n[DocShield AI] Server ready! Opening browser at http://localhost:8000 ...\n")
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    print("=" * 60)
    print("  DocShield AI — Starting Document Forensics System")
    print("  URL: http://localhost:8000")
    print("=" * 60)

    # Launch browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Start FastAPI server
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
