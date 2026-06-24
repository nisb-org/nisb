"""
Backend i18n helpers for NISB tool descriptors and tool envelope text.

These helpers are for UI-locale-driven backend strings only. They must not be
used to decide Room, Supervisor, RAG, or MCP worker final answer language.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping


DEFAULT_BACKEND_LOCALE = "en"
SUPPORTED_BACKEND_LOCALES = {"en", "zh-CN"}

_LOCALIZABLE_FIELD_NAMES = {
    "label",
    "description",
    "title",
    "message",
    "response",
    "badge",
    "name",
    "placeholder",
    "help",
    "summary",
    "status_text",
}


def normalize_backend_locale(value: Any, default: str = DEFAULT_BACKEND_LOCALE) -> str:
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

    if raw in SUPPORTED_BACKEND_LOCALES:
        return raw

    return default


def backend_locale(value: Any, default: str = DEFAULT_BACKEND_LOCALE) -> str:
    return normalize_backend_locale(value, default=default)


def _mapping_or_none(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _first_nonempty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return ""


def i18n_text(locale: Any, mapping: Mapping[str, Any] | None, default: Any = "") -> str:
    selected = normalize_backend_locale(locale)

    if not isinstance(mapping, Mapping):
        return str(default or "")

    value = _first_nonempty(
        mapping.get(selected),
        mapping.get("en"),
        mapping.get("zh-CN"),
        default,
        "",
    )
    return str(value)


def pick_i18n_text(locale: Any, mapping: Mapping[str, Any] | None, default: Any = "") -> str:
    return i18n_text(locale, mapping, default=default)


def text_i18n(*args: Any, locale: Any = None, default: Any = "", fallback: Any = "", **kwargs: Any) -> str:
    """
    Backward-compatible text picker.

    Supported call styles:
    - text_i18n(locale, mapping, default="")
    - text_i18n(mapping, locale="en", default="")
    - text_i18n(mapping, "en", default="")
    """

    mapping = kwargs.get("mapping")
    selected_locale = locale
    selected_default = _first_nonempty(default, fallback, kwargs.get("default"), kwargs.get("fallback"), "")

    if args:
        if isinstance(args[0], Mapping):
            mapping = args[0]
            if len(args) >= 2 and selected_locale is None:
                selected_locale = args[1]
            if len(args) >= 3:
                selected_default = _first_nonempty(args[2], selected_default)
        else:
            if selected_locale is None:
                selected_locale = args[0]
            if len(args) >= 2:
                mapping = args[1]
            if len(args) >= 3:
                selected_default = _first_nonempty(args[2], selected_default)

    if selected_locale is None:
        selected_locale = kwargs.get("lang") or kwargs.get("language") or kwargs.get("selected_locale") or DEFAULT_BACKEND_LOCALE

    return i18n_text(selected_locale, _mapping_or_none(mapping), default=selected_default)


def pick_i18n(*args: Any, locale: Any = None, default: Any = "", fallback: Any = "", **kwargs: Any) -> str:
    """
    Backward-compatible alias for descriptor and catalog code.

    Supported call styles match text_i18n().
    """

    return text_i18n(*args, locale=locale, default=default, fallback=fallback, **kwargs)


def with_i18n_field(row: Dict[str, Any] | None, field: str, locale: Any) -> Dict[str, Any]:
    out = dict(row or {})
    mapping = out.get(f"{field}_i18n")

    if isinstance(mapping, Mapping):
        out[field] = i18n_text(locale, mapping, out.get(field) or "")

    return out


def with_i18n_fields(
    row: Dict[str, Any] | None,
    fields: Iterable[str] | None,
    locale: Any,
) -> Dict[str, Any]:
    out = dict(row or {})

    for field in fields or ():
        out = with_i18n_field(out, str(field), locale)

    return out


def localize_i18n_fields(value: Any, locale: Any, *, keep_i18n: bool = True) -> Any:
    if isinstance(value, list):
        return [localize_i18n_fields(item, locale, keep_i18n=keep_i18n) for item in value]

    if not isinstance(value, dict):
        return value

    out: Dict[str, Any] = {}

    for key, item in value.items():
        if key.endswith("_i18n"):
            if keep_i18n:
                out[key] = item
            continue

        i18n_key = f"{key}_i18n"
        i18n_mapping = value.get(i18n_key)

        if key in _LOCALIZABLE_FIELD_NAMES and isinstance(i18n_mapping, Mapping):
            out[key] = i18n_text(locale, i18n_mapping, item or "")
            continue

        out[key] = localize_i18n_fields(item, locale, keep_i18n=keep_i18n)

    if keep_i18n:
        for key, item in value.items():
            if key.endswith("_i18n") and key not in out:
                out[key] = item

    return out


def localize_backend_payload(value: Any, locale: Any, *, keep_i18n: bool = True) -> Any:
    return localize_i18n_fields(value, locale, keep_i18n=keep_i18n)


def build_i18n_field(en: Any, zh_cn: Any | None = None) -> Dict[str, str]:
    return {
        "en": str(en or ""),
        "zh-CN": str(zh_cn if zh_cn is not None else en or ""),
    }


def attach_i18n_field(
    row: Dict[str, Any] | None,
    field: str,
    *,
    en: Any,
    zh_cn: Any | None = None,
    selected_locale: Any | None = None,
) -> Dict[str, Any]:
    out = dict(row or {})
    mapping = build_i18n_field(en, zh_cn)
    out[f"{field}_i18n"] = mapping

    if selected_locale is not None:
        out[field] = i18n_text(selected_locale, mapping, out.get(field) or "")
    elif field not in out:
        out[field] = str(en or "")

    return out


__all__ = [
    "DEFAULT_BACKEND_LOCALE",
    "SUPPORTED_BACKEND_LOCALES",
    "normalize_backend_locale",
    "backend_locale",
    "i18n_text",
    "pick_i18n_text",
    "text_i18n",
    "pick_i18n",
    "with_i18n_field",
    "with_i18n_fields",
    "localize_i18n_fields",
    "localize_backend_payload",
    "build_i18n_field",
    "attach_i18n_field",
]
