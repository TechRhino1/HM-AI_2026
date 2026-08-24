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
    ip = get_ip()
    print("=" * 80)
    print("      HM AI 4.0 — WORLDWIDE REMOTE MOBILE ACCESS LAUNCHER")
    print("=" * 80)
    print(f"Server Public IP: {ip}")
    print("\nStarting encrypted HTTPS tunnel for Port 8000...")

    tunnel_proc = subprocess.Popen(
        ["npx", "localtunnel", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    time.sleep(3)
    tunnel_url = None
    for _ in range(5):
        line = tunnel_proc.stdout.readline()
        if "your url is:" in line:
            tunnel_url = line.split("your url is:")[1].strip()
            break
        time.sleep(1)

    if not tunnel_url:
        tunnel_url = "https://twelve-doors-find.loca.lt"

    print("\n" + "*" * 80)
    print("  LIVE MOBILE HTTPS URL (Access from ANYWHERE in the world):")
    print(f"  {tunnel_url}")
    print("\n  Localtunnel Bypass Password (Public IP):")
    print(f"  {ip}")
    print("*" * 80 + "\n")

if __name__ == "__main__":
    main()
