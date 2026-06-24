from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from tools.i18n.backend_i18n import (
    normalize_backend_locale,
    text_i18n,
    pick_i18n,
    localize_i18n_fields,
)

_PROVIDER_DESCRIPTOR_VERSION = "v1"
_PROVIDER_TYPE_PRESET = "preset"
_PROVIDER_KIND_BUILTIN_EXTERNAL = "builtin_external_mcp"
_PROVIDER_ORIGIN_BUILTIN = "builtin_external"
_DEFAULT_SERVER_TOOL = "nisb_room_mcp_provider_call"
_DEFAULT_REQUESTED_MODE = "mcp"


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _env_configured(name: str) -> bool:
    return bool(_safe_str(os.getenv(name)))


def _auth_state(
    *,
    auth_type: str,
    required: bool,
    configured: bool,
    message_i18n: Dict[str, str],
    locale: Any = None,
    config_key: str = "",
    auth_url: str = "",
    scopes: list[str] | None = None,
) -> Dict[str, Any]:
    return {
        "type": _safe_str(auth_type),
        "required": bool(required),
        "configured": bool(configured),
        "config_key": _safe_str(config_key),
        "auth_url": _safe_str(auth_url),
        "scopes": list(scopes or []),
        "message": pick_i18n(message_i18n, locale),
        "message_i18n": dict(message_i18n or {}),
    }


def _availability(
    *,
    available: bool,
    message_i18n: Dict[str, str],
    locale: Any = None,
    reason: str = "",
) -> Dict[str, Any]:
    return {
        "available": bool(available),
        "reason": _safe_str(reason),
        "message": pick_i18n(message_i18n, locale),
        "message_i18n": dict(message_i18n or {}),
    }


def _boundary_hint(
    *,
    supports_workspace_context: bool,
    supports_focus_root: bool,
    default_inherit_workspace_context: bool,
    default_inherit_focus_root: bool,
    message_i18n: Dict[str, str],
    locale: Any = None,
) -> Dict[str, Any]:
    return {
        "supports_workspace_context": bool(supports_workspace_context),
        "supports_focus_root": bool(supports_focus_root),
        "default_inherit_workspace_context": bool(default_inherit_workspace_context),
        "default_inherit_focus_root": bool(default_inherit_focus_root),
        "message": pick_i18n(message_i18n, locale),
        "message_i18n": dict(message_i18n or {}),
    }


def _normalize_tool_templates(
    value: Any,
    *,
    fallback_tool_name: str = "search",
    fallback_requested_mode: str = _DEFAULT_REQUESTED_MODE,
    locale: Any = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in _safe_list(value):
        row = _safe_dict(item)
        if not row:
            continue
        normalized = localize_i18n_fields(dict(row), locale)
        normalized["tool_name"] = _safe_str(
            normalized.get("tool_name") or normalized.get("name"),
            fallback_tool_name,
        )
        normalized["requested_mode"] = _safe_str(
            normalized.get("requested_mode"),
            fallback_requested_mode,
        )
        out.append(normalized)

    if out:
        return out

    return [
        {
            "tool_name": fallback_tool_name,
            "requested_mode": fallback_requested_mode,
        }
    ]


def _first_tool_name(tool_templates: List[Dict[str, Any]]) -> str:
    for item in tool_templates:
        tool_name = _safe_str(_safe_dict(item).get("tool_name"))
        if tool_name:
            return tool_name
    return "search"


def _string_property(
    *,
    title_i18n: Dict[str, str],
    description_i18n: Optional[Dict[str, str]] = None,
    default: Any = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "type": "string",
        "title_i18n": dict(title_i18n or {}),
    }
    if description_i18n:
        row["description_i18n"] = dict(description_i18n or {})
    if default is not None:
        row["default"] = default
    return row


def _integer_property(
    *,
    title_i18n: Dict[str, str],
    description_i18n: Optional[Dict[str, str]] = None,
    default: int = 0,
    minimum: int = 1,
    maximum: Optional[int] = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "type": "integer",
        "title_i18n": dict(title_i18n or {}),
        "default": int(default),
        "minimum": int(minimum),
    }
    if maximum is not None:
        row["maximum"] = int(maximum)
    if description_i18n:
        row["description_i18n"] = dict(description_i18n or {})
    return row


def _enum_property(
    *,
    title_i18n: Dict[str, str],
    enum: List[str],
    default: str = "",
    description_i18n: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "type": "string",
        "title_i18n": dict(title_i18n or {}),
        "default": _safe_str(default),
        "enum": list(enum or []),
    }
    if description_i18n:
        row["description_i18n"] = dict(description_i18n or {})
    return row


def _params_schema(
    properties: Dict[str, Any],
    required: List[str],
    *,
    locale: Any = None,
) -> Dict[str, Any]:
    return localize_i18n_fields(
        {
            "type": "object",
            "properties": dict(properties or {}),
            "required": list(required or []),
        },
        locale,
    )


def _build_builtin_external_provider_schema(
    *,
    provider_id: str,
    label_i18n: Dict[str, str],
    description_i18n: Dict[str, str],
    tool_templates: List[Dict[str, Any]],
    params_schema: Dict[str, Any],
    params_defaults: Dict[str, Any],
    auth_state: Dict[str, Any],
    availability: Dict[str, Any],
    boundary_hint: Dict[str, Any],
    capabilities: Dict[str, Any],
    locale: Any = None,
) -> Dict[str, Any]:
    normalized_tool_templates = _normalize_tool_templates(tool_templates, locale=locale)
    tool_name = _first_tool_name(normalized_tool_templates)
    requested_mode = _safe_str(
        _safe_dict(normalized_tool_templates[0]).get("requested_mode"),
        _DEFAULT_REQUESTED_MODE,
    )

    return {
        "provider_id": _safe_str(provider_id).lower(),
        "provider_type": _PROVIDER_TYPE_PRESET,
        "provider_kind": _PROVIDER_KIND_BUILTIN_EXTERNAL,
        "provider_origin": _PROVIDER_ORIGIN_BUILTIN,
        "descriptor_version": _PROVIDER_DESCRIPTOR_VERSION,
        "label": pick_i18n(label_i18n, locale),
        "label_i18n": dict(label_i18n or {}),
        "description": pick_i18n(description_i18n, locale),
        "description_i18n": dict(description_i18n or {}),
        "server_tool": _DEFAULT_SERVER_TOOL,
        "tool_name": tool_name,
        "requested_mode": requested_mode,
        "invoke_contract": {
            "server_tool": _DEFAULT_SERVER_TOOL,
            "tool_name": tool_name,
            "requested_mode": requested_mode,
        },
        "tool_templates": normalized_tool_templates,
        "params_schema": dict(params_schema or {}),
        "params_defaults": dict(params_defaults or {}),
        "auth_state": dict(auth_state or {}),
        "availability": dict(availability or {}),
        "boundary_hint": dict(boundary_hint or {}),
        "capabilities": dict(capabilities or {}),
        "provider_origin_meta": {
            "registry_kind": "preset",
            "builtin_external": True,
        },
    }


def _provider_schema_serper(locale: Any = None) -> Dict[str, Any]:
    return _build_builtin_external_provider_schema(
        provider_id="serper",
        label_i18n=text_i18n("Serper Search", "Serper 搜索"),
        description_i18n=text_i18n(
            "Controlled web search provider for Room and worker web-search scenarios.",
            "受控网页搜索 provider；适合 Room / worker 的 web search 场景。",
        ),
        tool_templates=[
            {
                "tool_name": "search",
                "label_i18n": text_i18n("Web search", "网页搜索"),
                "description_i18n": text_i18n(
                    "Run a controlled search and return a concise search-result summary.",
                    "执行受控搜索并返回搜索结果摘要。",
                ),
                "requested_mode": "mcp",
            }
        ],
        params_schema=_params_schema(
            {
                "query": _string_property(
                    title_i18n=text_i18n("Query", "搜索词"),
                    description_i18n=text_i18n(
                        "Defaults to the current user question as the query.",
                        "默认会以当前用户问题作为 query。",
                    ),
                ),
                "num": _integer_property(
                    title_i18n=text_i18n("Number of results", "结果数量"),
                    description_i18n=text_i18n(
                        "Room defaults to 5 results for faster interaction. Increase it explicitly when a larger result set is needed.",
                        "Room 默认收敛到 5，优先交互速度；需要更大结果集时再显式调高。",
                    ),
                    default=5,
                    minimum=1,
                    maximum=10,
                ),
            },
            ["query"],
            locale=locale,
        ),
        params_defaults={
            "query": "{{user_query}}",
            "num": 5,
        },
        auth_state=_auth_state(
            auth_type="service_managed",
            required=False,
            configured=True,
            message_i18n=text_i18n(
                "This provider is managed by the server. No separate authentication is required in Room roles.",
                "当前 provider 由服务端统一配置，无需在 Room 角色中单独填鉴权信息。",
            ),
            locale=locale,
        ),
        availability=_availability(
            available=True,
            reason="",
            message_i18n=text_i18n("Provider is available.", "provider 可用。"),
            locale=locale,
        ),
        boundary_hint=_boundary_hint(
            supports_workspace_context=True,
            supports_focus_root=True,
            default_inherit_workspace_context=False,
            default_inherit_focus_root=False,
            message_i18n=text_i18n(
                "The current Room workspace and focus_root boundaries can be inherited explicitly. They are disabled by default.",
                "可显式继承当前 Room 的 workspace / focus_root 边界；默认关闭。",
            ),
            locale=locale,
        ),
        capabilities={
            "web": True,
            "mcp": True,
            "code": False,
            "fs_read": False,
            "fs_write": False,
        },
        locale=locale,
    )


def _provider_schema_arxiv(locale: Any = None) -> Dict[str, Any]:
    return _build_builtin_external_provider_schema(
        provider_id="arxiv",
        label_i18n=text_i18n("arXiv Papers", "arXiv 论文"),
        description_i18n=text_i18n(
            "Search arXiv papers and metadata for academic papers, preprints, and research leads.",
            "检索 arXiv 论文与元数据，适合学术论文、预印本与研究线索场景。",
        ),
        tool_templates=[
            {
                "tool_name": "search",
                "label_i18n": text_i18n("Paper search", "论文检索"),
                "description_i18n": text_i18n(
                    "Search arXiv papers by keyword and return titles, authors, dates, summaries, and links.",
                    "按关键词搜索 arXiv 论文，返回标题、作者、时间、摘要与链接。",
                ),
                "requested_mode": "mcp",
            }
        ],
        params_schema=_params_schema(
            {
                "query": _string_property(
                    title_i18n=text_i18n("Query", "搜索词"),
                    description_i18n=text_i18n(
                        "Defaults to the current user question. arXiv field queries such as cat:cs.AI AND transformer are also supported.",
                        "默认使用当前用户问题；也可写 arXiv 字段查询，如 cat:cs.AI AND transformer。",
                    ),
                ),
                "max_results": _integer_property(
                    title_i18n=text_i18n("Number of results", "结果数量"),
                    default=5,
                    minimum=1,
                    maximum=10,
                ),
                "sort_by": _enum_property(
                    title_i18n=text_i18n("Sort by", "排序方式"),
                    default="relevance",
                    enum=["relevance", "lastUpdatedDate", "submittedDate"],
                ),
                "sort_order": _enum_property(
                    title_i18n=text_i18n("Sort order", "排序顺序"),
                    default="descending",
                    enum=["ascending", "descending"],
                ),
            },
            ["query"],
            locale=locale,
        ),
        params_defaults={
            "query": "{{user_query}}",
            "max_results": 5,
            "sort_by": "relevance",
            "sort_order": "descending",
        },
        auth_state=_auth_state(
            auth_type="none",
            required=False,
            configured=True,
            message_i18n=text_i18n(
                "The arXiv provider does not require additional authentication.",
                "arXiv provider 当前无需额外鉴权。",
            ),
            locale=locale,
        ),
        availability=_availability(
            available=True,
            reason="",
            message_i18n=text_i18n("Provider is available.", "provider 可用。"),
            locale=locale,
        ),
        boundary_hint=_boundary_hint(
            supports_workspace_context=False,
            supports_focus_root=False,
            default_inherit_workspace_context=False,
            default_inherit_focus_root=False,
            message_i18n=text_i18n(
                "This is an external paper-search provider and does not directly inherit workspace or focus_root file boundaries. Narrow the scope in the query with a topic or category when needed.",
                "这是外部论文检索 provider，不直接继承 workspace / focus_root 文件边界；若需收窄范围，请在搜索词中显式说明主题或类别。",
            ),
            locale=locale,
        ),
        capabilities={
            "web": False,
            "mcp": True,
            "code": False,
            "fs_read": False,
            "fs_write": False,
        },
        locale=locale,
    )


def _provider_schema_pexels(locale: Any = None) -> Dict[str, Any]:
    configured = _env_configured("PEXELS_API_KEY")
    return _build_builtin_external_provider_schema(
        provider_id="pexels",
        label_i18n=text_i18n("Pexels Images", "Pexels 图片"),
        description_i18n=text_i18n(
            "Search browsable image assets for Room and worker visual references, illustrations, and visual exploration.",
            "检索可直接浏览的图片素材，适合 Room / worker 的图片参考、配图和视觉探索场景。",
        ),
        tool_templates=[
            {
                "tool_name": "search",
                "label_i18n": text_i18n("Image search", "图片检索"),
                "description_i18n": text_i18n(
                    "Search images by keyword and return image page links, photographers, and usable image URLs.",
                    "按关键词搜索图片，返回图片页链接、摄影师与可用图片地址。",
                ),
                "requested_mode": "mcp",
            }
        ],
        params_schema=_params_schema(
            {
                "query": _string_property(
                    title_i18n=text_i18n("Query", "搜索词"),
                    description_i18n=text_i18n(
                        "Defaults to the current user question as the query.",
                        "默认会以当前用户问题作为 query。",
                    ),
                ),
                "per_page": _integer_property(
                    title_i18n=text_i18n("Number of results", "结果数量"),
                    default=6,
                    minimum=1,
                    maximum=15,
                ),
                "page": _integer_property(
                    title_i18n=text_i18n("Page", "页码"),
                    default=1,
                    minimum=1,
                ),
                "orientation": _enum_property(
                    title_i18n=text_i18n("Orientation", "方向"),
                    default="",
                    enum=["", "landscape", "portrait", "square"],
                ),
            },
            ["query"],
            locale=locale,
        ),
        params_defaults={
            "query": "{{user_query}}",
            "per_page": 6,
            "page": 1,
            "orientation": "",
        },
        auth_state=_auth_state(
            auth_type="api_key",
            required=True,
            configured=configured,
            config_key="PEXELS_API_KEY",
            message_i18n=text_i18n(
                "Server-side PEXELS_API_KEY is configured. Room roles do not need separate authentication.",
                "需要服务端 PEXELS_API_KEY；当前角色内不单独填写鉴权信息。",
            )
            if configured
            else text_i18n(
                "Missing server-side PEXELS_API_KEY. This provider cannot be executed.",
                "缺少服务端 PEXELS_API_KEY，当前 provider 不可执行。",
            ),
            locale=locale,
        ),
        availability=_availability(
            available=configured,
            reason="" if configured else "missing_env:PEXELS_API_KEY",
            message_i18n=text_i18n("Provider is available.", "provider 可用。")
            if configured
            else text_i18n(
                "Missing server environment variable PEXELS_API_KEY.",
                "缺少服务端环境变量 PEXELS_API_KEY。",
            ),
            locale=locale,
        ),
        boundary_hint=_boundary_hint(
            supports_workspace_context=False,
            supports_focus_root=False,
            default_inherit_workspace_context=False,
            default_inherit_focus_root=False,
            message_i18n=text_i18n(
                "This is an external image-search provider and does not directly inherit workspace or focus_root file boundaries. For better results, specify style, subject, or composition in the query.",
                "这是外部图片检索 provider，不直接继承 workspace / focus_root 文件边界；若需更准确结果，请在搜索词中显式写清风格、主题或构图。",
            ),
            locale=locale,
        ),
        capabilities={
            "web": False,
            "mcp": True,
            "code": False,
            "fs_read": False,
            "fs_write": False,
        },
        locale=locale,
    )


def _provider_schema_exa(locale: Any = None) -> Dict[str, Any]:
    configured = _env_configured("EXA_API_KEY")
    return _build_builtin_external_provider_schema(
        provider_id="exa",
        label_i18n=text_i18n("Exa Search", "Exa 搜索"),
        description_i18n=text_i18n(
            "Search provider for retrieval scenarios such as news, research material, site-focused search, and domain-limited search.",
            "面向检索场景的搜索 provider；适合新闻、研究资料、站点收敛与域名限定搜索。",
        ),
        tool_templates=[
            {
                "tool_name": "search",
                "label_i18n": text_i18n("Advanced search", "高级检索"),
                "description_i18n": text_i18n(
                    "Run semantic search and return titles, links, authors, dates, and summaries or highlights.",
                    "执行语义搜索并返回标题、链接、作者、时间与摘要/高亮。",
                ),
                "requested_mode": "mcp",
            }
        ],
        params_schema=_params_schema(
            {
                "query": _string_property(
                    title_i18n=text_i18n("Query", "搜索词"),
                    description_i18n=text_i18n(
                        "Defaults to the current user question as the query.",
                        "默认会以当前用户问题作为 query。",
                    ),
                ),
                "num_results": _integer_property(
                    title_i18n=text_i18n("Number of results", "结果数量"),
                    default=5,
                    minimum=1,
                    maximum=10,
                ),
                "search_type": _enum_property(
                    title_i18n=text_i18n("Search type", "检索类型"),
                    default="auto",
                    enum=["auto", "neural", "fast", "deep-lite", "deep", "deep-reasoning", "instant"],
                ),
                "category": _enum_property(
                    title_i18n=text_i18n("Category", "类别"),
                    default="",
                    enum=["", "research paper", "news", "company", "people", "personal site", "financial report"],
                ),
                "include_domains": _string_property(
                    title_i18n=text_i18n("Included domains", "限定域名"),
                    description_i18n=text_i18n(
                        "Optional comma-separated or newline-separated domains, such as arxiv.org or paperswithcode.com. Runtime converts the value to the domain array required by the Exa API.",
                        "可选，输入逗号或换行分隔的域名，例如 arxiv.org, paperswithcode.com。执行时会自动转换为 Exa API 需要的域名数组。",
                    ),
                    default="",
                ),
            },
            ["query"],
            locale=locale,
        ),
        params_defaults={
            "query": "{{user_query}}",
            "num_results": 5,
            "search_type": "auto",
            "category": "",
            "include_domains": "",
        },
        auth_state=_auth_state(
            auth_type="api_key",
            required=True,
            configured=configured,
            config_key="EXA_API_KEY",
            message_i18n=text_i18n(
                "Server-side EXA_API_KEY is configured. Room roles do not need separate authentication.",
                "需要服务端 EXA_API_KEY；当前角色内不单独填写鉴权信息。",
            )
            if configured
            else text_i18n(
                "Missing server-side EXA_API_KEY. This provider cannot be executed.",
                "缺少服务端 EXA_API_KEY，当前 provider 不可执行。",
            ),
            locale=locale,
        ),
        availability=_availability(
            available=configured,
            reason="" if configured else "missing_env:EXA_API_KEY",
            message_i18n=text_i18n("Provider is available.", "provider 可用。")
            if configured
            else text_i18n(
                "Missing server environment variable EXA_API_KEY.",
                "缺少服务端环境变量 EXA_API_KEY。",
            ),
            locale=locale,
        ),
        boundary_hint=_boundary_hint(
            supports_workspace_context=False,
            supports_focus_root=False,
            default_inherit_workspace_context=False,
            default_inherit_focus_root=False,
            message_i18n=text_i18n(
                "This is an external retrieval provider and does not directly inherit workspace or focus_root file boundaries. Use included domains or category to narrow the search scope when needed.",
                "这是外部检索 provider，不直接继承 workspace / focus_root 文件边界；建议通过限定域名或 category 显式收窄范围。",
            ),
            locale=locale,
        ),
        capabilities={
            "web": True,
            "mcp": True,
            "code": False,
            "fs_read": False,
            "fs_write": False,
        },
        locale=locale,
    )


def get_room_mcp_provider_registry(locale: Any = None) -> Dict[str, Dict[str, Any]]:
    selected_locale = normalize_backend_locale(locale)
    return {
        "arxiv": _provider_schema_arxiv(selected_locale),
        "exa": _provider_schema_exa(selected_locale),
        "pexels": _provider_schema_pexels(selected_locale),
        "serper": _provider_schema_serper(selected_locale),
    }


__all__ = [
    "get_room_mcp_provider_registry",
]
