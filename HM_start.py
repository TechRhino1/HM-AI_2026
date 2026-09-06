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
import re
import socket
import shutil
import threading
import subprocess
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from jarvis.application.orchestrator import JarvisOrchestrator
from jarvis.api.server import run_web_server
# Admin credentials are resolved from environment at runtime (see jarvis.api.remote_auth)

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
    "serveo_url": "https://hm2026.serveousercontent.com",
    "serveo_status": "CONNECTING",
    "cloudflare_url": "establishing...",
    "cloudflare_status": "STARTING",
    "url": "https://hm2026.serveousercontent.com",
    "status": "STARTING",
    "provider": "Dual Tunnel (Serveo + Cloudflare)"
}

def get_local_wifi_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"

def find_cloudflared_binary():
    """Locates the Cloudflare Tunnel executable on Windows / Linux."""
    cand = shutil.which("cloudflared")
    if cand and os.path.exists(cand):
        return cand
    for p in [
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
        r"C:\cloudflared\cloudflared.exe",
        os.path.expanduser("~\\cloudflared.exe")
    ]:
        if os.path.exists(p):
            return p
    return None

def _save_active_tunnel_url(url: str, provider: str = ""):
    try:
        target = os.path.join(BASE_DIR, "active_tunnel_url.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write(url.strip())
    except Exception:
        pass

def _serveo_worker(port: int = 8501, custom_subdomain: str = "hm2026"):
    """Dedicated persistent worker for https://hm2026.serveousercontent.com with auto-reconnect."""
    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=10",
        "-o", "ServerAliveCountMax=3",
        "-o", "TCPKeepAlive=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-R", f"{custom_subdomain}:80:127.0.0.1:{port}",
        "serveo.net"
    ]
    key_path = os.path.expanduser("~/.ssh/id_ed25519")
    if os.path.exists(key_path):
        cmd = [cmd[0], "-i", key_path] + cmd[1:]

    while True:
        try:
            logger.info(f"Connecting Custom Subdomain HTTPS via serveo.net ({custom_subdomain})...")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            for _ in range(40):
                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
                    continue
                if "Forwarding HTTP traffic from" in line:
                    _TUNNEL_STATE["serveo_url"] = f"https://{custom_subdomain}.serveousercontent.com"
                    _TUNNEL_STATE["serveo_status"] = "CONNECTED"
                    _TUNNEL_STATE["url"] = _TUNNEL_STATE["serveo_url"]
                    _save_active_tunnel_url(_TUNNEL_STATE["serveo_url"], "serveo")
                    logger.info(f"Custom Subdomain Active: {_TUNNEL_STATE['serveo_url']}")
                    print(f"\n[HM_START] 🌐 CUSTOM SUBDOMAIN ACTIVE: {_TUNNEL_STATE['serveo_url']}\n", flush=True)
                    break
            while proc.poll() is None:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                time.sleep(1.0)
            logger.warning("Serveo custom tunnel closed. Auto-reconnecting in 3s...")
            _TUNNEL_STATE["serveo_status"] = "RECONNECTING"
            time.sleep(3)
        except Exception as e:
            logger.error(f"Serveo worker error: {e}. Reconnecting in 5s...")
            time.sleep(5)

def _cloudflare_worker(port: int = 8501):
    """Dedicated worker for Cloudflare Edge Tunnel with zero drops."""
    cloudflared_bin = find_cloudflared_binary()
    if not cloudflared_bin:
        logger.warning("cloudflared binary not found; skipping secondary edge tunnel.")
        return

    cmd = [cloudflared_bin, "tunnel", "--url", f"http://127.0.0.1:{port}"]
    while True:
        try:
            logger.info("Connecting High-Speed Cloudflare Edge Tunnel...")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            for _ in range(50):
                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
                    continue
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m:
                    url = m.group(0)
                    _TUNNEL_STATE["cloudflare_url"] = url
                    _TUNNEL_STATE["cloudflare_status"] = "CONNECTED"
                    logger.info(f"Cloudflare Edge Tunnel Active: {url}")
                    print(f"\n[HM_START] ⚡ CLOUDFLARE EDGE ACTIVE: {url}\n", flush=True)
                    break
            while proc.poll() is None:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                time.sleep(1.0)
            logger.warning("Cloudflare edge tunnel closed. Auto-reconnecting in 3s...")
            _TUNNEL_STATE["cloudflare_status"] = "RECONNECTING"
            time.sleep(3)
        except Exception as e:
            logger.error(f"Cloudflare worker error: {e}. Reconnecting in 5s...")
            time.sleep(5)

def _start_background_tunnel(port: int = 8501):
    """Launches both Serveo (custom domain hm2026) and Cloudflare (fast edge) in parallel."""
    t_serveo = threading.Thread(target=_serveo_worker, args=(port, "hm2026"), daemon=True, name="hm_tunnel_serveo")
    t_serveo.start()

    t_cf = threading.Thread(target=_cloudflare_worker, args=(port,), daemon=True, name="hm_tunnel_cf")
    t_cf.start()

def hm_start(mode: str = "live", port: int = 8501, host: str = "0.0.0.0", trade_style: str = "ALL"):
    local_ip = get_local_wifi_ip()

    # 1. Launch Parallel Mobile Tunnels
    tunnel_thread = threading.Thread(target=_start_background_tunnel, args=(port,), daemon=True, name="hm_mobile_tunnel")
    tunnel_thread.start()

    print("=" * 95, flush=True)
    print("                 HM AI 4.0 — INSTITUTIONAL QUANTITATIVE TRADING PLATFORM", flush=True)
    print("=" * 95, flush=True)
    print(f" -> Mode                       : {mode.upper()}", flush=True)
    print(f" -> Trade Style                : {trade_style.upper()}", flush=True)
    print(f" -> Remote Access Server       : http://{host}:{port}", flush=True)
    print(f" -> Permanent Local Wi-Fi Link : http://{local_ip}:{port}", flush=True)
    print(f" -> Custom Subdomain HTTPS     : https://hm2026.serveousercontent.com", flush=True)
    print(f" -> High-Speed Cloudflare Edge : establishing...", flush=True)
    print(f" -> Admin Username             : admin", flush=True)
    print(f" -> Admin Password             : admin (or Hms@2026)", flush=True)
    print("=" * 95, flush=True)

    # 2. Start Autonomous Orchestrator
    orchestrator = JarvisOrchestrator(mode=mode, trade_style=trade_style)
    orch_thread = threading.Thread(target=orchestrator.start, daemon=True, name="hm_orchestrator")
    orch_thread.start()
    logger.info(f"Autonomous Multi-Asset Trading Engine active ({mode.upper()} mode, style {trade_style.upper()}).")

    # 3. Start Remote Access Web Terminal & REST API Server with auto-recovery
    logger.info(f"Starting Remote Access Web Terminal at http://{host}:{port}...")
    while True:
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
            break
        except Exception as e:
            logger.error(f"Web server encountered error: {e}. Auto-restarting in 3s...", exc_info=True)
            time.sleep(3)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "live"
    hm_start(mode=mode)

if __name__ == "__main__":
    main()
