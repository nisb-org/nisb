from __future__ import annotations

from typing import Any, Dict

from core.storage import load_json

from .room_contracts import require_safe_id
from .room_store import atomic_write_json, room_dir


EXTERNAL_MCP_PUBLISH_FILENAME = "external_mcp_publish.json"


def external_mcp_publish_path(room_id: str) -> str:
    room_id = require_safe_id("room_id", room_id)
    return f"{room_dir(room_id)}/{EXTERNAL_MCP_PUBLISH_FILENAME}"


def load_external_mcp_publish_doc(room_id: str) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    data = load_json(external_mcp_publish_path(room_id))
    return data if isinstance(data, dict) else {}


def save_external_mcp_publish_doc(room_id: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    payload = doc if isinstance(doc, dict) else {}
    atomic_write_json(external_mcp_publish_path(room_id), payload)
    return payload


__all__ = [
    "EXTERNAL_MCP_PUBLISH_FILENAME",
    "external_mcp_publish_path",
    "load_external_mcp_publish_doc",
    "save_external_mcp_publish_doc",
]
