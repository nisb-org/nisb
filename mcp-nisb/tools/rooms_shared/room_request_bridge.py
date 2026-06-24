from __future__ import annotations

import json
import os
from importlib import import_module
from typing import Any, Dict, List, Optional, Tuple

from ..chat.models.registry import ModelRegistry
from .room_binding_policy import (
    _normalize_mode_used,
    _role_kb,
)
from .room_audit_helpers import _build_dialog_lines, _load_room_state
from .room_packet_builder import (
    _bridge_chat_result,
    _coerce_dict_list,
    _coerce_str_list,
    _empty_evidence_result,
    _ensure_formal_packet,
    _normalize_qascope_packet,
)
from .supervisor_runtime.prompt_input import _extract_user_question


class MissingLLMDependencyError(RuntimeError):
    pass


class MissingAnthropicDependencyError(RuntimeError):
    pass


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _get_int(args: Dict[str, Any], keys: List[str], default: int, lower: int, upper: int) -> int:
    for key in keys:
        if key not in args:
            continue
        try:
            n = int(args.get(key))
            return max(lower, min(upper, n))
        except Exception:
            continue
    return default


def _get_str(args: Dict[str, Any], keys: List[str], default: str = "") -> str:
    for key in keys:
        if key not in args:
            continue
        s = _safe_str(args.get(key))
        if s:
            return s
    return default


def _parse_optional_float(value: Any) -> Optional[float]:
    s = _safe_str(value)
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _parse_optional_int(value: Any) -> Optional[int]:
    s = _safe_str(value)
    if not s:
        return None
    try:
        return max(1, int(s))
    except Exception:
        return None


def _extract_llm_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        for key in ("response", "answer", "content", "text", "output", "message"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return str(result).strip()


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    s = _safe_str(text)
    if not s:
        raise ValueError("empty llm json text")

    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 3:
            s = "\n".join(lines[1:-1]).strip()

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        obj = json.loads(s[start:end + 1])
        if isinstance(obj, dict):
            return obj

    raise ValueError("llm json parse failed")


def _get_call_llm():
    imports = [
        ("core.openai_utils", "call_llm"),
        ("tools.openai_utils", "call_llm"),
        ("openai_utils", "call_llm"),
    ]
    last_error: Optional[Exception] = None
    for mod_name, attr_name in imports:
        try:
            mod = import_module(mod_name)
            fn = getattr(mod, attr_name, None)
            if callable(fn):
                return fn
        except ModuleNotFoundError as e:
            last_error = e
            continue
        except Exception as e:
            last_error = e
            continue
    if isinstance(last_error, ModuleNotFoundError) and getattr(last_error, "name", "") == "openai":
        raise MissingLLMDependencyError("当前环境缺少 openai 依赖，导致 call_llm 无法加载。")
    raise MissingLLMDependencyError("call_llm is unavailable")


def _call_llm_raw(**kwargs):
    call_llm = _get_call_llm()
    return call_llm(**kwargs)


def _extract_anthropic_text(result: Any) -> str:
    blocks = getattr(result, "content", None) or []
    texts: List[str] = []
    for block in blocks:
        if getattr(block, "type", "") == "text":
            txt = getattr(block, "text", "")
            if txt:
                texts.append(str(txt))
    return "\n".join(texts).strip()


def _call_openai_text(
    *,
    model_name: str,
    user_prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    try:
        kwargs: Dict[str, Any] = {"model": model_name, "user_prompt": user_prompt, "system_prompt": system_prompt}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        result = _call_llm_raw(**kwargs)
        text = _extract_llm_text(result)
        if text:
            return text
    except TypeError:
        pass
    except MissingLLMDependencyError:
        raise
    except Exception:
        pass

    combined = f"{system_prompt.strip()}\n\n{user_prompt.strip()}".strip()
    kwargs = {"model": model_name, "user_prompt": combined}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    try:
        result = _call_llm_raw(**kwargs)
    except TypeError:
        kwargs.pop("temperature", None)
        kwargs.pop("max_tokens", None)
        result = _call_llm_raw(**kwargs)
    return _extract_llm_text(result)


def _call_openai_json(
    *,
    model_name: str,
    user_prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {"model": model_name, "user_prompt": user_prompt, "system_prompt": system_prompt, "response_format": "json"}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    try:
        result = _call_llm_raw(**kwargs)
        if isinstance(result, dict):
            return result
        return _extract_json_from_text(_extract_llm_text(result))
    except TypeError:
        combined = f"{system_prompt.strip()}\n\n{user_prompt.strip()}".strip()
        fallback_kwargs = {"model": model_name, "user_prompt": combined}
        result = _call_llm_raw(**fallback_kwargs)
        if isinstance(result, dict):
            return result
        return _extract_json_from_text(_extract_llm_text(result))
    except MissingLLMDependencyError:
        raise


def _get_anthropic_client():
    try:
        from anthropic import Anthropic
    except Exception as e:
        raise MissingAnthropicDependencyError(f"anthropic_sdk_unavailable: {e}") from e
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise MissingAnthropicDependencyError("anthropic_api_key_missing")
    return Anthropic(api_key=api_key)


def _call_anthropic_text(
    *,
    model_name: str,
    user_prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    client = _get_anthropic_client()
    kwargs: Dict[str, Any] = {
        "model": model_name,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": max_tokens or 2048,
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    if temperature is not None:
        kwargs["temperature"] = max(0.0, min(1.0, float(temperature)))
    result = client.messages.create(**kwargs)
    return _extract_anthropic_text(result)


def _call_anthropic_json(
    *,
    model_name: str,
    user_prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    text = _call_anthropic_text(
        model_name=model_name,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return _extract_json_from_text(text)


def _resolve_runtime_model_config(
    *,
    requested_provider: str,
    requested_model: str,
    fallback_model: str,
    default_provider: str = "openai",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    registry = ModelRegistry()
    resolved = registry.resolve_model_selection(
        requested_provider=_safe_str(requested_provider).lower(),
        requested_model=_safe_str(requested_model),
        default_provider=_safe_str(default_provider, "openai").lower() or "openai",
        default_model=_safe_str(fallback_model, "gpt-4o-mini") or "gpt-4o-mini",
    )
    return {
        "requested_provider": _safe_str(requested_provider).lower(),
        "requested_model": _safe_str(requested_model),
        "applied_provider": _safe_str(resolved.get("applied_provider"), "openai") or "openai",
        "applied_model": _safe_str(resolved.get("applied_model"), fallback_model or "gpt-4o-mini") or "gpt-4o-mini",
        "fallback_reason": _safe_str(resolved.get("fallback_reason")),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def _call_model_text_with_runtime(
    *,
    model_name: str,
    provider_name: str = "",
    user_prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Tuple[str, Dict[str, Any]]:
    runtime = _resolve_runtime_model_config(
        requested_provider=provider_name,
        requested_model=model_name,
        fallback_model=model_name or "gpt-4o-mini",
        default_provider="openai",
        temperature=temperature,
        max_tokens=max_tokens,
    )
    try:
        if runtime["applied_provider"] == "anthropic":
            text = _call_anthropic_text(
                model_name=runtime["applied_model"],
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=runtime.get("temperature"),
                max_tokens=runtime.get("max_tokens"),
            )
        else:
            text = _call_openai_text(
                model_name=runtime["applied_model"],
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=runtime.get("temperature"),
                max_tokens=runtime.get("max_tokens"),
            )
        return text, runtime
    except Exception as e:
        if runtime["applied_provider"] != "openai":
            fallback_runtime = _resolve_runtime_model_config(
                requested_provider="openai",
                requested_model="gpt-4o-mini",
                fallback_model="gpt-4o-mini",
                default_provider="openai",
                temperature=temperature,
                max_tokens=max_tokens,
            )
            fallback_runtime["fallback_reason"] = runtime.get("fallback_reason") or f"provider_call_failed:{runtime['applied_provider']}:{type(e).__name__}"
            text = _call_openai_text(
                model_name=fallback_runtime["applied_model"],
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=fallback_runtime.get("temperature"),
                max_tokens=fallback_runtime.get("max_tokens"),
            )
            return text, fallback_runtime
        raise


def _call_model_json_with_runtime(
    *,
    model_name: str,
    provider_name: str = "",
    user_prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    runtime = _resolve_runtime_model_config(
        requested_provider=provider_name,
        requested_model=model_name,
        fallback_model=model_name or "gpt-4o-mini",
        default_provider="openai",
        temperature=temperature,
        max_tokens=max_tokens,
    )
    try:
        if runtime["applied_provider"] == "anthropic":
            data = _call_anthropic_json(
                model_name=runtime["applied_model"],
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=runtime.get("temperature"),
                max_tokens=runtime.get("max_tokens"),
            )
        else:
            data = _call_openai_json(
                model_name=runtime["applied_model"],
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=runtime.get("temperature"),
                max_tokens=runtime.get("max_tokens"),
            )
        return data, runtime
    except Exception as e:
        if runtime["applied_provider"] != "openai":
            fallback_runtime = _resolve_runtime_model_config(
                requested_provider="openai",
                requested_model="gpt-4o-mini",
                fallback_model="gpt-4o-mini",
                default_provider="openai",
                temperature=temperature,
                max_tokens=max_tokens,
            )
            fallback_runtime["fallback_reason"] = runtime.get("fallback_reason") or f"provider_call_failed:{runtime['applied_provider']}:{type(e).__name__}"
            data = _call_openai_json(
                model_name=fallback_runtime["applied_model"],
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=fallback_runtime.get("temperature"),
                max_tokens=fallback_runtime.get("max_tokens"),
            )
            return data, fallback_runtime
        raise


def _call_model_text(
    *,
    model_name: str,
    provider_name: str = "",
    user_prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    text, _ = _call_model_text_with_runtime(
        model_name=model_name,
        provider_name=provider_name,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return text


def _call_model_json(
    *,
    model_name: str,
    provider_name: str = "",
    user_prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    data, _ = _call_model_json_with_runtime(
        model_name=model_name,
        provider_name=provider_name,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return data


def _call_llm_json(
    *,
    model_name: str = "",
    user_prompt: str = "",
    system_prompt: str = "",
    provider_name: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    resolved_model_name = _safe_str(model_name or kwargs.get("model"), "gpt-4o-mini") or "gpt-4o-mini"
    resolved_user_prompt = _safe_str(user_prompt or kwargs.get("prompt") or kwargs.get("user") or kwargs.get("input"))
    resolved_system_prompt = _safe_str(system_prompt or kwargs.get("system") or kwargs.get("system_prompt"))
    resolved_provider_name = _safe_str(provider_name or kwargs.get("provider_name") or kwargs.get("provider")).lower()
    resolved_temperature = temperature if temperature is not None else _parse_optional_float(kwargs.get("temperature"))
    resolved_max_tokens = max_tokens if max_tokens is not None else _parse_optional_int(kwargs.get("max_tokens"))
    return _call_model_json(
        model_name=resolved_model_name,
        provider_name=resolved_provider_name,
        user_prompt=resolved_user_prompt,
        system_prompt=resolved_system_prompt,
        temperature=resolved_temperature,
        max_tokens=resolved_max_tokens,
    )


def _normalize_room_mode(value: Any, default: str = "off") -> str:
    s = _safe_str(value, default).lower()
    if s == "web":
        return "web"
    return _normalize_mode_used(s or default, default)


def _supervisor_runtime_request(room_state: Dict[str, Any], fallback_model: str) -> Dict[str, Any]:
    return {
        "provider_name": _safe_str(room_state.get("supervisor_provider")).lower(),
        "model_name": _safe_str(room_state.get("supervisor_model"), fallback_model) or fallback_model or "gpt-4o-mini",
        "temperature": _parse_optional_float(room_state.get("supervisor_temperature")),
        "max_tokens": _parse_optional_int(room_state.get("supervisor_max_tokens")),
    }


def _call_room_plain_reply(room_id: str, question: str, model_name: str) -> str:
    dialog = _build_dialog_lines(room_id, limit=30)
    prompt = "你在一个多人房间里协作。\n请基于下面对话给出简洁、可执行的回复。\n\n" + "\n".join(dialog) + f"\n\n用户对你说：{question}"
    return _call_model_text(model_name=model_name, user_prompt=prompt)


def _merge_delegate_ids_with_all_active(all_ids: List[str], requested_ids: List[str]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for item in requested_ids + all_ids:
        role_id = str(item or "").strip()
        if not role_id or role_id in seen or role_id not in all_ids:
            continue
        seen.add(role_id)
        ordered.append(role_id)
    return ordered or list(all_ids)


def _call_supervisor_plan(
    *,
    question: str,
    active_roles: List[Dict[str, Any]],
    model_name: str,
    room_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    all_ids = [str(r.get("role_id") or "").strip() for r in active_roles if str(r.get("role_id") or "").strip()]
    role_lines: List[str] = []
    for r in active_roles:
        kb = _role_kb(r)
        role_lines.append(
            f"- role_id={_safe_str(r.get('role_id'))} name={_safe_str(r.get('name'))} slug={_safe_str(r.get('slug'))} library_id={_safe_str(kb.get('library_id') or kb.get('libraryid'))} doc_id={_safe_str(kb.get('doc_id') or kb.get('docid'))} system_prompt={_safe_str(r.get('system_prompt'))[:120]}"
        )
    system_prompt = (
        "你是多角色房间的 Supervisor 编排器。\n"
        "你的任务是根据用户问题，为全部已激活角色安排最合适的执行顺序。\n"
        "默认必须覆盖全部已激活角色，不要遗漏任何一个有效角色。\n"
        "你只负责排序和简短计划摘要，不要裁剪掉用户已经激活的角色。\n"
        "严格只输出 JSON，不要输出解释。\n"
        'JSON 结构必须为：{"delegate_role_ids":["role_x","role_y"],"plan_summary":"..."}'
    )
    user_prompt = f"用户问题：{question}\n\n可用角色：\n" + "\n".join(role_lines)
    current_state = room_state if isinstance(room_state, dict) else {}
    rt_request = _supervisor_runtime_request(current_state, model_name)
    try:
        data, runtime = _call_model_json_with_runtime(
            model_name=rt_request["model_name"],
            provider_name=rt_request["provider_name"],
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=rt_request["temperature"],
            max_tokens=rt_request["max_tokens"],
        )
        ids = data.get("delegate_role_ids")
        if isinstance(ids, list):
            cleaned = [str(x).strip() for x in ids if str(x).strip()]
            cleaned = [x for x in cleaned if x in all_ids]
            ordered_ids = _merge_delegate_ids_with_all_active(all_ids, cleaned)
            if ordered_ids:
                return {
                    "delegate_role_ids": ordered_ids,
                    "plan_summary": _safe_str(data.get("plan_summary"), "按相关性安排全部激活角色依次执行"),
                    "runtime": runtime,
                }
        return {
            "delegate_role_ids": all_ids,
            "plan_summary": _safe_str(data.get("plan_summary"), "全部激活角色依次回复"),
            "runtime": runtime,
        }
    except Exception as e:
        return {
            "delegate_role_ids": all_ids,
            "plan_summary": "全部激活角色依次回复",
            "runtime": {
                "requested_provider": rt_request["provider_name"],
                "requested_model": rt_request["model_name"],
                "applied_provider": "",
                "applied_model": "",
                "fallback_reason": f"supervisor_plan_failed:{type(e).__name__}",
                "temperature": rt_request["temperature"],
                "max_tokens": rt_request["max_tokens"],
            },
        }


def _call_supervisor_final(
    *,
    question: str,
    role_replies: List[Dict[str, Any]],
    model_name: str,
    room_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not role_replies:
        return {"content": "", "runtime": {}}
    if len(role_replies) == 1:
        first = role_replies if isinstance(role_replies, list) and role_replies else {}
        return {
            "content": _safe_str(_safe_dict(first).get("content")),
            "runtime": {
                "requested_provider": "",
                "requested_model": "",
                "applied_provider": "",
                "applied_model": "",
                "fallback_reason": "single_reply_passthrough",
                "temperature": None,
                "max_tokens": None,
            },
        }
    lines = [f"【{_safe_str(r.get('role_name'), '角色')}】\n{_safe_str(r.get('content'))}" for r in role_replies if isinstance(r, dict) and _safe_str(r.get("content"))]
    if not lines:
        return {"content": "", "runtime": {}}
    prompt = f"用户问题：{question}\n\n各角色回复：\n\n" + "\n\n".join(lines) + "\n\n请综合以上角色观点，给出统一、简洁、可执行的最终答复。直接回答，不要逐段复述原文。"
    current_state = room_state if isinstance(room_state, dict) else {}
    rt_request = _supervisor_runtime_request(current_state, model_name)
    try:
        text, runtime = _call_model_text_with_runtime(
            model_name=rt_request["model_name"],
            provider_name=rt_request["provider_name"],
            user_prompt=prompt,
            temperature=rt_request["temperature"],
            max_tokens=rt_request["max_tokens"],
        )
        return {"content": text, "runtime": runtime}
    except Exception as e:
        return {
            "content": "",
            "runtime": {
                "requested_provider": rt_request["provider_name"],
                "requested_model": rt_request["model_name"],
                "applied_provider": "",
                "applied_model": "",
                "fallback_reason": f"supervisor_final_failed:{type(e).__name__}",
                "temperature": rt_request["temperature"],
                "max_tokens": rt_request["max_tokens"],
            },
        }


def _merge_role_binding(out: Dict[str, Any], request_args: Dict[str, Any], role: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(out)
    binding = _safe_dict(request_args.get("role_binding"))
    if not binding:
        binding = _safe_dict(role.get("binding") or role.get("bindings") or role.get("knowledge_binding"))
    if not binding:
        return merged
    mapping = {
        "library_id": ["library_id", "libraryid"],
        "doc_id": ["doc_id", "docid"],
        "group_id": ["group_id", "groupid"],
        "qa_store_scope": ["qa_store_scope", "qastorescope", "store_scope", "storescope"],
        "qa_evidence_scope": ["qa_evidence_scope", "qaevidencescope", "evidence_scope", "evidencescope"],
        "qa_top_k": ["qa_top_k", "qatopk"],
        "qa_max_evidence": ["qa_max_evidence", "qamaxevidence"],
        "qa_min_citations": ["qa_min_citations", "qamincitations"],
        "qa_max_citations": ["qa_max_citations", "qamaxcitations"],
        "qa_max_output_tokens": ["qa_max_output_tokens", "qamaxoutputtokens"],
        "qa_answer_lang": ["qa_answer_lang", "qaanswerlang"],
        "rag_mode": ["rag_mode"],
    }
    for dst_key, src_keys in mapping.items():
        if merged.get(dst_key) not in (None, ""):
            continue
        for src_key in src_keys:
            if binding.get(src_key) not in (None, ""):
                merged[dst_key] = binding.get(src_key)
                break
    return merged


def _build_orchestrate_args(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    state = _load_room_state(room_id)
    mcp_overrides = _safe_dict(request_args.get("mcp_overrides"))
    if not mcp_overrides:
        mcp_overrides = _safe_dict(state.get("mcp_overrides"))

    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)
    role_prompt = _safe_str(role.get("system_prompt"))
    user_question = _extract_user_question(question, request_args)

    rag_mode = _normalize_room_mode(
        request_args.get("requested_mode")
        or request_args.get("rag_mode")
        or request_args.get("mode_used")
        or _safe_dict(request_args.get("role_binding")).get("rag_mode")
        or mcp_overrides.get("rag_mode")
        or "off"
    )

    is_supervisor = role_id == "supervisor" or role_name.lower() == "supervisor"

    if is_supervisor:
        content = _safe_str(question)
    elif rag_mode in {"cite", "ground"}:
        parts: List[str] = []
        if user_question:
            parts.append(user_question)
        if role_name:
            parts.append(f"请从角色 {role_name} 的视角作答。")
        if role_prompt:
            parts.append(f"角色约束：{role_prompt}")
        content = "\n\n".join([x for x in parts if x]).strip() or _safe_str(question)
    else:
        content = _safe_str(question) or user_question

    room_actor_context = _safe_dict(request_args.get("room_actor_context"))
    room_supervisor_context = _safe_dict(request_args.get("room_supervisor_context"))
    p6_test_control = _safe_dict(request_args.get("p6_test_control"))

    probe_actor = _safe_str(
        p6_test_control.get("notebook_probe_actor")
        or request_args.get("notebook_probe_actor")
    ).lower()

    if not room_actor_context and probe_actor in {"supervisor", "worker", "skill"}:
        room_actor_context = {
            "actor_type": probe_actor,
            "actor_id": probe_actor,
        }

    out: Dict[str, Any] = {
        "content": content,
        "model": _safe_str(model_name, "gpt-4o-mini"),
        "rag_mode": rag_mode,
        "mcp_overrides": mcp_overrides,
        "request_id": _safe_str(request_args.get("request_id")),
        "conv_id": room_id,
    }

    passthrough_keys = [
        "token",
        "user_id",
        "_user_id",
        "actor_user_id",
        "room_owner_user_id",
        "role_owner_user_id",
        "actor_is_room_owner",
        "is_owner_actor",
        "shared_role_ids_snapshot",
        "shared_supervisor_enabled_snapshot",
        "role_shared_to_room",
        "supervisor_shared_to_room",
        "effective_execution_scope",
        "runtime_scope_stripped",
        "stripped_fields",
        "base_path",
        "basepath",
        "_base_path",
        "concept_language",
        "conceptlanguage",
        "concept_backend",
        "conceptbackend",
        "qa_store_scope",
        "qastorescope",
        "qa_evidence_scope",
        "qaevidencescope",
        "qa_top_k",
        "qatopk",
        "qa_max_evidence",
        "qamaxevidence",
        "qa_min_citations",
        "qamincitations",
        "qa_max_citations",
        "qamaxcitations",
        "qa_max_output_tokens",
        "qamaxoutputtokens",
        "qa_answer_lang",
        "qaanswerlang",
        "library_id",
        "libraryid",
        "doc_id",
        "docid",
        "group_id",
        "groupid",
        "capability_gate",
        "capabilitygate",
        "workspace_id",
        "workspace_name",
        "focus_root",
        "focus_label",
        "inherit_workspace_context",
        "inherit_focus_root",
        "requested_mode",
        "role_tools",
        "role_tool_policy",
        "tool_policy",
        "room_actor_context",
        "room_supervisor_context",
        "notebook_probe_actor",
    ]
    for key in passthrough_keys:
        if request_args.get(key) not in (None, ""):
            out[key] = request_args.get(key)

    if isinstance(request_args.get("attachments"), list):
        out["attachments"] = request_args.get("attachments")
    if isinstance(request_args.get("rss"), dict):
        out["rss"] = request_args.get("rss")
    if isinstance(request_args.get("workspace_context"), dict):
        out["workspace_context"] = request_args.get("workspace_context")
    if p6_test_control:
        out["p6_test_control"] = p6_test_control
    if room_actor_context:
        out["room_actor_context"] = room_actor_context
    if room_supervisor_context:
        out["room_supervisor_context"] = room_supervisor_context

    out = _merge_role_binding(out, request_args, role)
    out["rag_mode"] = _normalize_room_mode(out.get("rag_mode"), rag_mode)
    return out


def _load_worker_execution_module():
    return import_module(".room_worker_execution", __package__)


def _call_role_reply_with_runtime(room_id: str, question: str, role: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    mod = _load_worker_execution_module()
    return mod._call_role_reply_with_runtime(room_id=room_id, question=question, role=role, model_name=model_name)


def _call_role_reply(room_id: str, question: str, role: Dict[str, Any], model_name: str) -> str:
    mod = _load_worker_execution_module()
    return mod._call_role_reply(room_id=room_id, question=question, role=role, model_name=model_name)


def _call_room_ai_reply(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Optional[Dict[str, Any]] = None,
    role: Optional[Dict[str, Any]] = None,
) -> str:
    mod = _load_worker_execution_module()
    return mod._execute_room_worker_text(
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=request_args,
        role=role,
    )


def _call_room_ai_reply_packet(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Optional[Dict[str, Any]] = None,
    role: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    mod = _load_worker_execution_module()
    return mod._execute_room_worker_packet(
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=request_args,
        role=role,
    )


def _call_room_ai_reply_with_meta(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Optional[Dict[str, Any]] = None,
    role: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _call_room_ai_reply_packet(
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=request_args,
        role=role,
    )


def _call_room_reply_packet(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Optional[Dict[str, Any]] = None,
    role: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _call_room_ai_reply_packet(
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=request_args,
        role=role,
    )


def _call_room_reply_with_meta(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Optional[Dict[str, Any]] = None,
    role: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _call_room_ai_reply_packet(
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=request_args,
        role=role,
    )


def _call_role_reply_packet(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Optional[Dict[str, Any]] = None,
    role: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _call_room_ai_reply_packet(
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=request_args,
        role=role,
    )


def _call_role_reply_with_meta(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Optional[Dict[str, Any]] = None,
    role: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _call_room_ai_reply_packet(
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=request_args,
        role=role,
    )


__all__ = [
    "MissingAnthropicDependencyError",
    "MissingLLMDependencyError",
    "_bridge_chat_result",
    "_build_orchestrate_args",
    "_call_llm_json",
    "_call_role_reply",
    "_call_role_reply_packet",
    "_call_role_reply_with_meta",
    "_call_role_reply_with_runtime",
    "_call_room_ai_reply",
    "_call_room_ai_reply_packet",
    "_call_room_ai_reply_with_meta",
    "_call_room_plain_reply",
    "_call_room_reply_packet",
    "_call_room_reply_with_meta",
    "_call_supervisor_final",
    "_call_supervisor_plan",
    "_coerce_dict_list",
    "_coerce_str_list",
    "_empty_evidence_result",
    "_ensure_formal_packet",
    "_extract_user_question",
    "_get_int",
    "_get_str",
    "_merge_delegate_ids_with_all_active",
    "_merge_role_binding",
    "_normalize_qascope_packet",
    "_normalize_room_mode",
    "_safe_dict",
    "_safe_list",
    "_safe_str",
    "_supervisor_runtime_request",
]
