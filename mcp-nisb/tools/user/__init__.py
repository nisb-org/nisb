#!/usr/bin/env python3
"""
NISB user tools.

These tools expose registration, login, and lightweight account preferences.
Account preferences are used for UI locale persistence only. They must not be
used as Room answer language signals.
"""

import sys
from typing import Any, Dict

sys.path.insert(0, "/srv")

from core.user_system import UserAuthManager, normalize_user_locale


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _resolve_user_id(args: Dict[str, Any]) -> str:
    data = args if isinstance(args, dict) else {}
    return _safe_str(
        data.get("_user_id")
        or data.get("user_id")
        or data.get("current_user_id")
        or data.get("uid")
    )


def _status(success: bool, **payload: Any) -> Dict[str, Any]:
    out = {
        "success": bool(success),
        "status": "success" if success else "error",
    }
    out.update(payload)
    return out


def nisb_user_register(args: dict) -> dict:
    """Register a new NISB user."""
    data = args if isinstance(args, dict) else {}
    email = _safe_str(data.get("email"))
    username = _safe_str(data.get("username"))
    password = _safe_str(data.get("password"))

    if not all([email, username, password]):
        return _status(False, message="❌ Email, username, and password are required.")

    auth_manager = UserAuthManager()
    success, result = auth_manager.register(email, username, password)

    if success:
        return _status(
            True,
            user_id=result["user_id"],
            username=result["username"],
            email=result["email"],
            message=f"✅ Account created. User ID: {result['user_id']}",
        )

    return _status(
        False,
        message=f"❌ Registration failed: {result.get('error', 'Unknown error')}",
    )


def nisb_user_login(args: dict) -> dict:
    """Sign in to a NISB user account."""
    data = args if isinstance(args, dict) else {}
    email = _safe_str(data.get("email"))
    password = _safe_str(data.get("password"))

    if not all([email, password]):
        return _status(False, message="❌ Email and password are required.")

    auth_manager = UserAuthManager()
    success, result = auth_manager.login(email, password)

    if success:
        return _status(
            True,
            user_id=result["user_id"],
            username=result["username"],
            token=result["token"],
            expires_at=result["expires_at"],
            message=f"✅ Signed in. Welcome back, {result['username']}.",
        )

    return _status(
        False,
        message=f"❌ Sign in failed: {result.get('error', 'Invalid email or password')}",
    )


def nisb_user_preferences_get(args: dict) -> dict:
    """Get the current user's UI preferences."""
    user_id = _resolve_user_id(args)
    if not user_id:
        return _status(False, message="Missing user_id.")

    auth_manager = UserAuthManager()
    success, result = auth_manager.get_preferences(user_id)

    if not success:
        return _status(False, message=result.get("error", "Failed to load preferences."))

    return _status(
        True,
        preferences=result,
        locale=result.get("locale", "en"),
        localeExplicit=result.get("localeExplicit", False),
        message="Preferences loaded.",
    )


def nisb_user_preferences_set(args: dict) -> dict:
    """Save the current user's UI preferences."""
    data = args if isinstance(args, dict) else {}
    user_id = _resolve_user_id(data)
    if not user_id:
        return _status(False, message="Missing user_id.")

    locale = normalize_user_locale(data.get("locale"))
    locale_explicit = data.get("localeExplicit")
    if locale_explicit is None:
        locale_explicit = data.get("locale_explicit")
    if locale_explicit is None:
        locale_explicit = True

    auth_manager = UserAuthManager()
    success, result = auth_manager.set_preferences(
        user_id,
        {
            "locale": locale,
            "localeExplicit": bool(locale_explicit),
        },
    )

    if not success:
        return _status(False, message=result.get("error", "Failed to save preferences."))

    return _status(
        True,
        preferences=result,
        locale=result.get("locale", locale),
        localeExplicit=result.get("localeExplicit", True),
        message="Preferences saved.",
    )


__all__ = [
    "nisb_user_register",
    "nisb_user_login",
    "nisb_user_preferences_get",
    "nisb_user_preferences_set",
]
