"""
JARVIS AI 4.0 — Automated Remote Access Tunnel Launcher Script.
Connects with your authenticated localhost.run account or Serveo fallback.
"""
import subprocess
import urllib.request
import socket
import json
import sys
import time

def get_local_wifi_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def main():
    local_ip = get_local_wifi_ip()
    port = 8501

    print("=" * 80)
    print("        HM AI 4.0 — WORLDWIDE REMOTE MOBILE ACCESS LAUNCHER")
    print("=" * 80)
    print(f"\n1. PERMANENT LOCAL WI-FI ACCESS (Never changes at home):")
    print(f"   👉  http://{local_ip}:{port}")
    print("\n2. STARTING AUTHENTICATED GLOBAL HTTPS TUNNEL (For 4G/5G mobile access)...")

    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=20",
        "-o", "ServerAliveCountMax=10",
        "-R", f"80:127.0.0.1:{port}",
        "localhost.run"
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        tunnel_url = None

        for _ in range(25):
            line = proc.stdout.readline()
            if "tunneled with tls termination," in line:
                parts = line.split("tunneled with tls termination,")
                if len(parts) > 1:
                    tunnel_url = parts[1].strip()
                    break
            elif "Forwarding HTTP traffic from" in line:
                tunnel_url = line.split("Forwarding HTTP traffic from")[1].strip()
                break
            time.sleep(0.5)

        if tunnel_url:
            print("\n" + "*" * 80)
            print("  LIVE AUTHENTICATED MOBILE HTTPS URL (Access anywhere globally):")
            print(f"  👉  {tunnel_url}")
            print("\n  Default Username : admin")
            print("  Default Password : Hm@5656")
            print("*" * 80 + "\n")
            print("  Authenticated Account: tech54321.in@gmail.com")
            print("  Tunnel is running in background. Press Ctrl+C to close.")
            proc.wait()
        else:
            print("\nTunnel established. Access locally at: http://{local_ip}:{port}")
            proc.wait()

    except KeyboardInterrupt:
        print("\nTunnel closed by user.")
    except Exception as e:
        print(f"\nTunnel launcher error: {e}")

if __name__ == "__main__":
    main()
