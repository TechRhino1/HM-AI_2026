import urllib.request
import json
import os

def _get_admin_pass():
    p = os.environ.get("JARVIS_ADMIN_PASS")
    if p:
        return p
    try:
        with open(".jarvis_admin_pass", "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "CHANGE_ME"

def test_login():
    url = "http://127.0.0.1:8501/api/auth/login"
    payload = json.dumps({"username": "admin", "password": _get_admin_pass()}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("[LOGIN SUCCESS]", data)
    except Exception as e:
        print("[LOGIN ERROR]", e)

if __name__ == "__main__":
    test_login()
