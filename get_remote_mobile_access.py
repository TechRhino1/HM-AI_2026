"""
JARVIS AI 4.0 — Remote Mobile Access Link & Tunnel Helper.
Displays live public HTTPS URLs to connect to HM AI 4.0 Dashboard from any smartphone globally.
"""
import urllib.request
import json
import subprocess
import time

def get_public_ip():
    try:
        with urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5) as response:
            data = json.loads(response.read().decode())
            return data.get("ip", "Unknown")
    except Exception:
        return "Unknown"

def main():
    public_ip = get_public_ip()
    tunnel_url = "https://twelve-doors-find.loca.lt"

    print("=" * 80)
    print("      HM AI 4.0 -- WORLDWIDE REMOTE MOBILE ACCESS INSTRUCTIONS")
    print("=" * 80)
    print("\n1. Open this URL on your mobile phone browser from ANYWHERE in the world:\n")
    print(f"   URL: {tunnel_url}")
    print("\n2. When localtunnel asks for your 'Endpoint IP' / 'Tunnel Password':\n")
    print(f"   Enter IP: {public_ip}")
    print("\n3. Click 'Click to Submit' -- the glassmorphic login modal will open.")
    print("4. Enter your remote password to log into HM AI 4.0 Dashboard on mobile.")
    print("=" * 80)

if __name__ == "__main__":
    main()
