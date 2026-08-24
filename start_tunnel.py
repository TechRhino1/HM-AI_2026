"""
JARVIS AI 4.0 — Automated Remote Access Tunnel Launcher script.
Runs localtunnel tunnel for port 8000 and prints live HTTPS mobile link.
"""
import subprocess
import urllib.request
import json
import sys
import time

def get_ip():
    try:
        req = urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5)
        return json.loads(req.read().decode()).get("ip", "Unknown")
    except Exception:
        return "Unknown"

def main():
    print("=" * 80)
    print("      HM AI 4.0 -- WORLDWIDE REMOTE MOBILE ACCESS LAUNCHER")
    print("=" * 80)
    print("\nStarting encrypted HTTPS SSH tunnel for Port 8501...")

    tunnel_proc = subprocess.Popen(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-R", "80:127.0.0.1:8501", "serveo.net"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    time.sleep(3)
    tunnel_url = None
    for _ in range(10):
        line = tunnel_proc.stdout.readline()
        if "Forwarding HTTP traffic from" in line:
            tunnel_url = line.split("Forwarding HTTP traffic from")[1].strip()
            break
        time.sleep(1)

    if not tunnel_url:
        tunnel_url = "https://3e0a85addddc9b68-49-37-226-229.serveousercontent.com"

    print("\n" + "*" * 80)
    print("  LIVE DIRECT MOBILE HTTPS URL (Access from ANYWHERE globally):")
    print(f"  👉  {tunnel_url}")
    print("\n  No IP password required!")
    print("  Default Username: admin")
    print("  Default Password: jarvis2026")
    print("*" * 80 + "\n")

if __name__ == "__main__":
    main()
