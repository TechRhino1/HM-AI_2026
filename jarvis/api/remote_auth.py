"""
JARVIS AI 4.0 — Remote Access Authentication & Session Management Engine.
Provides secure password verification with salted hashing, HMAC-SHA256 session token generation,
token validation, server-side token revocation (logout), role-based access control, and user profile management.
"""
import os
import time
import hmac
import hashlib
import secrets
from typing import Dict, Any, Optional, Tuple

# Secret key for HMAC token signing (auto-generated or loaded from env)
SECRET_KEY = os.environ.get("JARVIS_SECRET_KEY", secrets.token_hex(32))

# Default Remote Access Admin Credentials (Override via environment variables)
ADMIN_USERNAME = os.environ.get("JARVIS_ADMIN_USER", "admin")
DEFAULT_PASS_RAW = os.environ.get("JARVIS_ADMIN_PASS", "jarvis2026")


class RemoteAuthEngine:
    """
    Secure Authentication and Session Engine for JARVIS AI Remote Web Terminals.
    """
    _tokens: Dict[str, float] = {}       # token -> expiration timestamp (24h validity)
    _revoked_tokens: set = set()          # set of revoked tokens (logged out)
    _token_ttl: float = 86400.0          # 24 hours in seconds

    # In-memory user database with salted hashes and roles
    _users: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _init_default_users(cls):
        """Initializes default institutional users with salted SHA-256 password hashes."""
        if cls._users:
            return

        def _make_user_record(username: str, password_raw: str, role: str, full_name: str) -> Dict[str, Any]:
            salt = secrets.token_hex(16)
            pwd_hash = cls._hash_password(password_raw, salt)
            return {
                "username": username.lower(),
                "role": role,
                "full_name": full_name,
                "salt": salt,
                "password_hash": pwd_hash,
                "created_at": time.time()
            }

        # 1. Primary Admin Account
        admin_pass = DEFAULT_PASS_RAW.strip() if DEFAULT_PASS_RAW else "jarvis2026"
        cls._users["admin"] = _make_user_record("admin", admin_pass, "ADMIN", "System Administrator")

        # 2. Trader Account
        cls._users["trader"] = _make_user_record("trader", "trader2026", "TRADER", "Senior Algo Trader")

        # 3. Viewer/Demo Account
        cls._users["demo"] = _make_user_record("demo", "demo2026", "VIEWER", "Demo Guest Account")

    @classmethod
    def _hash_password(cls, password: str, salt: str) -> str:
        """Returns salted SHA-256 hash of password."""
        salted_str = f"{salt}:{password.strip()}"
        return hashlib.sha256(salted_str.encode("utf-8")).hexdigest()

    @classmethod
    def verify_credentials(cls, username: str, password_raw: str) -> Optional[Dict[str, Any]]:
        """
        Strictly verifies provided username and password.
        Returns user dictionary if valid, None if invalid.
        """
        cls._init_default_users()
        user_key = (username or "").strip().lower()
        pwd = (password_raw or "").strip()

        if not user_key or not pwd:
            return None

        user_data = cls._users.get(user_key)
        if not user_data:
            return None

        salt = user_data["salt"]
        stored_hash = user_data["password_hash"]
        attempt_hash = cls._hash_password(pwd, salt)

        if hmac.compare_digest(attempt_hash, stored_hash):
            return {
                "username": user_data["username"],
                "role": user_data["role"],
                "full_name": user_data["full_name"]
            }

        return None

    @classmethod
    def create_session_token(cls, username: str) -> Dict[str, Any]:
        """
        Generates a tamper-proof HMAC-SHA256 signed session token for authenticated user.
        """
        cls._init_default_users()
        user_key = (username or "").strip().lower()
        user_data = cls._users.get(user_key, {"role": "TRADER", "full_name": username})

        timestamp = str(time.time())
        nonce = secrets.token_hex(16)
        payload = f"{user_key}:{timestamp}:{nonce}"
        signature = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"{payload}:{signature}"

        expires_at = time.time() + cls._token_ttl
        cls._tokens[token] = expires_at

        # Un-revoke token if previously in revoked set
        cls._revoked_tokens.discard(token)

        return {
            "token": token,
            "username": user_key,
            "role": user_data.get("role", "TRADER"),
            "full_name": user_data.get("full_name", user_key.title()),
            "expires_at": expires_at,
            "status": "AUTHENTICATED"
        }

    @classmethod
    def validate_token(cls, token: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Validates token signature, expiration, and ensures token is not revoked.
        Returns user session details if valid, None if invalid.
        """
        if not token:
            return None

        cls._init_default_users()

        # Clean token prefix if passed as 'Bearer <token>'
        if token.startswith("Bearer "):
            token = token[7:].strip()

        if token in cls._revoked_tokens:
            return None

        now = time.time()
        # Clean up expired tokens
        cls._tokens = {t: exp for t, exp in cls._tokens.items() if exp > now}

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
                        user_data = cls._users.get(username.lower(), {"role": "TRADER", "full_name": username.title()})
                        return {
                            "valid": True,
                            "username": username,
                            "role": user_data.get("role", "TRADER"),
                            "full_name": user_data.get("full_name", username.title()),
                            "expires_at": now + cls._token_ttl
                        }
        except Exception:
            pass

        return None

    @classmethod
    def revoke_token(cls, token: Optional[str]) -> bool:
        """
        Revokes the session token on logout, immediately invalidating access.
        """
        if not token:
            return False

        if token.startswith("Bearer "):
            token = token[7:].strip()

        cls._revoked_tokens.add(token)
        cls._tokens.pop(token, None)
        return True

    @classmethod
    def change_password(cls, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """
        Allows an authenticated user to update their password.
        """
        cls._init_default_users()
        user_key = (username or "").strip().lower()
        if not cls.verify_credentials(user_key, old_password):
            return False, "Current password verification failed"

        if len(new_password.strip()) < 6:
            return False, "New password must be at least 6 characters long"

        salt = secrets.token_hex(16)
        pwd_hash = cls._hash_password(new_password.strip(), salt)
        cls._users[user_key]["salt"] = salt
        cls._users[user_key]["password_hash"] = pwd_hash
        return True, "Password updated successfully"


# Auto-initialize default users on module load
RemoteAuthEngine._init_default_users()
