import os
import re
import time
import json
import tempfile
import subprocess
from typing import Any, Dict

from tools.i18n.backend_i18n import normalize_backend_locale


def _safe_rel_path(path: str) -> str:
    p = str(path or "").strip().replace("\\", "/")
    if not p:
        raise ValueError("path is required")
    if "\x00" in p:
        raise ValueError("Invalid path")
    if p.startswith("/"):
        raise ValueError("path must be relative to user root")
    if ".." in p.split("/"):
        raise ValueError("Invalid path (..)")
    return p.lstrip("/")


def _safe_uid(uid: str) -> str:
    u = str(uid or "").strip()
    if not u:
        u = os.environ.get("NISB_USER_ID", "") or "nisb_default_user"
    if not re.fullmatch(r"[a-zA-Z0-9_\-]+", u):
        raise ValueError("Invalid uid")
    return u


def _safe_workspace_id(workspace_id: str) -> str:
    w = str(workspace_id or "").strip()
    if not w:
        return ""
    if not w.startswith("workspace_"):
        raise ValueError("Invalid workspace_id")
    if not re.fullmatch(r"[a-zA-Z0-9_\-]+", w):
        raise ValueError("Invalid workspace_id")
    return w


def _user_root(uid: str) -> str:
    return f"/data/users/{uid}"


def _resolve_under_user(uid: str, rel_path: str) -> str:
    root = _user_root(uid)
    rel = _safe_rel_path(rel_path)
    abs_path = os.path.normpath(os.path.join(root, rel))
    root_norm = os.path.normpath(root) + os.sep
    abs_norm = os.path.normpath(abs_path)
    if not abs_norm.startswith(root_norm):
        raise ValueError("Resolved path escapes user root")
    return abs_path


def _strip_invisible(s: str) -> str:
    if s is None:
        return ""
    x = str(s)
    x = x.replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    return x.strip()


def _atomic_write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _safe_read_json(path: str) -> dict:
    try:
        if not path or not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            x = json.load(f)
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def _acquire_lock(lock_path: str, payload: str) -> None:
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    fd = None
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, payload.encode("utf-8"))
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass


def _release_lock(lock_path: str) -> None:
    try:
        if lock_path and os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception:
        pass


def _user_global_lock_path(uid: str) -> str:
    return f"/data/users/{uid}/.locks/nisb_office_convert.lock"


def _run_soffice_convert(abs_in: str, out_dir_abs: str, convert_to: str, timeout_seconds: int = 1800) -> Dict[str, Any]:
    cmd = [
        "soffice",
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--nolockcheck",
        "--nodefault",
        "--norestore",
        "--convert-to",
        convert_to,
        "--outdir",
        os.path.abspath(out_dir_abs),
        os.path.abspath(abs_in),
    ]

    with tempfile.TemporaryDirectory(prefix="nisb_soffice_home_") as home_dir:
        env = dict(os.environ)
        env["HOME"] = home_dir
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=int(timeout_seconds or 1800), env=env)
        return {
            "ok": p.returncode == 0,
            "cmd": cmd,
            "returncode": p.returncode,
            "stdout": (p.stdout or "")[:4000],
            "stderr": (p.stderr or "")[:4000],
        }


def nisb_ppt_convert_to_note(
    ppt_path,
    uid: str = "",
    workspace_id: str = "",
    output_md_path: str = "",
    image_dirname: str = "images",
    overwrite: bool = False,
    disable_notes: bool = False,
    keep_intermediate: bool = True,
    timeout_seconds: int = 1800,
    locale: str = "en",
):
    """
    Convert a .ppt file to .pptx with LibreOffice, then reuse the PPTX-to-note converter.
    """
    user_lock_path = ""
    target_lock_path = ""

    try:
        if isinstance(ppt_path, dict):
            args = ppt_path
            ppt_path = args.get("ppt_path", "")
            uid = args.get("uid", uid) or uid
            workspace_id = args.get("workspace_id", workspace_id) or workspace_id
            output_md_path = args.get("output_md_path", output_md_path) or output_md_path
            image_dirname = args.get("image_dirname", image_dirname) or image_dirname
            overwrite = bool(args.get("overwrite", overwrite))
            disable_notes = bool(args.get("disable_notes", disable_notes))
            keep_intermediate = bool(args.get("keep_intermediate", keep_intermediate))
            locale = args.get("locale", args.get("ui_locale", args.get("language", locale))) or locale
            try:
                timeout_seconds = int(args.get("timeout_seconds", timeout_seconds))
            except Exception:
                pass

        uid = _safe_uid(uid)
        workspace_id = _safe_workspace_id(workspace_id)
        locale = normalize_backend_locale(locale)

        ppt_rel = _strip_invisible(_safe_rel_path(ppt_path))
        if "?" in ppt_rel:
            ppt_rel = ppt_rel.split("?", 1)[0]
        if "#" in ppt_rel:
            ppt_rel = ppt_rel.split("#", 1)[0]
        ppt_rel = _strip_invisible(ppt_rel)

        ext = os.path.splitext(ppt_rel)[1].lower()
        if ext != ".ppt":
            return {
                "success": False,
                "message": "ppt_path must end with .ppt",
                "debug_ppt_path_repr": repr(ppt_rel),
                "debug_ext": ext,
            }

        abs_ppt = _resolve_under_user(uid, ppt_rel)
        if not os.path.exists(abs_ppt):
            return {"success": False, "message": f"PPT not found: {ppt_rel}"}

        try:
            st = os.stat(abs_ppt)
            src_size = int(st.st_size)
            src_mtime = int(st.st_mtime)
        except Exception:
            src_size = 0
            src_mtime = 0

        in_dir_rel = os.path.dirname(ppt_rel).replace("\\", "/").strip("/")
        stem = os.path.basename(ppt_rel).rsplit(".", 1)[0]
        pptx_rel = f"{in_dir_rel}/{stem}.pptx" if in_dir_rel else f"{stem}.pptx"
        abs_pptx = _resolve_under_user(uid, pptx_rel)

        user_lock_path = _user_global_lock_path(uid)
        lock_payload = json.dumps(
            {
                "pid": os.getpid(),
                "uid": uid,
                "source_path": ppt_rel,
                "started_at": int(time.time()),
                "tool": "nisb_ppt_convert_to_note",
            },
            ensure_ascii=False,
        )
        try:
            _acquire_lock(user_lock_path, lock_payload)
        except FileExistsError:
            existing = ""
            try:
                with open(user_lock_path, "r", encoding="utf-8") as f:
                    existing = f.read(4096)
            except Exception:
                existing = ""
            return {
                "success": False,
                "message": "Busy: another office conversion is running for this uid (max_concurrent=1).",
                "uid": uid,
                "lock_path": user_lock_path,
                "lock_content": existing,
            }

        target_lock_path = abs_pptx + ".office_ppt_to_pptx.lock"
        try:
            _acquire_lock(target_lock_path, lock_payload)
        except FileExistsError:
            return {
                "success": False,
                "message": "Conversion is already running for this target (lock exists).",
                "uid": uid,
                "ppt_path": ppt_rel,
                "target_lock_path": target_lock_path,
            }

        pptx_manifest_abs = abs_pptx + ".office_ppt_manifest.json"

        def _pptx_manifest_matches(m: dict) -> bool:
            try:
                if not isinstance(m, dict):
                    return False
                if str(m.get("tool") or "") != "nisb_ppt_convert_to_note":
                    return False
                if str(m.get("source_path") or "") != ppt_rel:
                    return False
                if int(m.get("source_size") or 0) != int(src_size or 0):
                    return False
                if int(m.get("source_mtime") or 0) != int(src_mtime or 0):
                    return False
                if str(m.get("pptx_path") or "") != pptx_rel:
                    return False
                return True
            except Exception:
                return False

        pptx_ready = False

        if os.path.exists(abs_pptx):
            m0 = _safe_read_json(pptx_manifest_abs)
            if _pptx_manifest_matches(m0):
                pptx_ready = True
            elif not overwrite:
                return {
                    "success": False,
                    "message": f"Target PPTX exists (overwrite=false): {pptx_rel}",
                    "pptx_path": pptx_rel,
                }
            else:
                return {
                    "success": False,
                    "message": "Refuse to overwrite: pptx manifest missing or not match ppt_path.",
                    "pptx_path": pptx_rel,
                }

        if not pptx_ready:
            out_dir_abs = os.path.dirname(abs_pptx) or _user_root(uid)
            run_res = _run_soffice_convert(
                abs_in=abs_ppt,
                out_dir_abs=out_dir_abs,
                convert_to="pptx",
                timeout_seconds=int(timeout_seconds or 1800),
            )

            if (not run_res.get("ok")) or (not os.path.exists(abs_pptx)):
                return {
                    "success": False,
                    "message": "PPT -> PPTX conversion failed (soffice).",
                    "uid": uid,
                    "ppt_path": ppt_rel,
                    "pptx_path": pptx_rel,
                    "cmd": run_res.get("cmd"),
                    "stdout": run_res.get("stdout"),
                    "stderr": run_res.get("stderr"),
                }

            _atomic_write_json(pptx_manifest_abs, {
                "tool": "nisb_ppt_convert_to_note",
                "uid": uid,
                "source_path": ppt_rel,
                "source_size": src_size,
                "source_mtime": src_mtime,
                "pptx_path": pptx_rel,
                "created_at": int(time.time()),
            })

        from tools.office.pptx_convert_to_note import nisb_pptx_convert_to_note

        res = nisb_pptx_convert_to_note({
            "pptx_path": pptx_rel,
            "uid": uid,
            "workspace_id": workspace_id,
            "output_md_path": output_md_path,
            "image_dirname": image_dirname,
            "overwrite": overwrite,
            "disable_notes": disable_notes,
            "skip_global_lock": True,
            "locale": locale,
        })

        if (not keep_intermediate) and res and res.get("success"):
            try:
                os.remove(abs_pptx)
            except Exception:
                pass
            try:
                if os.path.exists(pptx_manifest_abs):
                    os.remove(pptx_manifest_abs)
            except Exception:
                pass

        if isinstance(res, dict):
            res["source_ppt_path"] = ppt_rel
            res["intermediate_pptx_path"] = pptx_rel
            res["pipeline"] = "ppt->pptx->md"
        return res

    except FileNotFoundError:
        return {"success": False, "message": "soffice command not found. Please install LibreOffice in mcp-nisb Dockerfile."}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": f"soffice timeout: exceeded timeout_seconds={timeout_seconds}"}
    except Exception as e:
        return {"success": False, "message": f"PPT convert failed: {str(e)}"}
    finally:
        _release_lock(target_lock_path)
        _release_lock(user_lock_path)

