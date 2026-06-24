from __future__ import annotations

import os
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Iterable, List, Optional


_DEFAULT_WORKER_CONCURRENCY = 2
_DEFAULT_WORKER_STAGGER_MS = 120
_HARD_WORKER_CONCURRENCY_CAP = 4
_MAX_STAGGER_MS = 1000

_WORKER_CONCURRENCY_KEYS = ("max_worker_concurrency", "worker_concurrency")
_WORKER_STAGGER_KEYS = (
    "worker_concurrency_stagger_ms",
    "max_worker_concurrency_stagger_ms",
    "worker_stagger_ms",
    "max_worker_stagger_ms",
)


def _coerce_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(float(text))
        except Exception:
            return None
    return None


def _dict_or_empty(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _room_worker_concurrency_cap() -> int:
    raw = os.environ.get("NISB_ROOM_MAX_WORKER_CONCURRENCY_CAP")
    parsed = _coerce_int(raw)
    if parsed is None:
        return _HARD_WORKER_CONCURRENCY_CAP
    return max(1, min(_HARD_WORKER_CONCURRENCY_CAP, parsed))


def _normalize_worker_concurrency(
    value: Any,
    *,
    default: int = _DEFAULT_WORKER_CONCURRENCY,
) -> int:
    cap = _room_worker_concurrency_cap()
    parsed = _coerce_int(value)
    if parsed is None:
        parsed = default
    return max(1, min(cap, parsed))


def _normalize_worker_stagger_ms(
    value: Any,
    *,
    default: int = _DEFAULT_WORKER_STAGGER_MS,
) -> int:
    parsed = _coerce_int(value)
    if parsed is None:
        parsed = default
    return max(0, min(_MAX_STAGGER_MS, parsed))


def _iter_worker_concurrency_containers(source: Any) -> Iterable[Dict[str, Any]]:
    root = _dict_or_empty(source)
    if not root:
        return

    yield root

    orchestration = _dict_or_empty(root.get("orchestration"))
    if orchestration:
        yield orchestration

    settings = _dict_or_empty(root.get("settings"))
    if settings:
        yield settings

        settings_orchestration = _dict_or_empty(settings.get("orchestration"))
        if settings_orchestration:
            yield settings_orchestration

    room_settings = _dict_or_empty(root.get("room_settings"))
    if room_settings:
        yield room_settings

        room_settings_orchestration = _dict_or_empty(room_settings.get("orchestration"))
        if room_settings_orchestration:
            yield room_settings_orchestration

    runtime_control = _dict_or_empty(root.get("runtime_control_snapshot"))
    if runtime_control:
        yield runtime_control

        runtime_orchestration = _dict_or_empty(runtime_control.get("orchestration"))
        if runtime_orchestration:
            yield runtime_orchestration

        runtime_settings = _dict_or_empty(runtime_control.get("settings"))
        if runtime_settings:
            yield runtime_settings

            runtime_settings_orchestration = _dict_or_empty(runtime_settings.get("orchestration"))
            if runtime_settings_orchestration:
                yield runtime_settings_orchestration

        runtime_room_settings = _dict_or_empty(runtime_control.get("room_settings"))
        if runtime_room_settings:
            yield runtime_room_settings

            runtime_room_settings_orchestration = _dict_or_empty(
                runtime_room_settings.get("orchestration")
            )
            if runtime_room_settings_orchestration:
                yield runtime_room_settings_orchestration


def _get_worker_concurrency(*sources: Any, total: int = 0) -> int:
    for source in sources:
        for container in _iter_worker_concurrency_containers(source):
            for key in _WORKER_CONCURRENCY_KEYS:
                if key in container:
                    value = _normalize_worker_concurrency(container.get(key))
                    return max(1, min(max(total, 1), value)) if total else value

    value = _normalize_worker_concurrency(None)
    return max(1, min(max(total, 1), value)) if total else value


def _get_worker_stagger_ms(*sources: Any) -> int:
    for source in sources:
        for container in _iter_worker_concurrency_containers(source):
            for key in _WORKER_STAGGER_KEYS:
                if key in container:
                    return _normalize_worker_stagger_ms(container.get(key))

    env_value = os.environ.get("NISB_ROOM_WORKER_CONCURRENCY_STAGGER_MS")
    return _normalize_worker_stagger_ms(env_value)


def _get_worker_stagger_seconds(*sources: Any) -> float:
    return _get_worker_stagger_ms(*sources) / 1000.0


def _sleep_for_worker_stagger(
    *,
    item_index: int,
    max_workers: int,
    stagger_seconds: float,
) -> None:
    if stagger_seconds <= 0 or max_workers <= 1:
        return

    offset = (max(int(item_index or 1), 1) - 1) % max_workers
    if offset <= 0:
        return

    time.sleep(offset * stagger_seconds)


def _run_bounded_worker_pool(
    *,
    items: List[Dict[str, Any]],
    worker_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    error_result_fn: Callable[[Dict[str, Any], Exception], Dict[str, Any]],
    index_key: str = "idx",
    max_workers: int = 1,
    stagger_seconds: float = 0.0,
    on_result_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> List[Dict[str, Any]]:
    if not items:
        return []

    effective_workers = max(1, min(int(max_workers or 1), len(items)))
    results_by_index: Dict[int, Dict[str, Any]] = {}

    def _call_worker(item: Dict[str, Any]) -> Dict[str, Any]:
        item_index = _coerce_int(item.get(index_key)) or 0
        _sleep_for_worker_stagger(
            item_index=item_index,
            max_workers=effective_workers,
            stagger_seconds=stagger_seconds,
        )
        return worker_fn(item)

    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        future_map = {executor.submit(_call_worker, item): item for item in items}

        for future in as_completed(future_map):
            item = future_map[future]
            item_index = _coerce_int(item.get(index_key)) or 0
            try:
                result = future.result()
            except CancelledError:
                raise
            except Exception as ex:
                result = error_result_fn(item, ex)

            results_by_index[item_index] = result
            if on_result_fn is not None:
                on_result_fn(result)

    return [results_by_index[idx] for idx in sorted(results_by_index.keys())]


__all__ = [
    "_get_worker_concurrency",
    "_get_worker_stagger_ms",
    "_get_worker_stagger_seconds",
    "_normalize_worker_concurrency",
    "_normalize_worker_stagger_ms",
    "_run_bounded_worker_pool",
]

