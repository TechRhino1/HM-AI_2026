import urllib.request
import json

def test_endpoints():
    base_url = "http://127.0.0.1:8501"
    endpoints = [
        "/api/telemetry_state",
        "/api/candles?symbol=XAUUSD&tf=H1",
        "/api/radar",
        "/api/history",
        "/api/news",
        "/api/diagnostics",
        "/api/market-status?symbol=XAUUSD"
    ]

    print("Testing Web Terminal API Endpoints...")
    for ep in endpoints:
        url = base_url + ep
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DashboardTestClient"})
            with urllib.request.urlopen(req, timeout=5.0) as response:
                status = response.status
                data = response.read().decode("utf-8")
                parsed = json.loads(data)
                print(f"[OK] {ep:<35} -> HTTP {status} | Data Keys: {list(parsed.keys()) if isinstance(parsed, dict) else len(parsed)}")
        except Exception as e:
            print(f"[ERROR] {ep:<35} -> {e}")

if __name__ == "__main__":
    test_endpoints()
