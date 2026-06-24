import os
import re
import time
import json
import shutil
import tempfile
import subprocess
from urllib.parse import quote

from tools.i18n.backend_i18n import i18n_text, normalize_backend_locale


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


def _atomic_write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _append_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)


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
        if (not path) or (not os.path.exists(path)):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            x = json.load(f)
        return x if isinstance(x, dict) else {}
    except Exception:
        return {}


def _to_nisb_path_only(rel_path: str) -> str:
    rel_path = str(rel_path or "").replace("\\", "/").lstrip("/")
    return f"nisb://file?path={quote(rel_path, safe='')}"


def _rewrite_md_images(md_text: str, images_rel_dir: str) -> str:
    """
    Rewrite Markdown and HTML image references to nisb://file?path=... URLs.
    """
    if not md_text:
        return ""
    images_rel_dir = str(images_rel_dir or "").strip().replace("\\", "/").strip("/")

    img_md_pat = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

    def md_repl(m):
        alt = m.group(1) or ""
        target = (m.group(2) or "").strip()
        low = target.lower()

        if low.startswith("nisb://") or low.startswith("data:") or low.startswith("http://") or low.startswith("https://") or low.startswith("file:"):
            return m.group(0)

        t0 = target.split("?", 1)[0].split("#", 1)[0]
        base = os.path.basename(t0.replace("\\", "/"))
        if not re.search(r"\.(png|jpg|jpeg|webp|gif|bmp|svg)$", base, re.IGNORECASE):
            return m.group(0)

        rel_img = f"{images_rel_dir}/{base}" if images_rel_dir else base
        return f"![{alt}]({_to_nisb_path_only(rel_img)})"

    out = img_md_pat.sub(md_repl, md_text)

    img_tag_pat = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
    src_pat = re.compile(r"\bsrc\s*=\s*(\"([^\"]*)\"|'([^']*)'|([^\s>]+))", re.IGNORECASE)

    def html_tag_repl(m):
        tag = m.group(0) or ""
        m2 = src_pat.search(tag)
        if not m2:
            return tag

        src_val = m2.group(2) or m2.group(3) or m2.group(4) or ""
        src_val = src_val.strip()
        low = src_val.lower()

        if low.startswith("nisb://") or low.startswith("data:") or low.startswith("http://") or low.startswith("https://") or low.startswith("file:"):
            return tag

        t0 = src_val.split("?", 1)[0].split("#", 1)[0]
        base = os.path.basename(t0.replace("\\", "/"))
        if not re.search(r"\.(png|jpg|jpeg|webp|gif|bmp|svg)$", base, re.IGNORECASE):
            return tag

        rel_img = f"{images_rel_dir}/{base}" if images_rel_dir else base
        new_src = _to_nisb_path_only(rel_img)

        old_full = m2.group(1)
        if old_full.startswith('"') or old_full.startswith("'"):
            q = old_full[0]
            new_full = q + new_src + q
        else:
            new_full = new_src

        return tag[:m2.start(1)] + new_full + tag[m2.end(1):]

    out = img_tag_pat.sub(html_tag_repl, out)
    return out


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


def _rm_tree_safe(path: str) -> None:
    if not path:
        return
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def _user_global_lock_path(uid: str) -> str:
    return f"/data/users/{uid}/.locks/nisb_office_convert.lock"


def _run_pptx2md_cli(
    abs_pptx: str,
    cwd_dir: str,
    output_md_filename: str,
    image_dirname: str,
    disable_notes: bool,
    timeout_seconds: int,
):
    cmd = ["pptx2md", os.path.abspath(abs_pptx), "-o", output_md_filename, "-i", image_dirname]

    if disable_notes:
        cmd_try = cmd + ["--disable-notes"]
        p = subprocess.run(cmd_try, cwd=cwd_dir, capture_output=True, text=True, timeout=timeout_seconds)
        if p.returncode == 0:
            return {"ok": True, "cmd": cmd_try, "stdout": p.stdout, "stderr": p.stderr, "disable_notes_applied": True}

        err = (p.stderr or "") + "\n" + (p.stdout or "")
        low = err.lower()
        if ("unrecognized" in low) or ("no such option" in low) or ("unknown option" in low) or ("invalid option" in low):
            p2 = subprocess.run(cmd, cwd=cwd_dir, capture_output=True, text=True, timeout=timeout_seconds)
            if p2.returncode == 0:
                return {
                    "ok": True,
                    "cmd": cmd,
                    "stdout": p2.stdout,
                    "stderr": p2.stderr,
                    "disable_notes_applied": False,
                    "warning": "disable_notes not supported by pptx2md CLI; fallback without flag.",
                }
            return {"ok": False, "cmd": cmd, "stdout": p2.stdout, "stderr": p2.stderr, "disable_notes_applied": False}

        return {"ok": False, "cmd": cmd_try, "stdout": p.stdout, "stderr": p.stderr, "disable_notes_applied": False}

    p0 = subprocess.run(cmd, cwd=cwd_dir, capture_output=True, text=True, timeout=timeout_seconds)
    return {"ok": (p0.returncode == 0), "cmd": cmd, "stdout": p0.stdout, "stderr": p0.stderr, "disable_notes_applied": False}


_PPTX_NOTE_LABELS = {
    "source_pptx": {"en": "Source PPTX", "zh-CN": "来源 PPTX"},
    "images": {"en": "Images", "zh-CN": "图片"},
    "notes": {"en": "Notes", "zh-CN": "备注"},
}


def _pptx_note_label(locale: str, key: str) -> str:
    return i18n_text(locale, _PPTX_NOTE_LABELS.get(key), key)


def nisb_pptx_convert_to_note(
    pptx_path,
    uid: str = "",
    workspace_id: str = "",
    output_md_path: str = "",
    image_dirname: str = "images",
    overwrite: bool = False,
    disable_notes: bool = False,
    timeout_seconds: int = 1800,
    skip_global_lock: bool = False,
    locale: str = "en",
):
    """
    Convert a PPTX into Markdown plus extracted images.
    """
    user_lock_path = ""
    target_lock_path = ""

    try:
        if isinstance(pptx_path, dict):
            args = pptx_path
            pptx_path = args.get("pptx_path", "")
            uid = args.get("uid", uid) or uid
            workspace_id = args.get("workspace_id", workspace_id) or workspace_id
            output_md_path = args.get("output_md_path", output_md_path) or output_md_path
            image_dirname = args.get("image_dirname", image_dirname) or image_dirname
            overwrite = bool(args.get("overwrite", overwrite))
            disable_notes = bool(args.get("disable_notes", disable_notes))
            skip_global_lock = bool(args.get("skip_global_lock", skip_global_lock))
            locale = args.get("locale", args.get("ui_locale", args.get("language", locale))) or locale
            try:
                timeout_seconds = int(args.get("timeout_seconds", timeout_seconds))
            except Exception:
                pass

        uid = _safe_uid(uid)
        workspace_id = _safe_workspace_id(workspace_id)
        locale = normalize_backend_locale(locale)

        pptx_rel = _strip_invisible(_safe_rel_path(pptx_path))
        if "?" in pptx_rel:
            pptx_rel = pptx_rel.split("?", 1)[0]
        if "#" in pptx_rel:
            pptx_rel = pptx_rel.split("#", 1)[0]
        pptx_rel = _strip_invisible(pptx_rel)

        ext0 = os.path.splitext(pptx_rel)[1].lower()
        if ext0 != ".pptx":
            return {"success": False, "message": "pptx_path must end with .pptx", "debug_pptx_path_repr": repr(pptx_rel), "debug_ext": ext0}

        abs_pptx = _resolve_under_user(uid, pptx_rel)
        if not os.path.exists(abs_pptx):
            return {"success": False, "message": f"PPTX not found: {pptx_rel}"}

        try:
            st = os.stat(abs_pptx)
            src_size = int(st.st_size)
            src_mtime = int(st.st_mtime)
        except Exception:
            src_size = 0
            src_mtime = 0

        pptx_dir_rel = os.path.dirname(pptx_rel).replace("\\", "/").strip("/")
        pptx_stem = os.path.basename(pptx_rel).rsplit(".", 1)[0]

        if output_md_path:
            md_rel = _strip_invisible(_safe_rel_path(output_md_path))
            if os.path.splitext(md_rel)[1].lower() != ".md":
                return {"success": False, "message": "output_md_path must end with .md"}
        else:
            md_rel = f"{pptx_dir_rel}/{pptx_stem}_pptx.md" if pptx_dir_rel else f"{pptx_stem}_pptx.md"

        abs_md = _resolve_under_user(uid, md_rel)

        md_dir_rel = os.path.dirname(md_rel).replace("\\", "/").strip("/")
        md_stem = os.path.splitext(os.path.basename(md_rel))[0]
        images_dirname2 = str(image_dirname or "images").strip().replace("\\", "/").strip("/")
        images_rel = f"{md_dir_rel}/{md_stem}_{images_dirname2}" if md_dir_rel else f"{md_stem}_{images_dirname2}"
        abs_images_dir = _resolve_under_user(uid, images_rel)

        manifest_abs = abs_md + ".office_convert_manifest.json"

        def _manifest_matches(m: dict) -> bool:
            try:
                if not isinstance(m, dict):
                    return False
                if str(m.get("source_path") or "") != pptx_rel:
                    return False
                ms = m.get("source_size", None)
                mm = m.get("source_mtime", None)
                if ms is not None and int(ms or 0) != int(src_size or 0):
                    return False
                if mm is not None and int(mm or 0) != int(src_mtime or 0):
                    return False
                if str(m.get("tool") or "") != "nisb_pptx_convert_to_note":
                    return False
                if str(m.get("md_path") or "") != md_rel:
                    return False
                return True
            except Exception:
                return False

        if os.path.exists(abs_md) and not overwrite:
            m0 = _safe_read_json(manifest_abs)
            if _manifest_matches(m0):
                return {
                    "success": True,
                    "message": "Target markdown already exists (same pptx).",
                    "already_exists": True,
                    "uid": uid,
                    "pptx_path": pptx_rel,
                    "md_path": md_rel,
                    "images_dir": images_rel,
                    "mode": "single",
                }
            return {"success": False, "message": f"Target markdown exists (overwrite=false): {md_rel}", "md_path": md_rel}

        if overwrite and os.path.exists(abs_md):
            m0 = _safe_read_json(manifest_abs)
            if not _manifest_matches(m0):
                return {"success": False, "message": "Refuse to overwrite: manifest missing or not match pptx_path.", "md_path": md_rel}

        lock_payload = json.dumps(
            {"pid": os.getpid(), "uid": uid, "source_path": pptx_rel, "started_at": int(time.time()), "tool": "nisb_pptx_convert_to_note"},
            ensure_ascii=False,
        )

        if not bool(skip_global_lock):
            user_lock_path = _user_global_lock_path(uid)
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

        target_lock_path = abs_md + ".office_convert.lock"
        try:
            _acquire_lock(target_lock_path, lock_payload)
        except FileExistsError:
            return {"success": False, "message": "Conversion is already running for this target (lock exists).", "uid": uid, "pptx_path": pptx_rel, "target_lock_path": target_lock_path}

        if overwrite:
            try:
                if os.path.exists(abs_md):
                    os.remove(abs_md)
            except Exception:
                pass
            _rm_tree_safe(abs_images_dir)

        os.makedirs(abs_images_dir, exist_ok=True)

        md_dir_abs = os.path.dirname(abs_md) or _user_root(uid)
        img_dirname_for_cli = os.path.basename(abs_images_dir)

        tmp_name = f".tmp_pptx2md_{int(time.time())}_{os.getpid()}.md"
        tmp_md_abs = os.path.join(md_dir_abs, tmp_name)

        run_res = _run_pptx2md_cli(
            abs_pptx=abs_pptx,
            cwd_dir=md_dir_abs,
            output_md_filename=tmp_name,
            image_dirname=img_dirname_for_cli,
            disable_notes=bool(disable_notes),
            timeout_seconds=int(timeout_seconds or 1800),
        )

        if (not run_res.get("ok")) or (not os.path.exists(tmp_md_abs)):
            stderr = (run_res.get("stderr") or "")[:4000]
            stdout = (run_res.get("stdout") or "")[:2000]
            return {
                "success": False,
                "message": "pptx2md conversion failed.",
                "uid": uid,
                "pptx_path": pptx_rel,
                "md_path": md_rel,
                "images_dir": images_rel,
                "cmd": run_res.get("cmd"),
                "stderr": stderr,
                "stdout": stdout,
            }

        try:
            with open(tmp_md_abs, "r", encoding="utf-8", errors="ignore") as f:
                md_body = f.read()
        finally:
            try:
                if os.path.exists(tmp_md_abs):
                    os.remove(tmp_md_abs)
            except Exception:
                pass

        header = []
        header.append(f"# {pptx_stem}")
        header.append("")
        header.append(f"> {_pptx_note_label(locale, 'source_pptx')}: {pptx_rel}")
        header.append(f"> {_pptx_note_label(locale, 'images')}: {images_rel}")
        if disable_notes:
            header.append(f"> {_pptx_note_label(locale, 'notes')}: requested_disabled")
        header.append("")
        header.append("---")
        header.append("")
        _atomic_write_text(abs_md, "\n".join(header))

        md_body2 = _rewrite_md_images(md_body or "", images_rel_dir=images_rel)
        _append_text(abs_md, md_body2 or "")

        _atomic_write_json(manifest_abs, {
            "tool": "nisb_pptx_convert_to_note",
            "uid": uid,
            "source_path": pptx_rel,
            "source_size": src_size,
            "source_mtime": src_mtime,
            "md_path": md_rel,
            "images_dir": images_rel,
            "disable_notes": bool(disable_notes),
            "disable_notes_applied": bool(run_res.get("disable_notes_applied")),
            "created_at": int(time.time()),
        })

        out = {
            "success": True,
            "message": "PPTX converted (single).",
            "uid": uid,
            "pptx_path": pptx_rel,
            "md_path": md_rel,
            "images_dir": images_rel,
            "mode": "single",
            "disable_notes": bool(disable_notes),
        }
        if run_res.get("warning"):
            out["warning"] = run_res.get("warning")
        return out

    except subprocess.TimeoutExpired:
        return {"success": False, "message": f"pptx2md timeout: exceeded timeout_seconds={timeout_seconds}"}
    except FileNotFoundError:
        return {"success": False, "message": "pptx2md command not found. Please ensure pptx2md is installed in requirements.txt."}
    except Exception as e:
        return {"success": False, "message": f"PPTX convert failed: {str(e)}"}
    finally:
        _release_lock(target_lock_path)
        _release_lock(user_lock_path)
