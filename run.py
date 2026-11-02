"""
CustomerIQ — Customer Segmentation & Intelligence Platform
Application Launcher
============================================================
Run:
    python run.py
    python run.py --port 5000 --host 127.0.0.1
"""

import argparse
import sys
from pathlib import Path

# Ensure the project directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CustomerIQ Web Application Launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    print("=" * 70)
    print("  CustomerIQ — Customer Segmentation & Intelligence Platform")
    print(f"  Server URL: http://{args.host}:{args.port}")
    print("  RFM + K-Means Clustering Machine Learning Engine")
    print("=" * 70)

    app.run(host=args.host, port=args.port, debug=args.debug)
