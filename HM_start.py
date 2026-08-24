"""
HM AI 4.0 — Primary Autonomous System Launcher (hm_start.py).
Launches the autonomous multi-asset trading engine, Quality Gate decision matrix, self-learning database, and Remote Access Web Terminal.
"""
import os
import sys
import time
import threading
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from jarvis.application.orchestrator import JarvisOrchestrator
from jarvis.api.server import run_web_server
from jarvis.api.remote_auth import ADMIN_USERNAME, DEFAULT_PASS_RAW

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("HM_START")

def hm_start(mode: str = "live", port: int = 8501, host: str = "0.0.0.0"):
    print("=" * 95)
    print("                 HM AI 4.0 — INSTITUTIONAL QUANTITATIVE TRADING PLATFORM")
    print("=" * 95)
    print(f" -> Mode                       : {mode.upper()}")
    print(f" -> Remote Access Server       : http://{host}:{port}")
    print(f" -> Admin Login Username       : {ADMIN_USERNAME}")
    print(f" -> Default Access Password    : {DEFAULT_PASS_RAW}")
    print("=" * 95)

    # 1. Start Autonomous Orchestrator
    orchestrator = JarvisOrchestrator(mode=mode)
    orch_thread = threading.Thread(target=orchestrator.start, daemon=True, name="hm_orchestrator")
    orch_thread.start()
    logger.info(f"Autonomous Multi-Asset Trading Engine active ({mode.upper()} mode).")

    # 2. Start Remote Access Web Terminal & REST API Server
    logger.info(f"Starting Remote Access Web Terminal at http://{host}:{port}...")
    try:
        run_web_server(port=port, host=host)
    except KeyboardInterrupt:
        logger.info("Shutting down HM AI 4.0 trading platform...")
        orchestrator.stop()
        print("\n[SHUTDOWN] HM AI 4.0 stopped cleanly.")

if __name__ == "__main__":
    hm_start(mode="live", port=8501, host="0.0.0.0")

