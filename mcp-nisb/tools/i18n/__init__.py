from .backend_i18n import (
    DEFAULT_BACKEND_LOCALE,
    SUPPORTED_BACKEND_LOCALES,
    normalize_backend_locale,
    text_i18n,
    pick_i18n,
    localize_i18n_fields,
)

i18n_text = text_i18n

__all__ = [
    "DEFAULT_BACKEND_LOCALE",
    "SUPPORTED_BACKEND_LOCALES",
    "normalize_backend_locale",
    "text_i18n",
    "i18n_text",
    "pick_i18n",
    "localize_i18n_fields",
]
