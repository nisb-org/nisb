from __future__ import annotations

from typing import Any, Dict

from .room_mcp_provider_contract import (
    normalize_room_mcp_provider_contract,
)
from .room_mcp_provider_descriptor_imported import (
    build_imported_room_mcp_provider_contract as _build_imported_room_mcp_provider_contract,
)
from .room_mcp_provider_descriptor_local import (
    build_room_shared_mcp_provider_contract as _build_room_shared_mcp_provider_contract,
    build_room_shared_mcp_share_ref,
)


def build_room_shared_mcp_provider_contract(
    meta: Dict[str, Any],
    state: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return normalize_room_mcp_provider_contract(
        _build_room_shared_mcp_provider_contract(meta, state),
    )


def build_imported_room_mcp_provider_contract(
    raw: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return normalize_room_mcp_provider_contract(
        _build_imported_room_mcp_provider_contract(raw),
    )


def normalize_room_mcp_provider_descriptor(
    raw: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return normalize_room_mcp_provider_contract(raw)


__all__ = [
    "build_room_shared_mcp_provider_contract",
    "build_room_shared_mcp_share_ref",
    "build_imported_room_mcp_provider_contract",
    "normalize_room_mcp_provider_descriptor",
]
