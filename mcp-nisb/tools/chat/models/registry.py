#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict, List, Optional

from tools.i18n.backend_i18n import normalize_backend_locale, text_i18n, pick_i18n


class ModelRegistry:
    _instance = None
    _models_cache: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    PROVIDER_META: Dict[str, Dict[str, str]] = {
        "openai": {"icon": "🤖", "name": "OpenAI"},
        "anthropic": {"icon": "🧠", "name": "Anthropic"},
        "deepseek": {"icon": "🔍", "name": "DeepSeek"},
    }

    OPENAI_FALLBACK_MODELS = [
        ("gpt-5", "GPT-5", text_i18n("New", "🔥 新"), 0),
        ("gpt-5-mini", "GPT-5 Mini", text_i18n("Recommended", "推荐"), 1),
        ("gpt-4o", "GPT-4o", text_i18n("Latest", "最新"), 2),
        ("gpt-4o-mini", "GPT-4o Mini", text_i18n("Recommended", "推荐"), 3),
        ("gpt-4.1", "GPT-4.1", None, 4),
        ("gpt-4.1-mini", "GPT-4.1 Mini", None, 5),
        ("gpt-4-turbo", "GPT-4 Turbo", None, 6),
        ("gpt-3.5-turbo", "GPT-3.5 Turbo", None, 7),
        ("o1-preview", "O1 Preview", text_i18n("Reasoning", "推理"), 8),
        ("o1-mini", "O1 Mini", None, 9),
        ("o3", "O3", text_i18n("Reasoning", "推理"), 10),
        ("o4-mini", "O4 Mini", None, 11),
    ]

    ANTHROPIC_MODELS = [
        ("claude-opus-4-8", "Claude Opus 4.8", text_i18n("Most capable", "最强"), 0),
        ("claude-sonnet-4-6", "Claude Sonnet 4.6", text_i18n("Best balance", "均衡"), 1),
        ("claude-haiku-4-5", "Claude Haiku 4.5", text_i18n("Fastest", "最快"), 2),
        ("claude-opus-4-7", "Claude Opus 4.7", None, 3),
        ("claude-opus-4-6", "Claude Opus 4.6", None, 4),
        ("claude-sonnet-4-5", "Claude Sonnet 4.5", None, 5),
        ("claude-opus-4-1", "Claude Opus 4.1", None, 6),
        ("claude-sonnet-4", "Claude Sonnet 4", None, 7),
        ("claude-opus-4", "Claude Opus 4", None, 8),
        ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", None, 9),
        ("claude-3-haiku-20240307", "Claude 3 Haiku", None, 10),
    ]

    DEEPSEEK_MODELS = [
        ("deepseek-chat", "DeepSeek Chat", None, 0),
        ("deepseek-coder", "DeepSeek Coder", text_i18n("Code", "代码"), 1),
    ]

    OPENAI_ALLOWED_PREFIXES = (
        "gpt-5",
        "gpt-4o",
        "gpt-4.1",
        "gpt-4",
        "gpt-3.5",
        "o1",
        "o3",
        "o4-mini",
    )

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_available_models(
        self,
        refresh: bool = False,
        locale: Any = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        selected_locale = normalize_backend_locale(locale)

        if refresh:
            self.clear_cache()

        cached = self._models_cache.get(selected_locale)
        if cached is not None:
            return cached

        providers: Dict[str, List[Dict[str, Any]]] = {}

        openai_enabled = bool(os.getenv("OPENAI_API_KEY"))
        anthropic_enabled = bool(os.getenv("ANTHROPIC_API_KEY"))
        deepseek_enabled = bool(os.getenv("DEEPSEEK_API_KEY"))

        providers["openai"] = self._get_openai_models(
            enabled=openai_enabled,
            locale=selected_locale,
        )
        providers["anthropic"] = self._build_static_catalog(
            provider="anthropic",
            rows=self.ANTHROPIC_MODELS,
            enabled=anthropic_enabled,
            locale=selected_locale,
        )
        providers["deepseek"] = self._build_static_catalog(
            provider="deepseek",
            rows=self.DEEPSEEK_MODELS,
            enabled=deepseek_enabled,
            locale=selected_locale,
        )

        self._models_cache[selected_locale] = providers
        return providers

    def get_provider_meta(self, provider: str) -> Dict[str, str]:
        key = str(provider or "").strip().lower()
        return dict(self.PROVIDER_META.get(key) or {
            "icon": "🤖",
            "name": key or "Unknown",
        })

    def get_models_for_provider(
        self,
        provider: str,
        refresh: bool = False,
        locale: Any = None,
    ) -> List[Dict[str, Any]]:
        p = str(provider or "").strip().lower()
        return list(self.get_available_models(refresh=refresh, locale=locale).get(p, []))

    def get_flat_models(
        self,
        refresh: bool = False,
        locale: Any = None,
    ) -> List[Dict[str, Any]]:
        providers = self.get_available_models(refresh=refresh, locale=locale)
        out: List[Dict[str, Any]] = []
        for rows in providers.values():
            out.extend(rows)
        return out

    def pick_default_model(
        self,
        *,
        preferred_provider: str = "openai",
        preferred_model: str = "gpt-4o-mini",
        enabled_only: bool = True,
        refresh: bool = False,
        locale: Any = None,
    ) -> Optional[Dict[str, Any]]:
        providers = self.get_available_models(refresh=refresh, locale=locale)
        flat = self.get_flat_models(refresh=False, locale=locale)

        preferred_provider = str(preferred_provider or "openai").strip().lower() or "openai"
        preferred_model = str(preferred_model or "gpt-4o-mini").strip() or "gpt-4o-mini"

        exact = self._find_model(
            provider=preferred_provider,
            model_id=preferred_model,
            flat=flat,
            require_enabled=enabled_only,
        )
        if exact:
            return exact

        picked = self._pick_default_for_provider(
            provider=preferred_provider,
            rows=providers.get(preferred_provider) or [],
            require_enabled=enabled_only,
        )
        if picked:
            return picked

        for provider_name in self._iter_provider_names(preferred_provider):
            picked = self._pick_default_for_provider(
                provider=provider_name,
                rows=providers.get(provider_name) or [],
                require_enabled=enabled_only,
            )
            if picked:
                return picked

        return None

    def resolve_model_selection(
        self,
        *,
        requested_provider: str = "",
        requested_model: str = "",
        default_provider: str = "openai",
        default_model: str = "gpt-4o-mini",
        locale: Any = None,
    ) -> Dict[str, Any]:
        req_provider = str(requested_provider or "").strip().lower()
        req_model = str(requested_model or "").strip()
        def_provider = str(default_provider or "openai").strip().lower() or "openai"
        def_model = str(default_model or "gpt-4o-mini").strip() or "gpt-4o-mini"

        flat = self.get_flat_models(locale=locale)
        providers = self.get_available_models(locale=locale)
        fallback_reason = ""

        if req_provider and req_model:
            match = self._find_model(
                provider=req_provider,
                model_id=req_model,
                flat=flat,
                require_enabled=True,
            )
            if match:
                return {
                    "requested_provider": req_provider,
                    "requested_model": req_model,
                    "applied_provider": match["provider"],
                    "applied_model": match["model_id"],
                    "fallback_reason": "",
                    "resolved": True,
                }

            disabled_match = self._find_model(
                provider=req_provider,
                model_id=req_model,
                flat=flat,
                require_enabled=False,
            )
            fallback_reason = "requested_model_disabled" if disabled_match else "requested_model_unresolved"

        elif not req_provider and req_model:
            inferred = self._find_model_any_provider(
                model_id=req_model,
                flat=flat,
                require_enabled=True,
            )
            if inferred:
                return {
                    "requested_provider": inferred["provider"],
                    "requested_model": req_model,
                    "applied_provider": inferred["provider"],
                    "applied_model": inferred["model_id"],
                    "fallback_reason": "",
                    "resolved": True,
                }

            disabled_inferred = self._find_model_any_provider(
                model_id=req_model,
                flat=flat,
                require_enabled=False,
            )
            fallback_reason = "requested_model_disabled" if disabled_inferred else "requested_model_unresolved"

        elif req_provider and not req_model:
            picked = self._pick_default_for_provider(
                provider=req_provider,
                rows=providers.get(req_provider) or [],
                require_enabled=True,
            )
            if picked:
                return {
                    "requested_provider": req_provider,
                    "requested_model": "",
                    "applied_provider": picked["provider"],
                    "applied_model": picked["model_id"],
                    "fallback_reason": "requested_model_missing",
                    "resolved": True,
                }

            disabled_picked = self._pick_default_for_provider(
                provider=req_provider,
                rows=providers.get(req_provider) or [],
                require_enabled=False,
            )
            fallback_reason = "requested_provider_disabled" if disabled_picked else "requested_provider_unavailable"

        default_pick = self.pick_default_model(
            preferred_provider=def_provider,
            preferred_model=def_model,
            enabled_only=True,
            locale=locale,
        )
        if default_pick:
            return {
                "requested_provider": req_provider,
                "requested_model": req_model,
                "applied_provider": default_pick["provider"],
                "applied_model": default_pick["model_id"],
                "fallback_reason": fallback_reason,
                "resolved": True,
            }

        disabled_default_pick = self.pick_default_model(
            preferred_provider=def_provider,
            preferred_model=def_model,
            enabled_only=False,
            locale=locale,
        )
        if disabled_default_pick:
            return {
                "requested_provider": req_provider,
                "requested_model": req_model,
                "applied_provider": disabled_default_pick["provider"],
                "applied_model": disabled_default_pick["model_id"],
                "fallback_reason": fallback_reason or "no_enabled_models",
                "resolved": False,
            }

        return {
            "requested_provider": req_provider,
            "requested_model": req_model,
            "applied_provider": def_provider,
            "applied_model": def_model,
            "fallback_reason": fallback_reason or "registry_empty",
            "resolved": False,
        }

    def _build_entry(
        self,
        *,
        provider: str,
        model_id: str,
        label: str,
        badge_i18n: Optional[Dict[str, str]] = None,
        family: str = "",
        supports_tools: bool = True,
        supports_stream: bool = True,
        enabled: bool = True,
        aliases: Optional[List[str]] = None,
        priority: int = 99,
        locale: Any = None,
    ) -> Dict[str, Any]:
        alias_rows: List[str] = []
        seen = set()

        for item in aliases or []:
            s = str(item or "").strip()
            if not s:
                continue
            low = s.lower()
            if low in seen:
                continue
            seen.add(low)
            alias_rows.append(s)

        selected_badge = pick_i18n(badge_i18n, locale) if badge_i18n else None

        return {
            "provider": provider,
            "model_id": model_id,
            "value": model_id,
            "label": label,
            "badge": selected_badge,
            "badge_i18n": dict(badge_i18n or {}),
            "family": family or self._infer_family(provider, model_id),
            "supports_tools": bool(supports_tools),
            "supports_stream": bool(supports_stream),
            "enabled": bool(enabled),
            "aliases": alias_rows,
            "priority": int(priority),
        }

    def _build_static_catalog(
        self,
        *,
        provider: str,
        rows: List[tuple],
        enabled: bool,
        locale: Any = None,
    ) -> List[Dict[str, Any]]:
        built = [
            self._build_entry(
                provider=provider,
                model_id=model_id,
                label=label,
                badge_i18n=badge_i18n,
                family=self._infer_family(provider, model_id),
                supports_tools=True,
                supports_stream=True,
                enabled=enabled,
                aliases=self._build_aliases(model_id),
                priority=priority,
                locale=locale,
            )
            for model_id, label, badge_i18n, priority in rows
        ]
        return self._sort_models(built)

    def _get_openai_models(self, enabled: bool, locale: Any = None) -> List[Dict[str, Any]]:
        if not enabled:
            return self._get_openai_fallback_models(enabled=False, locale=locale)

        try:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            print("[DEBUG] Fetching model list from OpenAI API...", file=sys.stderr)

            rows: List[Dict[str, Any]] = []
            seen_ids = set()

            for model in client.models.list().data:
                model_id = str(getattr(model, "id", "") or "").strip()
                if not model_id:
                    continue
                if model_id in seen_ids:
                    continue
                if not self._is_relevant_openai_model(model_id):
                    continue

                seen_ids.add(model_id)
                base_name = self._get_base_model_name(model_id)

                rows.append(
                    self._build_entry(
                        provider="openai",
                        model_id=model_id,
                        label=self._format_model_name(base_name),
                        badge_i18n=self._get_model_badge_i18n(base_name),
                        family=self._infer_family("openai", base_name),
                        supports_tools=True,
                        supports_stream=True,
                        enabled=True,
                        aliases=self._build_aliases(model_id),
                        priority=self._priority_for_model("openai", base_name),
                        locale=locale,
                    )
                )

            rows = self._sort_models(rows)
            print(f"[DEBUG] Fetched {len(rows)} OpenAI models", file=sys.stderr)

            return rows or self._get_openai_fallback_models(enabled=True, locale=locale)

        except Exception as e:
            print(f"[WARN] Failed to fetch OpenAI models: {e}", file=sys.stderr)
            return self._get_openai_fallback_models(enabled=True, locale=locale)

    def _get_openai_fallback_models(self, enabled: bool, locale: Any = None) -> List[Dict[str, Any]]:
        rows = [
            self._build_entry(
                provider="openai",
                model_id=model_id,
                label=label,
                badge_i18n=badge_i18n,
                family=self._infer_family("openai", model_id),
                supports_tools=True,
                supports_stream=True,
                enabled=enabled,
                aliases=self._build_aliases(model_id),
                priority=priority,
                locale=locale,
            )
            for model_id, label, badge_i18n, priority in self.OPENAI_FALLBACK_MODELS
        ]
        return self._sort_models(rows)

    def _is_relevant_openai_model(self, model_id: str) -> bool:
        mid = str(model_id or "").strip().lower()
        return any(mid.startswith(prefix) for prefix in self.OPENAI_ALLOWED_PREFIXES)

    def _build_aliases(self, model_id: str) -> List[str]:
        exact = str(model_id or "").strip()
        base = self._get_base_model_name(exact)
        aliases: List[str] = []

        for item in [exact, base]:
            s = str(item or "").strip()
            if s:
                aliases.append(s)

        return aliases

    def _get_base_model_name(self, model_id: str) -> str:
        text = str(model_id or "").strip()
        if not text:
            return ""

        text = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", text)
        text = re.sub(r"-\d{8}$", "", text)
        return text

    def _get_model_badge_i18n(self, base_name: str) -> Optional[Dict[str, str]]:
        name = str(base_name or "").strip().lower()

        if name == "gpt-5" or name.startswith("gpt-5."):
            return text_i18n("New", "🔥 新")
        if name == "gpt-5-mini":
            return text_i18n("Recommended", "推荐")
        if name == "gpt-4o":
            return text_i18n("Latest", "最新")
        if name == "gpt-4o-mini":
            return text_i18n("Recommended", "推荐")
        if name in ("o1-preview", "o3"):
            return text_i18n("Reasoning", "推理")
        return None

    def _format_model_name(self, model_id: str) -> str:
        base = self._get_base_model_name(model_id).lower()

        mapping = {
            "gpt-5": "GPT-5",
            "gpt-5-mini": "GPT-5 Mini",
            "gpt-4o": "GPT-4o",
            "gpt-4o-mini": "GPT-4o Mini",
            "gpt-4.1": "GPT-4.1",
            "gpt-4.1-mini": "GPT-4.1 Mini",
            "gpt-4-turbo": "GPT-4 Turbo",
            "gpt-4": "GPT-4",
            "gpt-3.5-turbo": "GPT-3.5 Turbo",
            "o1-preview": "O1 Preview",
            "o1-mini": "O1 Mini",
            "o3": "O3",
            "o4-mini": "O4 Mini",
        }

        if base in mapping:
            return mapping[base]

        if base.startswith("gpt-"):
            return base.replace("gpt-", "GPT-").replace("-mini", " Mini").replace("-nano", " Nano").replace("-preview", " Preview")
        if base.startswith("o"):
            return base.upper().replace("-mini", " Mini").replace("-preview", " Preview")

        return str(model_id or "").strip()

    def _infer_family(self, provider: str, model_id: str) -> str:
        p = str(provider or "").strip().lower()
        mid = self._get_base_model_name(model_id).lower()

        if p == "openai":
            if mid.startswith("gpt-5"):
                return "gpt-5"
            if mid.startswith("gpt-4o"):
                return "gpt-4o"
            if mid.startswith("gpt-4.1"):
                return "gpt-4.1"
            if mid.startswith("gpt-4"):
                return "gpt-4"
            if mid.startswith("gpt-3.5"):
                return "gpt-3.5"
            if mid.startswith("o1"):
                return "o1"
            if mid.startswith("o3"):
                return "o3"
            if mid.startswith("o4"):
                return "o4"
        if p == "anthropic":
            if "opus" in mid:
                return "claude-opus"
            if "sonnet" in mid:
                return "claude-sonnet"
            if "haiku" in mid:
                return "claude-haiku"
            return "claude"
        if p == "deepseek":
            if "coder" in mid:
                return "deepseek-coder"
            return "deepseek-chat"
        return p or "unknown"

    def _priority_for_model(self, provider: str, model_id: str) -> int:
        p = str(provider or "").strip().lower()
        mid = self._get_base_model_name(model_id).lower()

        priority_map = {
            ("openai", "gpt-5"): 0,
            ("openai", "gpt-5-mini"): 1,
            ("openai", "gpt-4o"): 2,
            ("openai", "gpt-4o-mini"): 3,
            ("openai", "gpt-4.1"): 4,
            ("openai", "gpt-4.1-mini"): 5,
            ("openai", "gpt-4-turbo"): 6,
            ("openai", "gpt-3.5-turbo"): 7,
            ("openai", "o1-preview"): 8,
            ("openai", "o1-mini"): 9,
            ("openai", "o3"): 10,
            ("openai", "o4-mini"): 11,
            ("anthropic", "claude-sonnet-4-5"): 0,
            ("anthropic", "claude-haiku-4-5"): 1,
            ("anthropic", "claude-opus-4-1"): 2,
            ("anthropic", "claude-sonnet-4"): 3,
            ("anthropic", "claude-opus-4"): 4,
            ("deepseek", "deepseek-chat"): 0,
            ("deepseek", "deepseek-coder"): 1,
        }

        for (pp, prefix), value in priority_map.items():
            if p == pp and mid.startswith(prefix):
                return value
        return 99

    def _snapshot_rank(self, model_id: str) -> int:
        mid = str(model_id or "").strip()
        if not mid:
            return 0

        m = re.search(r"(\d{4}-\d{2}-\d{2})$", mid)
        if m:
            return int(m.group(1).replace("-", ""))

        m = re.search(r"(\d{8})$", mid)
        if m:
            return int(m.group(1))

        return 0

    def _sort_models(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            rows,
            key=lambda x: (
                int(x.get("priority", 99)),
                str(x.get("label") or "").lower(),
                -self._snapshot_rank(str(x.get("model_id") or "")),
                str(x.get("model_id") or "").lower(),
            ),
        )

    def _find_model(
        self,
        *,
        provider: str,
        model_id: str,
        flat: List[Dict[str, Any]],
        require_enabled: bool = True,
    ) -> Optional[Dict[str, Any]]:
        p = str(provider or "").strip().lower()
        mid = str(model_id or "").strip()
        base = self._get_base_model_name(mid).lower()

        for row in flat:
            if str(row.get("provider") or "").strip().lower() != p:
                continue
            if require_enabled and not bool(row.get("enabled")):
                continue

            current = str(row.get("model_id") or "").strip()
            current_base = self._get_base_model_name(current).lower()
            aliases = [str(x).strip().lower() for x in (row.get("aliases") or []) if str(x).strip()]

            if current == mid:
                return row
            if mid.lower() in aliases or base in aliases:
                return row
            if current_base == base:
                return row

        return None

    def _find_model_any_provider(
        self,
        model_id: str,
        *,
        flat: List[Dict[str, Any]],
        require_enabled: bool = True,
    ) -> Optional[Dict[str, Any]]:
        mid = str(model_id or "").strip()
        base = self._get_base_model_name(mid).lower()

        for row in flat:
            if require_enabled and not bool(row.get("enabled")):
                continue

            current = str(row.get("model_id") or "").strip()
            current_base = self._get_base_model_name(current).lower()
            aliases = [str(x).strip().lower() for x in (row.get("aliases") or []) if str(x).strip()]

            if current == mid:
                return row
            if mid.lower() in aliases or base in aliases:
                return row
            if current_base == base:
                return row

        return None

    def _pick_default_for_provider(
        self,
        provider: str,
        rows: List[Dict[str, Any]],
        *,
        require_enabled: bool = True,
    ) -> Optional[Dict[str, Any]]:
        if not rows:
            return None

        target = [x for x in rows if bool(x.get("enabled"))] if require_enabled else list(rows)
        if not target:
            return None

        ordered = self._sort_models(target)
        return ordered[0] if ordered else None

    def _iter_provider_names(self, preferred_provider: str = "") -> List[str]:
        preferred = str(preferred_provider or "").strip().lower()
        base = ["openai", "anthropic", "deepseek"]

        ordered: List[str] = []
        seen = set()

        for item in [preferred] + base:
            s = str(item or "").strip().lower()
            if not s or s in seen:
                continue
            seen.add(s)
            ordered.append(s)

        return ordered

    def clear_cache(self):
        self._models_cache = {}


__all__ = ["ModelRegistry"]

