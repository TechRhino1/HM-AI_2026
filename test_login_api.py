import urllib.request
import json

def test_login():
    url = "http://127.0.0.1:8501/api/auth/login"
    payload = json.dumps({"username": "admin", "password": "jarvis2026"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("[LOGIN SUCCESS]", data)
    except Exception as e:
        print("[LOGIN ERROR]", e)

if __name__ == "__main__":
    test_login()
