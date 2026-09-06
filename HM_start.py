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
    "url": "establishing...",
    "status": "STARTING",
    "provider": "None",
    "proc": None
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

def _cleanup_stale_processes():
    """Safely terminates previously tracked tunnel subprocesses."""
    proc = _TUNNEL_STATE.get("proc")
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=2.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        _TUNNEL_STATE["proc"] = None

def _save_active_tunnel_url(url: str, provider: str = ""):
    try:
        target = os.path.join(BASE_DIR, "active_tunnel_url.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write(url.strip())
    except Exception:
        pass

def _start_background_tunnel(port: int = 8501):
    """
    Starts persistent authenticated HTTPS mobile tunnel with automatic multi-provider fallback.
    Priority 1: Cloudflare Tunnel (trycloudflare.com) — zero drops, CDN-accelerated, sub-second latency.
    Priority 2: localhost.run (SSH tunnel with aggressive keepalive).
    Priority 3: pinggy.io (SSH tunnel over port 443).
    Priority 4: serveo.net (SSH tunnel).
    """
    _cleanup_stale_processes()
    key_path = os.path.expanduser("~/.ssh/id_ed25519")
    local_ip = get_local_wifi_ip()

    cloudflared_bin = find_cloudflared_binary()

    providers = []
    if cloudflared_bin:
        providers.append(("Cloudflare Tunnel", [cloudflared_bin, "tunnel", "--url", f"http://127.0.0.1:{port}"]))

    providers.append(("localhost.run", [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=10",
        "-o", "ServerAliveCountMax=3",
        "-o", "TCPKeepAlive=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-R", f"80:127.0.0.1:{port}",
        "nokey@localhost.run"
    ]))

    providers.append(("pinggy.io", [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=10",
        "-o", "ServerAliveCountMax=3",
        "-o", "TCPKeepAlive=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-p", "443",
        "-R0:127.0.0.1:{port}",
        "a.pinggy.io"
    ]))

    providers.append(("serveo.net", [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=10",
        "-o", "ServerAliveCountMax=3",
        "-o", "TCPKeepAlive=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-R", f"80:127.0.0.1:{port}",
        "serveo.net"
    ]))

    p_idx = 0
    while True:
        p_name, cmd = providers[p_idx % len(providers)]
        if "ssh" in cmd[0] and os.path.exists(key_path) and "-i" not in cmd:
            cmd = [cmd[0], "-i", key_path] + cmd[1:]

        try:
            logger.info(f"Establishing high-speed mobile HTTPS tunnel via {p_name}...")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            _TUNNEL_STATE["proc"] = proc
            _TUNNEL_STATE["status"] = "INITIALIZING"
            _TUNNEL_STATE["provider"] = p_name

            url_found = False
            start_t = time.time()

            while time.time() - start_t < 25:
                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
                    continue

                clean_line = line.strip()

                # 1. Cloudflare Tunnel regex
                if "trycloudflare.com" in clean_line:
                    m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", clean_line)
                    if m:
                        url = m.group(0)
                        _TUNNEL_STATE["url"] = url
                        _TUNNEL_STATE["status"] = "CONNECTED"
                        _save_active_tunnel_url(url, p_name)
                        url_found = True
                        break

                # 2. localhost.run parsing
                elif "tunneled with tls termination," in clean_line:
                    parts = clean_line.split("tunneled with tls termination,")
                    if len(parts) > 1:
                        url = parts[1].strip()
                        _TUNNEL_STATE["url"] = url
                        _TUNNEL_STATE["status"] = "CONNECTED"
                        _save_active_tunnel_url(url, p_name)
                        url_found = True
                        break

                # 3. pinggy.io regex
                elif "pinggy.link" in clean_line:
                    m = re.search(r"https?://[a-zA-Z0-9-]+\.a\.free\.pinggy\.link", clean_line)
                    if m:
                        url = m.group(0).replace("http://", "https://")
                        _TUNNEL_STATE["url"] = url
                        _TUNNEL_STATE["status"] = "CONNECTED"
                        _save_active_tunnel_url(url, p_name)
                        url_found = True
                        break

                # 4. serveo.net parsing
                elif "Forwarding HTTP traffic from" in clean_line:
                    url = clean_line.split("Forwarding HTTP traffic from")[1].strip()
                    _TUNNEL_STATE["url"] = url
                    _TUNNEL_STATE["status"] = "CONNECTED"
                    _save_active_tunnel_url(url, p_name)
                    url_found = True
                    break

            if url_found:
                active_url = _TUNNEL_STATE["url"]
                logger.info(f"Mobile HTTPS Tunnel active: {active_url}")
                print("\n" + "=" * 95, flush=True)
                print(f" [HM_START] ⚡ SECURE CLOUD MOBILE TUNNEL ACTIVE: {active_url}", flush=True)
                print(f"  -> Tunnel Provider       : {p_name}", flush=True)
                print(f"  -> Permanent Local Wi-Fi : http://{local_ip}:{port}", flush=True)
                print(f"  -> Remote Auth Login     : admin / admin (or Hms@2026)", flush=True)
                print("=" * 95 + "\n", flush=True)

                # Keep reading output so buffer doesn't fill up
                while proc.poll() is None:
                    line = proc.stdout.readline()
                    if not line and proc.poll() is not None:
                        break
                    time.sleep(0.5)

            # If reached here, process exited or timed out
            ret = proc.poll()
            logger.warning(f"Tunnel via {p_name} closed (code {ret}). Reconnecting in 2s...")
            _TUNNEL_STATE["status"] = "RECONNECTING"
            p_idx += 1
            time.sleep(2)
        except Exception as e:
            _TUNNEL_STATE["status"] = f"ERROR: {e}"
            logger.error(f"Tunnel error ({p_name}): {e}. Trying next provider...")
            p_idx += 1
            time.sleep(3)

def hm_start(mode: str = "live", port: int = 8501, host: str = "0.0.0.0", trade_style: str = "ALL"):
    local_ip = get_local_wifi_ip()
    mobile_url = _TUNNEL_STATE["url"]

    # 1. Launch Mobile Tunnel Background Worker
    tunnel_thread = threading.Thread(target=_start_background_tunnel, args=(port,), daemon=True, name="hm_mobile_tunnel")
    tunnel_thread.start()

    print("=" * 95, flush=True)
    print("                 HM AI 4.0 — INSTITUTIONAL QUANTITATIVE TRADING PLATFORM", flush=True)
    print("=" * 95, flush=True)
    print(f" -> Mode                       : {mode.upper()}", flush=True)
    print(f" -> Trade Style                : {trade_style.upper()}", flush=True)
    print(f" -> Remote Access Server       : http://{host}:{port}", flush=True)
    print(f" -> Permanent Local Wi-Fi Link : http://{local_ip}:{port}", flush=True)
    print(f" -> Global Mobile HTTPS Link   : {mobile_url}", flush=True)
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
