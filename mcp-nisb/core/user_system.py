#!/usr/bin/env python3
"""
NISB standalone user system.

This module manages local users, sessions, and lightweight account profile
preferences. UI locale preferences are stored inside the existing users.profile
JSON field to avoid a release-time database migration.
"""

import os
import json
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple

NISB_USER_SYSTEM_ENABLED = os.environ.get("NISB_USER_SYSTEM_ENABLED", "false").lower() == "true"
NISB_REGISTRATION_ENABLED = os.environ.get("NISB_REGISTRATION_ENABLED", "true").lower() == "true"

NISB_TOKEN_EXPIRY_SECONDS = int(os.environ.get("NISB_TOKEN_EXPIRY_SECONDS", str(30 * 24 * 3600)))
NISB_TOKEN_SLIDING = os.environ.get("NISB_TOKEN_SLIDING", "true").lower() == "true"
NISB_TOKEN_REFRESH_THRESHOLD_SECONDS = int(
    os.environ.get("NISB_TOKEN_REFRESH_THRESHOLD_SECONDS", str(12 * 3600))
)

DEFAULT_USER_LOCALE = "en"
SUPPORTED_USER_LOCALES = {"en", "zh-CN"}


def normalize_user_locale(value: Any, default: str = DEFAULT_USER_LOCALE) -> str:
    raw = str(value or "").strip().replace("_", "-")
    lowered = raw.lower()

    if lowered in {"zh", "zh-cn", "zh-hans"}:
        return "zh-CN"
    if lowered.startswith("zh-"):
        return "zh-CN"
    if lowered in {"en", "en-us", "en-gb"}:
        return "en"
    if lowered.startswith("en-"):
        return "en"

    return raw if raw in SUPPORTED_USER_LOCALES else default


def _json_obj(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    try:
        value = json.loads(str(raw or "{}"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _bool_pref(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return default


class UserDatabase:
    """SQLite-backed user database."""

    DB_PATH = "/data/nisb_users.db"

    def __init__(self):
        self.conn = None
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(self.DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT,
                is_active BOOLEAN DEFAULT 1,
                profile TEXT DEFAULT '{}'
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS permissions (
                user_id TEXT PRIMARY KEY,
                roles TEXT DEFAULT '["user"]',
                permissions TEXT DEFAULT '["read:own", "write:own"]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invitations (
                invitation_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL,
                created_by TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                used_by TEXT,
                used_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users(user_id),
                FOREIGN KEY (used_by) REFERENCES users(user_id)
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT NOT NULL,
                resource TEXT,
                details TEXT,
                timestamp TEXT NOT NULL,
                ip_address TEXT
            )
        """
        )
        self.conn.commit()

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class UserAuthManager:
    """User authentication and profile preference manager."""

    def __init__(self):
        self.db = UserDatabase()
        self.secret_key = os.environ.get("NISB_SECRET_KEY", "nisb-secret-dev")
        self.token_expiry = max(0, int(NISB_TOKEN_EXPIRY_SECONDS))

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        )
        return f"{salt}${pwd_hash.hex()}"

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        try:
            salt, pwd_hash = password_hash.split("$")
            new_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                100000,
            )
            return new_hash.hex() == pwd_hash
        except Exception:
            return False

    def register(self, email: str, username: str, password: str) -> Tuple[bool, Dict]:
        if not NISB_USER_SYSTEM_ENABLED:
            return False, {"error": "NISB user system is not enabled"}

        if not NISB_REGISTRATION_ENABLED:
            return False, {"error": "Registration is disabled"}

        try:
            if not all([email, username, password]) or len(password) < 8:
                return False, {"error": "Invalid registration parameters"}

            existing = self.db.execute(
                "SELECT * FROM users WHERE email = ? OR username = ?",
                (email, username),
            ).fetchone()
            if existing:
                return False, {"error": "User already exists"}

            user_id = f"nisb_{secrets.token_hex(8)}"
            password_hash = self.hash_password(password)
            now = datetime.now().isoformat()

            profile = {
                "name": username,
                "preferences": {
                    "locale": DEFAULT_USER_LOCALE,
                    "localeExplicit": False,
                },
            }

            self.db.execute(
                "INSERT INTO users (user_id, email, username, password_hash, created_at, profile) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, email, username, password_hash, now, json.dumps(profile, ensure_ascii=False)),
            )

            self.db.execute(
                "INSERT INTO permissions (user_id, created_at) VALUES (?, ?)",
                (user_id, now),
            )
            self.db.commit()

            return True, {"user_id": user_id, "username": username, "email": email}
        except Exception as e:
            return False, {"error": str(e)}

    def login(self, email: str, password: str) -> Tuple[bool, Dict]:
        if not NISB_USER_SYSTEM_ENABLED:
            return False, {"error": "NISB user system is not enabled"}

        try:
            user = self.db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not user or not self.verify_password(password, user["password_hash"]) or not user["is_active"]:
                return False, {"error": "Invalid email or password"}

            token = f"{user['user_id']}_{secrets.token_hex(32)}"
            session_id = f"session_{secrets.token_hex(16)}"
            now = datetime.now()

            if self.token_expiry <= 0:
                expires_at = (now + timedelta(days=3650)).isoformat()
            else:
                expires_at = (now + timedelta(seconds=self.token_expiry)).isoformat()

            self.db.execute(
                "INSERT INTO sessions (session_id, user_id, token, created_at, expires_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
                (session_id, user["user_id"], token, now.isoformat(), expires_at),
            )
            self.db.execute(
                "UPDATE users SET last_login = ? WHERE user_id = ?",
                (now.isoformat(), user["user_id"]),
            )
            self.db.commit()

            return True, {
                "user_id": user["user_id"],
                "username": user["username"],
                "token": token,
                "expires_at": expires_at,
            }
        except Exception as e:
            return False, {"error": str(e)}

    def verify_token(self, token: str) -> Tuple[bool, str]:
        if not NISB_USER_SYSTEM_ENABLED:
            return False, ""

        try:
            tok = (token or "").strip()
            if not tok:
                return False, ""

            session = self.db.execute(
                "SELECT * FROM sessions WHERE token = ? AND is_active = 1",
                (tok,),
            ).fetchone()
            if not session:
                return False, ""

            expires_at = datetime.fromisoformat(session["expires_at"])
            now = datetime.now()

            if now > expires_at:
                try:
                    self.db.execute("UPDATE sessions SET is_active = 0 WHERE token = ?", (tok,))
                    self.db.commit()
                except Exception:
                    pass
                return False, ""

            if NISB_TOKEN_SLIDING and self.token_expiry > 0:
                remaining = (expires_at - now).total_seconds()
                if remaining < max(60, int(NISB_TOKEN_REFRESH_THRESHOLD_SECONDS)):
                    new_expires_at = (now + timedelta(seconds=self.token_expiry)).isoformat()
                    self.db.execute(
                        "UPDATE sessions SET expires_at = ? WHERE token = ?",
                        (new_expires_at, tok),
                    )
                    self.db.commit()

            return True, session["user_id"]
        except Exception:
            return False, ""

    def get_user_profile(self, user_id: str) -> Tuple[bool, Dict[str, Any]]:
        uid = str(user_id or "").strip()
        if not uid:
            return False, {"error": "Missing user_id"}

        try:
            row = self.db.execute(
                "SELECT profile FROM users WHERE user_id = ? AND is_active = 1",
                (uid,),
            ).fetchone()
            if not row:
                return False, {"error": "User not found"}

            return True, _json_obj(row["profile"])
        except Exception as e:
            return False, {"error": str(e)}

    def save_user_profile(self, user_id: str, profile: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        uid = str(user_id or "").strip()
        if not uid:
            return False, {"error": "Missing user_id"}

        try:
            row = self.db.execute(
                "SELECT user_id FROM users WHERE user_id = ? AND is_active = 1",
                (uid,),
            ).fetchone()
            if not row:
                return False, {"error": "User not found"}

            clean_profile = profile if isinstance(profile, dict) else {}
            self.db.execute(
                "UPDATE users SET profile = ? WHERE user_id = ?",
                (json.dumps(clean_profile, ensure_ascii=False), uid),
            )
            self.db.commit()

            return True, clean_profile
        except Exception as e:
            return False, {"error": str(e)}

    def get_preferences(self, user_id: str) -> Tuple[bool, Dict[str, Any]]:
        ok, profile = self.get_user_profile(user_id)
        if not ok:
            return False, profile

        prefs = profile.get("preferences")
        if not isinstance(prefs, dict):
            prefs = {}

        settings = profile.get("settings")
        if not isinstance(settings, dict):
            settings = {}

        explicit = _bool_pref(
            prefs.get("localeExplicit", prefs.get("locale_explicit", settings.get("localeExplicit", settings.get("locale_explicit")))),
            False,
        )

        locale_source = prefs.get("locale") or settings.get("locale") or profile.get("locale")
        locale = normalize_user_locale(locale_source)

        return True, {
            "locale": locale if explicit else DEFAULT_USER_LOCALE,
            "localeExplicit": explicit,
        }

    def set_preferences(self, user_id: str, preferences: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        uid = str(user_id or "").strip()
        if not uid:
            return False, {"error": "Missing user_id"}

        prefs_in = preferences if isinstance(preferences, dict) else {}
        locale = normalize_user_locale(prefs_in.get("locale"))
        explicit = _bool_pref(
            prefs_in.get("localeExplicit", prefs_in.get("locale_explicit")),
            True,
        )

        ok, profile = self.get_user_profile(uid)
        if not ok:
            return False, profile

        existing = profile.get("preferences")
        if not isinstance(existing, dict):
            existing = {}

        existing["locale"] = locale
        existing["localeExplicit"] = explicit

        profile["preferences"] = existing

        ok, saved_or_error = self.save_user_profile(uid, profile)
        if not ok:
            return False, saved_or_error

        return True, {
            "locale": locale,
            "localeExplicit": explicit,
        }
