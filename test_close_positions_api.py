import urllib.request
import json

def test_close_all():
    # 1. Login to get token
    login_url = "http://127.0.0.1:8501/api/auth/login"
    login_req = urllib.request.Request(login_url, data=json.dumps({"username": "admin", "password": "Hm@5656"}).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(login_req) as resp:
        token = json.loads(resp.read().decode("utf-8"))["token"]
        print("[TOKEN OBTAINED]:", token[:30] + "...")

    # 2. Call close_all_positions
    close_url = "http://127.0.0.1:8501/api/action/close_all_positions"
    close_req = urllib.request.Request(close_url, data=b"{}", headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(close_req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("[CLOSE ALL RESULT]:", data)

if __name__ == "__main__":
    test_close_all()
