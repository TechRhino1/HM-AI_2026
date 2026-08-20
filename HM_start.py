import os, sys, time, re, socket, subprocess, threading, logging
import signal

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from jarvis.application.orchestrator import JarvisOrchestrator
from jarvis.api.server import run_web_server
from jarvis.application.state_manager import GLOBAL_STATE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("jarvis_system.log", encoding="utf-8")
    ]
)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def start_cloudflare_tunnel(port=8501):
    cloudflared_path = os.path.join(ROOT_DIR, "tools", "cloudflared.exe")
    if not os.path.exists(cloudflared_path):
        return None, None

    log_path = os.path.join(ROOT_DIR, "tools", "tunnel.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("")

    cmd = [cloudflared_path, "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"]
    out_f = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=out_f, stderr=out_f, text=True)

    tunnel_url = None
    for _ in range(25):
        time.sleep(1)
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                matches = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', content)
                if matches:
                    tunnel_url = matches[0]
                    break

    return proc, tunnel_url

def main():
    mode = "view" if len(sys.argv) > 1 and sys.argv[1].lower() == "view" else "live"
    local_ip = get_local_ip()

    print("\n" + "="*70)
    print("       HM_v3 — JARVIS AI 3.0 UNIFIED TRADING TERMINAL        ")
    print("="*70)
    print("[+] Initializing MT5 terminal, Risk Engine & 14-Point Quality Gates...")

    orchestrator = JarvisOrchestrator(mode=mode)
    orchestrator.start()

    print("[+] Starting Web Terminal Server on Port 8501...")
    server_thread = threading.Thread(target=run_web_server, args=(8501,), daemon=True)
    server_thread.start()

    print("[+] Initializing Cloudflare Secure Tunnel for Mobile Access...")
    tunnel_proc, tunnel_url = start_cloudflare_tunnel(8501)

    snap = GLOBAL_STATE.get_state_snapshot()
    acc = snap.get("account") or {}

    print("\n" + "="*70)
    print("                     JARVIS AI 3.0 COMMAND CENTER                     ")
    print("="*70)
    status_str = "ACTIVE (LIVE)" if not snap.get("safe_mode") else "SAFE MODE"
    print(f"STATUS:          {status_str}")
    print(f"EXECUTION MODE:  {snap.get('execution_mode')} (14-Point Quality Gate Active)")
    print(f"BROKER SERVER:   {acc.get('server', 'XMGlobal-MT5')} (#{acc.get('login', 345841337)})")
    print(f"BALANCE / EQ:    ${acc.get('balance', 0):,.2f} / ${acc.get('equity', 0):,.2f}")
    print("-"*70)
    print("ACCESS LINKS (PC & MOBILE PHONE):")
    print(f"  [Desktop PC]:   http://localhost:8501")
    print(f"  [Wi-Fi Phone]:  http://{local_ip}:8501")
    if tunnel_url:
        print(f"  [Remote 4G/5G]: {tunnel_url}")
    else:
        print("  [Remote 4G/5G]: Starting in background (see tools/tunnel.log)")
    print("="*70)
    print("[+] System is actively monitoring market opportunities.")
    print("[+] Press Ctrl+C to gracefully stop all engines and tunnels.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Gracefully shutting down HM_v3...")
        orchestrator.stop()
        if tunnel_proc:
            tunnel_proc.terminate()
        print("[+] Jarvis and Cloudflare safely terminated.\n")

if __name__ == "__main__":
    main()
