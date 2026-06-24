import json
import os
import time
from typing import Any, Dict, List, Tuple


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    tmp = f"{path}.tmp.{os.getpid()}.{int(time.time() * 1000)}"
    ensure_dir(os.path.dirname(path))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_prefs(prefs: Dict[str, Any]) -> Dict[str, Any]:
    def clamp_num(v: Any, mn: float, mx: float, default: float) -> float:
        try:
            n = float(v)
        except Exception:
            return default
        if n < mn:
            return mn
        if n > mx:
            return mx
        return n

    return {
        "brightness": int(round(clamp_num(prefs.get("brightness"), 70, 110, 100))),
        "fontSize": int(round(clamp_num(prefs.get("fontSize"), 13, 22, 16))),
        "lineHeight": float(clamp_num(prefs.get("lineHeight"), 1.2, 2.2, 1.6)),
        "padding": int(round(clamp_num(prefs.get("padding"), 0, 36, 0))),
        "warmth": int(round(clamp_num(prefs.get("warmth"), 0, 100, 0))),
        "smooth": int(round(clamp_num(prefs.get("smooth"), 0, 100, 0))),
    }


def _pick_str(d: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _infer_user_id(arguments: Dict[str, Any], user_id: str = None, userid: str = None) -> str:
    return _pick_str(
        {
            "user_id": user_id,
            "userid": userid,
            **(arguments or {}),
        },
        ["user_id", "_user_id", "userid", "uid"],
    )


def _resolve_basepath(arguments: Dict[str, Any], basepath: str = None, user_id: str = None, userid: str = None) -> str:
    # 1) 优先用注入的 basepath（你环境里一般会注入）
    bp = basepath or (arguments or {}).get("basepath") or (arguments or {}).get("base_path") or (arguments or {}).get("_base_path")
    if bp:
        return str(bp)

    # 2) 兼容：你的真实数据根目录是 /opt/nisb-data/users/{uid}
    uid = _infer_user_id(arguments, user_id=user_id, userid=userid)
    if uid:
        cand = os.path.join("/opt/nisb-data/users", uid)
        if os.path.exists(cand):
            return cand

    # 3) 再退回 /data/users/{uid}（兼容旧环境）
    if uid:
        return os.path.join("/data/users", uid)

    return ""


def default_preset_path(basepath: str) -> str:
    return os.path.join(basepath, "storage", "config", "reading_optimizer", "default.json")


def custom_presets_path(basepath: str) -> str:
    return os.path.join(basepath, "storage", "config", "reading_optimizer", "custom_presets.json")


def _load_custom_presets(basepath: str) -> List[Dict[str, Any]]:
    path = custom_presets_path(basepath)
    if not os.path.exists(path):
        return []
    data = read_json(path)
    arr = data.get("presets") if isinstance(data, dict) else None
    if not isinstance(arr, list):
        return []
    out: List[Dict[str, Any]] = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        pid = str(x.get("id") or "").strip()
        name = str(x.get("name") or "").strip()
        prefs = x.get("prefs") if isinstance(x.get("prefs"), dict) else {}
        if not pid or not name:
            continue
        out.append(
            {
                "id": pid,
                "name": name[:18],
                "prefs": normalize_prefs(prefs),
                "created_at": int(x.get("created_at") or 0),
                "updated_at": int(x.get("updated_at") or 0),
            }
        )
    out.sort(key=lambda t: int(t.get("created_at") or 0), reverse=True)
    return out


def _save_custom_presets(basepath: str, presets: List[Dict[str, Any]]) -> None:
    path = custom_presets_path(basepath)
    payload = {
        "updated_at": int(time.time()),
        "presets": presets,
    }
    atomic_write_json(path, payload)


def nisb_readopt_get_default_preset(arguments: Dict[str, Any], user_id: str = None, basepath: str = None, userid: str = None, **kwargs):
    try:
        bp = _resolve_basepath(arguments, basepath=basepath, user_id=user_id, userid=userid)
        if not bp:
            return {"hasdefault": False, "preset": None, "error": "missing basepath"}

        path = default_preset_path(bp)
        if not os.path.exists(path):
            return {"hasdefault": False, "preset": None}

        data = read_json(path)
        preset = data.get("preset") if isinstance(data, dict) else None
        if not isinstance(preset, dict):
            return {"hasdefault": False, "preset": None}

        name = str(preset.get("name") or "").strip()
        presetid = str(preset.get("presetid") or "").strip()
        prefs = preset.get("prefs") if isinstance(preset.get("prefs"), dict) else {}
        if not name or not presetid:
            return {"hasdefault": False, "preset": None}

        return {
            "hasdefault": True,
            "preset": {
                "presetid": presetid,
                "name": name,
                "prefs": normalize_prefs(prefs),
                "updated_at": int(data.get("updated_at") or 0),
            },
        }
    except Exception as e:
        return {"hasdefault": False, "preset": None, "error": f"{type(e).__name__}: {e}"}


def nisb_readopt_set_default_preset(arguments: Dict[str, Any], user_id: str = None, basepath: str = None, userid: str = None, **kwargs):
    try:
        bp = _resolve_basepath(arguments, basepath=basepath, user_id=user_id, userid=userid)
        uid = _infer_user_id(arguments, user_id=user_id, userid=userid)
        if not bp:
            return {"ok": False, "error": "missing basepath"}

        presetid = _pick_str(arguments, ["presetid", "preset_id", "presetId", "id"])
        name = _pick_str(arguments, ["name", "preset_name", "presetName", "title"])
        prefs = arguments.get("prefs")
        if not isinstance(prefs, dict):
            return {"ok": False, "error": "prefs must be object"}

        if not presetid:
            return {"ok": False, "error": "presetid is required"}
        if not name:
            return {"ok": False, "error": "name is required"}

        now = int(time.time())
        payload = {
            "user_id": uid,
            "updated_at": now,
            "preset": {
                "presetid": presetid,
                "name": name[:32],
                "prefs": normalize_prefs(prefs),
            },
        }

        path = default_preset_path(bp)
        atomic_write_json(path, payload)

        return {"ok": True, "hasdefault": True, "preset": payload["preset"], "updated_at": now, "path": path}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def nisb_readopt_clear_default_preset(arguments: Dict[str, Any], user_id: str = None, basepath: str = None, userid: str = None, **kwargs):
    try:
        bp = _resolve_basepath(arguments, basepath=basepath, user_id=user_id, userid=userid)
        if not bp:
            return {"ok": False, "error": "missing basepath"}

        path = default_preset_path(bp)
        if os.path.exists(path):
            os.remove(path)
        return {"ok": True, "cleared": True, "path": path}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def nisb_readopt_get_custom_presets(arguments: Dict[str, Any], user_id: str = None, basepath: str = None, userid: str = None, **kwargs):
    try:
        bp = _resolve_basepath(arguments, basepath=basepath, user_id=user_id, userid=userid)
        if not bp:
            return {"ok": False, "presets": [], "error": "missing basepath"}

        presets = _load_custom_presets(bp)
        return {"ok": True, "presets": presets, "path": custom_presets_path(bp)}
    except Exception as e:
        return {"ok": False, "presets": [], "error": f"{type(e).__name__}: {e}"}


def nisb_readopt_save_custom_preset(arguments: Dict[str, Any], user_id: str = None, basepath: str = None, userid: str = None, **kwargs):
    try:
        bp = _resolve_basepath(arguments, basepath=basepath, user_id=user_id, userid=userid)
        if not bp:
            return {"ok": False, "error": "missing basepath"}

        pid = _pick_str(arguments, ["presetid", "preset_id", "presetId", "id"])
        name = _pick_str(arguments, ["name", "preset_name", "presetName", "title"])
        prefs = arguments.get("prefs")
        if not isinstance(prefs, dict):
            return {"ok": False, "error": "prefs must be object"}
        if not name:
            return {"ok": False, "error": "name is required"}

        now = int(time.time())
        if not pid:
            pid = f"cp_{int(time.time() * 1000)}"

        prefsnorm = normalize_prefs(prefs)

        presets = _load_custom_presets(bp)
        next_presets: List[Dict[str, Any]] = []
        found = False

        for p in presets:
            if str(p.get("id")) == pid:
                next_presets.append(
                    {
                        "id": pid,
                        "name": name[:18],
                        "prefs": prefsnorm,
                        "created_at": int(p.get("created_at") or now),
                        "updated_at": now,
                    }
                )
                found = True
            else:
                next_presets.append(p)

        if not found:
            next_presets.append(
                {
                    "id": pid,
                    "name": name[:18],
                    "prefs": prefsnorm,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        next_presets.sort(key=lambda t: int(t.get("created_at") or 0), reverse=True)
        next_presets = next_presets[:6]

        _save_custom_presets(bp, next_presets)

        return {
            "ok": True,
            "saved": True,
            "preset": {"id": pid, "name": name[:18], "prefs": prefsnorm},
            "path": custom_presets_path(bp),
            "count": len(next_presets),
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def nisb_readopt_delete_custom_preset(arguments: Dict[str, Any], user_id: str = None, basepath: str = None, userid: str = None, **kwargs):
    try:
        bp = _resolve_basepath(arguments, basepath=basepath, user_id=user_id, userid=userid)
        if not bp:
            return {"ok": False, "error": "missing basepath"}

        pid = _pick_str(arguments, ["presetid", "preset_id", "presetId", "id"])
        if not pid:
            return {"ok": False, "error": "presetid is required"}

        presets = _load_custom_presets(bp)
        next_presets = [p for p in presets if str(p.get("id")) != pid]
        _save_custom_presets(bp, next_presets)

        return {"ok": True, "deleted": True, "path": custom_presets_path(bp), "count": len(next_presets)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

