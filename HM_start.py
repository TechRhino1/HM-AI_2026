"""
HM AI 4.0 — Primary Autonomous System Launcher (HM_start.py).
Launches:
 1. Autonomous Multi-Asset Trading Engine & Quality Gate Decision Matrix
 2. Remote Access Web Terminal & REST API Server (Port 8501)
 3. Automatic Authenticated HTTPS Mobile Access Tunnel (localhost.run / serveo)
 4. Permanent Local Wi-Fi & Global Cloud Access
All in one single command!
"""
import os
import sys
import time
import socket
import threading
import subprocess
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from jarvis.application.orchestrator import JarvisOrchestrator
from jarvis.api.server import run_web_server
from jarvis.api.remote_auth import ADMIN_USERNAME, DEFAULT_PASS_RAW

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("HM_START")

_TUNNEL_STATE = {
    "url": "https://ab23fdf1a98644.lhr.life",
    "status": "STARTING",
    "proc": None
}

def get_local_wifi_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def _cleanup_stale_processes():
    """Kills orphan ssh processes to avoid port forward collisions on Serveo."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "ssh.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def _start_background_tunnel(port: int = 8501, custom_subdomain: str = "hm2026"):
    """Starts persistent authenticated HTTPS mobile tunnel with automatic multi-provider fallback."""
    _cleanup_stale_processes()
    key_path = os.path.expanduser("~/.ssh/id_ed25519")

    providers = [
        ("serveo.net", ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=10", "-o", "ExitOnForwardFailure=yes", "-R", f"{custom_subdomain}:80:127.0.0.1:{port}", "serveo.net"]),
        ("localhost.run", ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=15", "-o", "ExitOnForwardFailure=yes", "-R", f"80:127.0.0.1:{port}", "localhost.run"]),
    ]

    p_idx = 0
    while True:
        p_name, cmd = providers[p_idx % len(providers)]
        if os.path.exists(key_path) and "-i" not in cmd:
            cmd = [cmd[0], "-i", key_path] + cmd[1:]
        
        try:
            logger.info(f"Establishing mobile HTTPS tunnel via {p_name}...")
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
            _TUNNEL_STATE["proc"] = proc
            _TUNNEL_STATE["status"] = "CONNECTED"

            for _ in range(40):
                line = proc.stdout.readline()
                if not line:
                    line = proc.stderr.readline()
                if not line:
                    break
                if "Forwarding HTTP traffic from" in line:
                    _TUNNEL_STATE["url"] = line.split("Forwarding HTTP traffic from")[1].strip()
                    logger.info(f"Mobile HTTPS Tunnel active: {_TUNNEL_STATE['url']}")
                    break
                elif "tunneled with tls termination," in line:
                    parts = line.split("tunneled with tls termination,")
                    if len(parts) > 1:
                        _TUNNEL_STATE["url"] = parts[1].strip()
                        logger.info(f"Mobile HTTPS Tunnel active: {_TUNNEL_STATE['url']}")
                        break
                time.sleep(0.2)

            proc.wait()
            _TUNNEL_STATE["status"] = "RECONNECTING"
            logger.warning(f"Tunnel via {p_name} closed. Reconnecting to next provider in 2s...")
            p_idx += 1
            time.sleep(2)
        except Exception as e:
            _TUNNEL_STATE["status"] = f"ERROR: {e}"
            logger.error(f"Tunnel error ({p_name}): {e}. Trying next provider...")
            p_idx += 1
            time.sleep(3)

def hm_start(mode: str = "live", port: int = 8501, host: str = "0.0.0.0"):
    local_ip = get_local_wifi_ip()
    mobile_url = f"https://hm2026.serveousercontent.com"

    # 1. Launch Mobile Tunnel Background Worker
    tunnel_thread = threading.Thread(target=_start_background_tunnel, args=(port,), daemon=True, name="hm_mobile_tunnel")
    tunnel_thread.start()

    print("=" * 95, flush=True)
    print("                 HM AI 4.0 — INSTITUTIONAL QUANTITATIVE TRADING PLATFORM", flush=True)
    print("=" * 95, flush=True)
    print(f" -> Mode                       : {mode.upper()}", flush=True)
    print(f" -> Remote Access Server       : http://{host}:{port}", flush=True)
    print(f" -> Permanent Local Wi-Fi Link : http://{local_ip}:{port}", flush=True)
    print(f" -> Global Mobile HTTPS Link   : {mobile_url}", flush=True)
    print(f" -> Admin Login Username       : {ADMIN_USERNAME}", flush=True)
    print(f" -> Access Password            : {DEFAULT_PASS_RAW}", flush=True)
    print("=" * 95, flush=True)

    # 2. Start Autonomous Orchestrator
    orchestrator = JarvisOrchestrator(mode=mode)
    orch_thread = threading.Thread(target=orchestrator.start, daemon=True, name="hm_orchestrator")
    orch_thread.start()
    logger.info(f"Autonomous Multi-Asset Trading Engine active ({mode.upper()} mode).")

    # 3. Start Remote Access Web Terminal & REST API Server
    logger.info(f"Starting Remote Access Web Terminal at http://{host}:{port}...")
    try:
        run_web_server(port=port, host=host)
    except KeyboardInterrupt:
        logger.info("Shutting down HM AI 4.0 trading platform...")
        orchestrator.stop()
        if _TUNNEL_STATE["proc"]:
            try:
                _TUNNEL_STATE["proc"].terminate()
            except Exception:
                pass
        print("\n[SHUTDOWN] HM AI 4.0 stopped cleanly.", flush=True)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "live"
    hm_start(mode=mode)

if __name__ == "__main__":
    main()
