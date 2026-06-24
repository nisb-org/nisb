from __future__ import annotations

import json
import os
from typing import Any, Dict


DEFAULT_EXTERNAL_MCP_ENDPOINT = "https://mcp.nisb.me/nisb/mcp"


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def resolve_external_mcp_endpoint(value: Any = None) -> str:
    explicit = _safe_str(value)
    if explicit:
        return explicit

    env_value = _safe_str(os.environ.get("NISB_EXTERNAL_MCP_ENDPOINT"))
    if env_value:
        return env_value

    return DEFAULT_EXTERNAL_MCP_ENDPOINT


def _json_pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _yaml_quote(value: Any) -> str:
    text = _safe_str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_generic_mcp_config(
    *,
    endpoint_url: str,
    token: str,
    server_name: str = "nisb_room",
) -> Dict[str, Any]:
    server_name = _safe_str(server_name, "nisb_room")
    return {
        "mcpServers": {
            server_name: {
                "type": "streamable-http",
                "url": endpoint_url,
                "headers": {
                    "Authorization": f"Bearer {token}",
                },
            }
        }
    }


def build_librechat_config(
    *,
    endpoint_url: str,
    token: str,
    server_name: str = "nisb_room",
) -> Dict[str, Any]:
    server_name = _safe_str(server_name, "nisb_room")
    return {
        "mcpServers": {
            server_name: {
                "type": "streamable-http",
                "url": endpoint_url,
                "headers": {
                    "Authorization": f"Bearer {token}",
                },
            }
        }
    }


def build_librechat_yaml_text(
    *,
    endpoint_url: str,
    token: str,
    server_name: str = "nisb_room",
) -> str:
    server_name = _safe_str(server_name, "nisb_room")
    return "\n".join(
        [
            "mcpServers:",
            f"  {server_name}:",
            "    type: streamable-http",
            f"    url: {_yaml_quote(endpoint_url)}",
            "    headers:",
            f"      Authorization: {_yaml_quote('Bearer ' + token)}",
        ]
    )


def build_external_mcp_config_bundle(
    *,
    publish: Dict[str, Any],
    plaintext_token: str,
    endpoint_url: str = "",
    server_name: str = "nisb_room",
) -> Dict[str, Any]:
    endpoint = resolve_external_mcp_endpoint(endpoint_url)
    token = _safe_str(plaintext_token)

    generic = build_generic_mcp_config(
        endpoint_url=endpoint,
        token=token,
        server_name=server_name,
    )
    librechat = build_librechat_config(
        endpoint_url=endpoint,
        token=token,
        server_name=server_name,
    )
    librechat_yaml = build_librechat_yaml_text(
        endpoint_url=endpoint,
        token=token,
        server_name=server_name,
    )

    return {
        "endpoint_url": endpoint,
        "server_name": server_name,
        "provider_id": _safe_str(publish.get("provider_id")),
        "source_room_id": _safe_str(publish.get("source_room_id")),
        "token": token,
        "authorization_header": f"Bearer {token}",
        "generic_mcp_config": generic,
        "generic_mcp_config_json": _json_pretty(generic),
        "librechat_config": librechat,
        "librechat_config_json": _json_pretty(librechat),
        "librechat_config_yaml": librechat_yaml,
    }


__all__ = [
    "DEFAULT_EXTERNAL_MCP_ENDPOINT",
    "resolve_external_mcp_endpoint",
    "build_generic_mcp_config",
    "build_librechat_config",
    "build_librechat_yaml_text",
    "build_external_mcp_config_bundle",
]
