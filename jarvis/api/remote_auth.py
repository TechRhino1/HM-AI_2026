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
import logging
import bcrypt
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger("JARVIS_RemoteAuth")

# Persistent Secret key for HMAC token signing (auto-generated & stored on disk or loaded from env)
def _get_or_create_secret_key() -> str:
    env_key = os.environ.get("JARVIS_SECRET_KEY")
    if env_key and len(env_key.strip()) >= 16:
        return env_key.strip()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    key_file = os.path.join(base_dir, ".jarvis_secret_key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if len(k) >= 32:
                    return k
        except Exception as e:
            logger.warning(f"Could not read persistent secret key file: {e}")

    new_key = secrets.token_hex(32)
    try:
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(new_key)
    except Exception as e:
        logger.warning(f"Could not write persistent secret key file: {e}")
    return new_key

SECRET_KEY = _get_or_create_secret_key()

# Default Remote Access Admin Credentials (Override via environment variables)
ADMIN_USERNAME = os.environ.get("JARVIS_ADMIN_USER", "admin")

def _resolve_admin_password() -> str:
    """Resolve the admin password from env, else generate + persist a random one (never a known literal)."""
    env_pass = os.environ.get("JARVIS_ADMIN_PASS")
    if env_pass and len(env_pass.strip()) >= 8:
        return env_pass.strip()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pass_file = os.path.join(base_dir, ".jarvis_admin_pass")
    try:
        if os.path.exists(pass_file):
            with open(pass_file, "r", encoding="utf-8") as f:
                existing = f.read().strip()
                if existing:
                    return existing
    except Exception:
        pass
    new_pass = secrets.token_urlsafe(18)
    try:
        with open(pass_file, "w", encoding="utf-8") as f:
            f.write(new_pass)
    except Exception as e:
        logger.warning(f"Could not persist generated admin password: {e}")
    logger.warning(
        "SECURITY NOTICE: JARVIS_ADMIN_PASS not set. Generated a random admin password "
        "(saved to .jarvis_admin_pass). Set JARVIS_ADMIN_PASS to use a fixed password."
    )
    return new_pass

DEFAULT_PASS_RAW = _resolve_admin_password()


class RemoteAuthEngine:
    """
    Secure Authentication and Session Engine for JARVIS AI Remote Web Terminals.
    Includes rate limiting, temporary lockout against brute-force attacks, and persistent HMAC signing.
    """
    _tokens: Dict[str, float] = {}       # token -> expiration timestamp (24h validity)
    _revoked_tokens: set = set()          # set of revoked tokens (logged out)
    _token_ttl: float = 86400.0          # 24 hours in seconds

    # Failed login attempts tracker for brute force protection
    _failed_attempts: Dict[str, List[float]] = {}
    _lockout_duration_sec: float = 60.0
    _max_failed_attempts: int = 5

    # In-memory user database with salted hashes and roles
    _users: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def check_rate_limit(cls, identifier: str) -> Tuple[bool, int]:
        """
        Checks if identifier (IP or username) is currently locked out.
        Returns (is_allowed, seconds_remaining).
        """
        now = time.time()
        key = (identifier or "global").strip().lower()
        attempts = cls._failed_attempts.get(key, [])
        # Retain attempts within last 300 seconds (5 mins)
        attempts = [t for t in attempts if (now - t) < 300.0]
        cls._failed_attempts[key] = attempts

        if len(attempts) >= cls._max_failed_attempts:
            last_attempt = max(attempts)
            elapsed = now - last_attempt
            if elapsed < cls._lockout_duration_sec:
                remaining = max(1, int(cls._lockout_duration_sec - elapsed))
                return False, remaining

        return True, 0

    @classmethod
    def record_failed_attempt(cls, identifier: str):
        now = time.time()
        key = (identifier or "global").strip().lower()
        if key not in cls._failed_attempts:
            cls._failed_attempts[key] = []
        cls._failed_attempts[key].append(now)

    @classmethod
    def record_successful_login(cls, identifier: str):
        key = (identifier or "global").strip().lower()
        cls._failed_attempts.pop(key, None)

    @classmethod
    def _init_default_users(cls):
        """Initializes default institutional users with salted SHA-256 password hashes."""
        if cls._users:
            return

        def _make_user_record(username: str, password_raw: str, role: str, full_name: str) -> Dict[str, Any]:
            salt = secrets.token_hex(16)
            pwd_hash = cls._hash_password(password_raw)
            return {
                "username": username.lower(),
                "role": role,
                "full_name": full_name,
                "salt": salt,
                "password_hash": pwd_hash,
                "created_at": time.time()
            }

        # 1. Primary Admin Account
        admin_pass = DEFAULT_PASS_RAW.strip() if DEFAULT_PASS_RAW else secrets.token_urlsafe(18)
        cls._users["admin"] = _make_user_record("admin", admin_pass, "ADMIN", "System Administrator")

        # 2. Trader Account
        trader_pass = os.environ.get("JARVIS_TRADER_PASS") or secrets.token_urlsafe(16)
        cls._users["trader"] = _make_user_record("trader", trader_pass, "TRADER", "Senior Algo Trader")

        # 3. Viewer/Demo Account
        demo_pass = os.environ.get("JARVIS_DEMO_PASS") or secrets.token_urlsafe(16)
        cls._users["demo"] = _make_user_record("demo", demo_pass, "VIEWER", "Demo Guest Account")

    @classmethod
    def _hash_password(cls, password: str, salt: str = None) -> str:
        """Returns bcrypt hash of password (salt param retained for call compatibility)."""
        pw = password.strip().encode("utf-8")[:72]
        return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")

    @classmethod
    def _verify_password(cls, password: str, stored_hash: str) -> bool:
        """Constant-time verification supporting bcrypt hashes."""
        try:
            if stored_hash.startswith("$2"):
                return bcrypt.checkpw(password.strip().encode("utf-8")[:72], stored_hash.encode("utf-8"))
        except Exception:
            return False
        return False

    @classmethod
    def verify_credentials(cls, username: str, password_raw: str, client_ip: str = "") -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Strictly verifies provided username and password with brute-force rate limiting.
        Returns (user_dict, error_msg).
        """
        cls._init_default_users()
        user_key = (username or "").strip().lower()
        pwd = (password_raw or "").strip()

        # Check rate limits for both IP and username
        allowed_ip, remaining_ip = cls.check_rate_limit(client_ip or "global")
        if not allowed_ip:
            return None, f"Too many failed login attempts. Account locked for {remaining_ip}s."

        allowed_user, remaining_user = cls.check_rate_limit(user_key)
        if not allowed_user:
            return None, f"Too many failed login attempts for user '{user_key}'. Locked for {remaining_user}s."

        if not user_key or not pwd:
            return None, "Username and password required"

        user_data = cls._users.get(user_key)
        if not user_data:
            cls.record_failed_attempt(client_ip or "global")
            cls.record_failed_attempt(user_key)
            return None, "Invalid username or password"

        stored_hash = user_data["password_hash"]

        if cls._verify_password(pwd, stored_hash):
            cls.record_successful_login(client_ip or "global")
            cls.record_successful_login(user_key)
            return {
                "username": user_data["username"],
                "role": user_data["role"],
                "full_name": user_data["full_name"]
            }, ""

        cls.record_failed_attempt(client_ip or "global")
        cls.record_failed_attempt(user_key)
        return None, "Invalid username or password"

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

        pwd_hash = cls._hash_password(new_password.strip())
        cls._users[user_key]["password_hash"] = pwd_hash
        return True, "Password updated successfully"


# Auto-initialize default users on module load
RemoteAuthEngine._init_default_users()
