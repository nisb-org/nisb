#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from core.user_context import auto_user_context
from tools.chat.models.registry import ModelRegistry
from tools.i18n.backend_i18n import normalize_backend_locale


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "on", "y"):
        return True
    if s in ("0", "false", "no", "off", "n"):
        return False

    return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def _message(locale: str, *, provider_count: int, total_models: int, enabled_models: int) -> tuple[str, str]:
    if locale == "zh-CN":
        return (
            f"已返回模型目录，共 {provider_count} 个提供商。",
            f"✅ 提供商 {provider_count} 个，可见模型 {total_models} 个，已启用模型 {enabled_models} 个",
        )

    return (
        f"Loaded model catalog with {provider_count} providers.",
        f"✅ Providers {provider_count}, visible models {total_models}, enabled models {enabled_models}",
    )


@auto_user_context
def nisb_chat_models(args: dict) -> dict:
    args = args or {}
    locale = normalize_backend_locale(args.get("locale"))
    registry = ModelRegistry()

    refresh = _as_bool(args.get("refresh"), False)
    include_disabled = _as_bool(args.get("include_disabled"), True)

    try:
        providers_models = registry.get_available_models(refresh=refresh, locale=locale)
    except TypeError:
        providers_models = registry.get_available_models(refresh=refresh)

    providers = {}

    enabled_provider_count = 0
    enabled_model_count = 0
    total_model_count = 0

    for provider_key in ["openai", "anthropic", "deepseek"]:
        rows = list(providers_models.get(provider_key) or [])
        if not rows:
            continue

        provider_meta = registry.get_provider_meta(provider_key)
        provider_enabled = any(bool(row.get("enabled")) for row in rows)
        visible_rows = rows if include_disabled else [row for row in rows if bool(row.get("enabled"))]

        if not visible_rows:
            continue

        if provider_enabled:
            enabled_provider_count += 1

        enabled_model_count += len([row for row in rows if bool(row.get("enabled"))])
        total_model_count += len(visible_rows)

        providers[provider_key] = {
            "icon": provider_meta.get("icon") or "🤖",
            "name": provider_meta.get("name") or provider_key,
            "enabled": provider_enabled,
            "models": visible_rows,
        }

    try:
        default_entry = registry.pick_default_model(
            preferred_provider="openai",
            preferred_model="gpt-4o-mini",
            enabled_only=True,
            refresh=False,
            locale=locale,
        ) or registry.pick_default_model(
            preferred_provider="openai",
            preferred_model="gpt-4o-mini",
            enabled_only=False,
            refresh=False,
            locale=locale,
        )
    except TypeError:
        default_entry = registry.pick_default_model(
            preferred_provider="openai",
            preferred_model="gpt-4o-mini",
            enabled_only=True,
            refresh=False,
        ) or registry.pick_default_model(
            preferred_provider="openai",
            preferred_model="gpt-4o-mini",
            enabled_only=False,
            refresh=False,
        )

    default_model = _safe_str((default_entry or {}).get("model_id"), "gpt-4o-mini")
    default_provider = _safe_str((default_entry or {}).get("provider"), "openai")

    response, message = _message(
        locale,
        provider_count=len(providers),
        total_models=total_model_count,
        enabled_models=enabled_model_count,
    )

    tool_results = {
        "providers": providers,
        "default_model": default_model,
        "default_provider": default_provider,
        "provider_count": len(providers),
        "enabled_provider_count": enabled_provider_count,
        "total_models": total_model_count,
        "enabled_models": enabled_model_count,
        "include_disabled": include_disabled,
        "locale": locale,
    }

    return {
        "status": "success",
        "response": response,
        "message": message,
        "tool_results": tool_results,
        "providers": providers,
        "default": default_model,
        "total": total_model_count,
    }


__all__ = ["nisb_chat_models"]
