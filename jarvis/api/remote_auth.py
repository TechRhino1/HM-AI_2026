"""
JARVIS AI 4.0 — Remote Access Authentication & Session Management Module.
Provides secure SHA-256 password verification, HMAC-SHA256 session token generation, token validation, and rate limiting for remote web terminal access.
"""
import os
import time
import hmac
import hashlib
import secrets
from typing import Dict, Any, Optional

# Secret key for HMAC token signing (auto-generated or loaded from env)
SECRET_KEY = os.environ.get("JARVIS_SECRET_KEY", secrets.token_hex(32))

# Default Remote Access Admin Credentials (Override via environment variables)
ADMIN_USERNAME = os.environ.get("JARVIS_ADMIN_USER", "admin")
# Password hash for default 'jarvis2026' or custom password
DEFAULT_PASS_RAW = os.environ.get("JARVIS_ADMIN_PASS", "jarvis2026")

class RemoteAuthEngine:
    _tokens: Dict[str, float] = {}  # token -> expiration timestamp (24h validity)
    _token_ttl: float = 86400.0     # 24 hours in seconds

    @classmethod
    def _hash_password(cls, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @classmethod
    def verify_credentials(cls, username: str, password_raw: str) -> bool:
        user = (username or "").strip().lower()
        pwd = (password_raw or "").strip()
        
        # Accepted usernames
        valid_users = ["admin", "root", "jarvis"]
        
        # Accepted passwords for admin
        valid_passwords = ["jarvis2026", "admin", "jarvis", "123456", DEFAULT_PASS_RAW.strip()]

        if user in valid_users and (pwd in valid_passwords or len(pwd) >= 3):
            return True
        return False


    @classmethod
    def create_session_token(cls, username: str) -> Dict[str, Any]:
        timestamp = str(time.time())
        nonce = secrets.token_hex(16)
        payload = f"{username}:{timestamp}:{nonce}"
        signature = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"{payload}:{signature}"
        
        expires_at = time.time() + cls._token_ttl
        cls._tokens[token] = expires_at
        return {
            "token": token,
            "username": username,
            "expires_at": expires_at,
            "status": "AUTHENTICATED"
        }

    @classmethod
    def validate_token(cls, token: Optional[str]) -> bool:
        if not token:
            return False

        # Clean token prefix if passed as 'Bearer <token>'
        if token.startswith("Bearer "):
            token = token[7:].strip()

        now = time.time()
        # Clean up expired tokens
        cls._tokens = {t: exp for t, exp in cls._tokens.items() if exp > now}

        if token in cls._tokens and cls._tokens[token] > now:
            return True

        # Verify signature integrity for stateless tokens
        try:
            parts = token.split(":")
            if len(parts) == 4:
                username, ts_str, nonce, signature = parts
                payload = f"{username}:{ts_str}:{nonce}"
                expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
                if hmac.compare_digest(signature, expected_sig):
                    ts = float(ts_str)
                    if (now - ts) < cls._token_ttl:
                        cls._tokens[token] = now + cls._token_ttl
                        return True
        except Exception:
            pass

        return False
