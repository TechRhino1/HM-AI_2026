"""
JARVIS AI 4.0 — Automated Remote Access Tunnel Launcher Script.
Provides encrypted HTTPS mobile access tunnel with keep-alive, auto-reconnect, and local Wi-Fi links.
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
    print("\n2. STARTING GLOBAL ENCRYPTED HTTPS TUNNEL (For 4G/5G mobile access)...")

    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=5",
        "-R", f"80:127.0.0.1:{port}",
        "serveo.net"
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        tunnel_url = None

        for _ in range(15):
            line = proc.stdout.readline()
            if "Forwarding HTTP traffic from" in line:
                tunnel_url = line.split("Forwarding HTTP traffic from")[1].strip()
                break
            time.sleep(1)

        if tunnel_url:
            print("\n" + "*" * 80)
            print("  LIVE GLOBAL MOBILE HTTPS URL (Access from ANYWHERE globally):")
            print(f"  👉  {tunnel_url}")
            print("\n  Username : admin")
            print("  Password : Hm@5656")
            print("*" * 80 + "\n")
            print("  [Tip] For a permanent 100% fixed URL that never changes, install Tailscale (https://tailscale.com).")
            print("  Tunnel is running actively in the background. Press Ctrl+C to close.")
            proc.wait()
        else:
            print("\nUnable to retrieve dynamic tunnel URL from Serveo.")
            print(f"You can always access locally at: http://{local_ip}:{port}")

    except KeyboardInterrupt:
        print("\nTunnel closed by user.")
    except Exception as e:
        print(f"\nTunnel launcher error: {e}")

if __name__ == "__main__":
    main()
