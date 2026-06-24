from __future__ import annotations

from typing import Any, Dict, Optional

import httpx


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _normalize_remote_error(
    *,
    status_code: int = 0,
    response_json: Optional[Dict[str, Any]] = None,
    response_text: str = "",
    message: str = "",
) -> Dict[str, Any]:
    payload = response_json if isinstance(response_json, dict) else {}

    explicit_error_code = _safe_lower(payload.get("error_code") or payload.get("code"))
    explicit_error_kind = _safe_lower(payload.get("error_kind"))
    explicit_user_message = _safe_str(
        payload.get("user_message")
        or payload.get("message")
        or payload.get("error")
        or payload.get("detail")
    )

    text = " | ".join(
        [
            _safe_lower(message),
            _safe_lower(response_text[:2000]),
            _safe_lower(payload.get("user_message")),
            _safe_lower(payload.get("message")),
            _safe_lower(payload.get("error")),
            _safe_lower(payload.get("detail")),
            _safe_lower(payload.get("code")),
            _safe_lower(payload.get("error_code")),
            _safe_lower(payload.get("error_kind")),
        ]
    )

    def _pack(code: str, user_message: str, *, kind: str = "remote_error", retryable: bool = False) -> Dict[str, Any]:
        return {
            "error_kind": kind,
            "error_code": code,
            "user_message": user_message,
            "retryable": retryable,
        }

    if (
        explicit_error_code in {
            "room_access_revoked",
            "member_access_revoked",
            "federated_member_access_revoked",
        }
        or explicit_error_kind in {
            "room_access_revoked",
            "member_access_revoked",
            "federated_member_access_revoked",
        }
        or "room_access_revoked" in text
        or "member_access_revoked" in text
        or "federated_member_access_revoked" in text
    ):
        return _pack(
            "room_access_revoked",
            explicit_user_message or "你对该 federated room 的访问已被房主撤销。",
            kind="room_access_revoked",
            retryable=False,
        )

    if (
        status_code == 401
        or "401" in text
        or "unauthorized" in text
        or "invalid token" in text
        or "token invalid" in text
        or "token expired" in text
        or ("bearer" in text and "invalid" in text)
        or ("bearer" in text and "missing" in text)
    ):
        return _pack(
            "token_invalid",
            explicit_user_message or "peer token 无效或已过期，请更新 token 后重试。",
            kind="auth",
            retryable=True,
        )

    if "invite_expired" in text or "invite expired" in text:
        return _pack(
            "invite_expired",
            explicit_user_message or "invite 已过期，需要房主重新签发。",
            kind="invite",
            retryable=False,
        )

    if "invite_revoked" in text or "invite revoked" in text:
        return _pack(
            "invite_revoked",
            explicit_user_message or "invite 已撤销，不可再接受。",
            kind="invite",
            retryable=False,
        )

    if "invite_used" in text or "invite used" in text or "already used" in text:
        return _pack(
            "invite_used",
            explicit_user_message or "invite 已被使用，不可重复接受。",
            kind="invite",
            retryable=False,
        )

    if "invite_ambiguous" in text or "invite ambiguous" in text:
        return _pack(
            "invite_ambiguous",
            explicit_user_message or "存在多条可匹配 invite，请核对 peer_id / target_peer_id。",
            kind="invite",
            retryable=False,
        )

    if (
        "peer_mismatch" in text
        or "target_peer" in text
        or "peer mismatch" in text
    ):
        return _pack(
            "peer_mismatch",
            explicit_user_message or "invite 与当前 peer 不匹配，请核对 peer_id / target_peer_id。",
            kind="peer",
            retryable=False,
        )

    if "invite_not_active" in text or "invite not active" in text:
        return _pack(
            "invite_not_active",
            explicit_user_message or "invite 当前不是 active 状态。",
            kind="invite",
            retryable=False,
        )

    if "invite_not_found" in text or "invite not found" in text:
        return _pack(
            "invite_not_found",
            explicit_user_message or "invite 不存在，或当前 peer 与 invite 不匹配。",
            kind="invite",
            retryable=False,
        )

    if status_code == 403 or "permission denied" in text or "forbidden" in text or "permission" in text:
        return _pack(
            "permission_denied",
            explicit_user_message or "当前 token 权限不足，不能访问该房间或接口。",
            kind="permission",
            retryable=False,
        )

    if "peer_not_found" in text or "peer not found" in text:
        return _pack(
            "peer_not_found",
            explicit_user_message or "peer 不存在或已禁用。",
            kind="peer",
            retryable=False,
        )

    if status_code == 404 or "room not found" in text or "not found" in text:
        return _pack(
            "room_not_found",
            explicit_user_message or "owner VPS 上未找到该房间或资源。",
            kind="missing",
            retryable=False,
        )

    if (
        status_code == 0
        or "request failed" in text
        or "timed out" in text
        or "timeout" in text
        or "connect" in text
        or "connection refused" in text
        or "name or service not known" in text
        or "temporary failure in name resolution" in text
        or "all connection attempts failed" in text
        or "nodename nor servname provided" in text
    ):
        return _pack(
            "owner_unreachable",
            explicit_user_message or "owner VPS 当前不可达，请检查 base_url 或服务状态。",
            kind="network",
            retryable=True,
        )

    return _pack(
        explicit_error_code or "remote_error",
        explicit_user_message or _safe_str(message) or "远端调用失败。",
        kind=explicit_error_kind or "remote_error",
        retryable=False,
    )


def _is_error_like_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("success") is False:
        return True
    return _safe_lower(payload.get("status")) in {"error", "failed", "fail"}


def _structured_remote_failure(
    payload: Dict[str, Any],
    *,
    fallback_message: str,
    status_code: int = 200,
    response_text: str = "",
) -> Dict[str, Any]:
    src = payload if isinstance(payload, dict) else {}

    norm = _normalize_remote_error(
        status_code=status_code,
        response_json=src,
        response_text=response_text,
        message=_safe_str(src.get("message")) or fallback_message,
    )

    retryable = src.get("retryable")
    if not isinstance(retryable, bool):
        retryable = bool(norm.get("retryable"))

    return {
        "error_code": _safe_str(src.get("error_code") or src.get("code") or norm.get("error_code")) or "remote_error",
        "error_kind": _safe_str(src.get("error_kind") or norm.get("error_kind")) or "remote_error",
        "user_message": _safe_str(
            src.get("user_message")
            or src.get("message")
            or src.get("error")
            or src.get("detail")
            or norm.get("user_message")
            or fallback_message
        ) or fallback_message,
        "retryable": retryable,
    }


def _error_result(
    *,
    message: str,
    error_code: str,
    error_kind: str = "error",
    user_message: str = "",
    retryable: bool = False,
    **extra: Any,
) -> Dict[str, Any]:
    res = {
        "success": False,
        "status": "error",
        "message": message,
        "error_code": error_code,
        "error_kind": error_kind,
        "user_message": user_message or message,
        "retryable": bool(retryable),
    }
    res.update(extra)
    return res

def _build_httpx_timeout(timeout_sec: float) -> httpx.Timeout:
    try:
        total = float(timeout_sec)
    except Exception:
        total = 8.0

    total = max(1.0, total)

    connect_sec = max(1.0, min(total, 10.0))
    read_sec = total
    write_sec = max(1.0, min(total, 30.0))
    pool_sec = max(1.0, min(total, 10.0))

    return httpx.Timeout(
        connect=connect_sec,
        read=read_sec,
        write=write_sec,
        pool=pool_sec,
    )

def _remote_mcp_call(
    *,
    base_url: str,
    token: str,
    tool: str,
    arguments: Dict[str, Any],
    timeout_sec: float,
) -> Dict[str, Any]:
    url = f"{_safe_str(base_url).rstrip('/')}/api/mcp/call"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "tool": _safe_str(tool),
        "arguments": arguments if isinstance(arguments, dict) else {},
    }

    timeout = _build_httpx_timeout(timeout_sec)
    timeout_connect_sec = float(timeout.connect or 0)
    timeout_read_sec = float(timeout.read or 0)
    timeout_write_sec = float(timeout.write or 0)
    timeout_pool_sec = float(timeout.pool or 0)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            raw_text = response.text
            status_code = response.status_code
            try:
                response_json = response.json()
            except Exception:
                response_json = {"raw_text": raw_text}

            common = {
                "status_code": status_code,
                "url": url,
                "tool": tool,
                "response_json": response_json if isinstance(response_json, dict) else {"value": response_json},
                "response_text_preview": raw_text[:2000],
                "auth_mode": "bearer" if token else "none",
                "base_url": base_url,
                "timeout_sec": timeout_sec,
                "timeout_connect_sec": timeout_connect_sec,
                "timeout_read_sec": timeout_read_sec,
                "timeout_write_sec": timeout_write_sec,
                "timeout_pool_sec": timeout_pool_sec,
            }

            if response.is_error:
                norm = _normalize_remote_error(
                    status_code=status_code,
                    response_json=response_json if isinstance(response_json, dict) else {},
                    response_text=raw_text,
                    message=f"remote mcp http error: {status_code}",
                )
                return {
                    "success": False,
                    "status": "error",
                    "message": f"remote mcp http error: {status_code}",
                    **norm,
                    **common,
                }

            return {
                "success": True,
                "status": "success",
                **common,
            }

    except httpx.ConnectTimeout as e:
        return {
            "success": False,
            "status": "error",
            "message": f"remote mcp connect timeout: {e}",
            "error_code": "owner_timeout",
            "error_kind": "network",
            "user_message": "owner VPS 连接超时，请检查 base_url、网络连通性或适当放宽超时。",
            "retryable": True,
            "status_code": 0,
            "url": url,
            "tool": tool,
            "response_json": {},
            "response_text_preview": "",
            "auth_mode": "bearer" if token else "none",
            "base_url": base_url,
            "timeout_sec": timeout_sec,
            "timeout_connect_sec": timeout_connect_sec,
            "timeout_read_sec": timeout_read_sec,
            "timeout_write_sec": timeout_write_sec,
            "timeout_pool_sec": timeout_pool_sec,
            "timeout_stage": "connect",
            "remote_execution_may_have_completed": False,
            "exception_type": type(e).__name__,
        }
    except httpx.ReadTimeout as e:
        return {
            "success": False,
            "status": "error",
            "message": f"remote mcp read timeout: {e}",
            "error_code": "owner_timeout",
            "error_kind": "network",
            "user_message": "owner VPS 响应超时，当前请求可能已到达远端但未在超时内返回。",
            "retryable": True,
            "status_code": 0,
            "url": url,
            "tool": tool,
            "response_json": {},
            "response_text_preview": "",
            "auth_mode": "bearer" if token else "none",
            "base_url": base_url,
            "timeout_sec": timeout_sec,
            "timeout_connect_sec": timeout_connect_sec,
            "timeout_read_sec": timeout_read_sec,
            "timeout_write_sec": timeout_write_sec,
            "timeout_pool_sec": timeout_pool_sec,
            "timeout_stage": "read",
            "remote_execution_may_have_completed": True,
            "exception_type": type(e).__name__,
        }
    except httpx.ConnectError as e:
        return {
            "success": False,
            "status": "error",
            "message": f"remote mcp connect error: {e}",
            "error_code": "owner_unreachable",
            "error_kind": "network",
            "user_message": "owner VPS 当前不可达，请检查 base_url、端口、TLS 或服务状态。",
            "retryable": True,
            "status_code": 0,
            "url": url,
            "tool": tool,
            "response_json": {},
            "response_text_preview": "",
            "auth_mode": "bearer" if token else "none",
            "base_url": base_url,
            "timeout_sec": timeout_sec,
            "timeout_connect_sec": timeout_connect_sec,
            "timeout_read_sec": timeout_read_sec,
            "timeout_write_sec": timeout_write_sec,
            "timeout_pool_sec": timeout_pool_sec,
            "timeout_stage": "connect",
            "remote_execution_may_have_completed": False,
            "exception_type": type(e).__name__,
        }
    except Exception as e:
        norm = _normalize_remote_error(
            status_code=0,
            response_json={},
            response_text="",
            message=f"remote mcp request failed: {e}",
        )
        return {
            "success": False,
            "status": "error",
            "message": f"remote mcp request failed: {e}",
            **norm,
            "status_code": 0,
            "url": url,
            "tool": tool,
            "response_json": {},
            "response_text_preview": "",
            "auth_mode": "bearer" if token else "none",
            "base_url": base_url,
            "timeout_sec": timeout_sec,
            "timeout_connect_sec": timeout_connect_sec,
            "timeout_read_sec": timeout_read_sec,
            "timeout_write_sec": timeout_write_sec,
            "timeout_pool_sec": timeout_pool_sec,
            "timeout_stage": "request",
            "remote_execution_may_have_completed": False,
            "exception_type": type(e).__name__,
        }


__all__ = [
    "_error_result",
    "_is_error_like_payload",
    "_normalize_remote_error",
    "_remote_mcp_call",
    "_structured_remote_failure",
]

