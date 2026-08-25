"""
Automated Authentication Test Suite for HM AI 4.0
Tests Login, Logout, Session Verification, Password Validation, and Token Revocation.
"""
import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://127.0.0.1:8501"

def run_auth_tests():
    print("=" * 80)
    print("RUNNING HM AI 4.0 AUTHENTICATION (LOGIN, LOGOUT, VERIFY & ROLES) TEST SUITE")
    print("=" * 80)
    passed = 0
    failed = 0

    def test_post(name, endpoint, payload, expected_status, headers=None, validator=None):
        nonlocal passed, failed
        url = f"{BASE_URL}{endpoint}"
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        body = json.dumps(payload).encode("utf-8") if payload is not None else b""
        req = urllib.request.Request(url, data=body, headers=h, method="POST")

        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                data = json.loads(resp.read().decode("utf-8"))
                if status == expected_status and (validator is None or validator(data)):
                    print(f"[PASS] {name:50} -> HTTP {status} OK | Response Validated")
                    passed += 1
                    return data
                else:
                    print(f"[FAIL] {name:50} -> Expected {expected_status}, got {status}")
                    failed += 1
                    return None
        except urllib.error.HTTPError as e:
            if e.code == expected_status:
                try:
                    data = json.loads(e.read().decode("utf-8"))
                except Exception:
                    data = {}
                if validator is None or validator(data):
                    print(f"[PASS] {name:50} -> HTTP {e.code} Expected | Error Handled Correctly")
                    passed += 1
                    return data
            print(f"[FAIL] {name:50} -> Expected HTTP {expected_status}, got {e.code}")
            failed += 1
            return None
        except Exception as ex:
            print(f"[FAIL] {name:50} -> Exception: {ex}")
            failed += 1
            return None

    # 1. Test Login with Valid Admin Credentials
    admin_session = test_post(
        "1. Login Valid Admin (admin / Hm@5656)",
        "/api/auth/login",
        {"username": "admin", "password": "Hm@5656"},
        200,
        validator=lambda d: bool(d.get("token") and d.get("role") == "ADMIN")
    )
    admin_token = admin_session["token"] if admin_session else ""

    # 2. Test Login with Invalid Password (Rejection)
    test_post(
        "2. Login Invalid Password (admin / wrongpass123)",
        "/api/auth/login",
        {"username": "admin", "password": "wrongpass123"},
        401,
        validator=lambda d: d.get("status") == "UNAUTHORIZED"
    )

    # 3. Test Login with Invalid Username
    test_post(
        "3. Login Unknown User (unknown_user / 123456)",
        "/api/auth/login",
        {"username": "unknown_user", "password": "123456"},
        401,
        validator=lambda d: d.get("status") == "UNAUTHORIZED"
    )

    # 4. Test Login with Secondary Account (trader / trader2026)
    test_post(
        "4. Login Valid Trader (trader / trader2026)",
        "/api/auth/login",
        {"username": "trader", "password": "trader2026"},
        200,
        validator=lambda d: bool(d.get("token") and d.get("role") == "TRADER")
    )

    # 5. Test Token Verification with Valid Admin Token
    test_post(
        "5. Verify Valid Admin Token",
        "/api/auth/verify",
        {},
        200,
        headers={"Authorization": f"Bearer {admin_token}"},
        validator=lambda d: d.get("valid") is True and d.get("user", {}).get("username") == "admin"
    )

    # 6. Test Token Verification without Token (Unauthorized)
    test_post(
        "6. Verify Missing Token (Unauthorized)",
        "/api/auth/verify",
        {},
        401,
        validator=lambda d: d.get("valid") is False
    )

    # 7. Test Logout (Server-side Token Revocation)
    test_post(
        "7. Logout Admin Session (/api/auth/logout)",
        "/api/auth/logout",
        {},
        200,
        headers={"Authorization": f"Bearer {admin_token}"},
        validator=lambda d: d.get("status") == "LOGGED_OUT"
    )

    # 8. Test Verification of Revoked Token (Must Fail with 401)
    test_post(
        "8. Verify Revoked Token (Must be Rejected)",
        "/api/auth/verify",
        {},
        401,
        headers={"Authorization": f"Bearer {admin_token}"},
        validator=lambda d: d.get("valid") is False
    )

    print("=" * 80)
    print(f"TEST RESULTS: {passed} PASSED | {failed} FAILED")
    print("=" * 80)

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_auth_tests()
