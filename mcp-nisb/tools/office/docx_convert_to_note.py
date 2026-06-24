import os
import re
import time
import json
import shutil
import tempfile
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
        if not path or not os.path.exists(path):
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
    if not md_text:
        return ""
    images_rel_dir = str(images_rel_dir or "").strip().replace("\\", "/").strip("/")

    img_pat = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

    def repl(m):
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

    return img_pat.sub(repl, md_text)


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


_OFFICE_DOCX_NOTE_LABELS = {
    "source_docx": {"en": "Source DOCX", "zh-CN": "来源 DOCX"},
    "images": {"en": "Images", "zh-CN": "图片"},
}


def _office_docx_note_label(locale: str, key: str) -> str:
    return i18n_text(locale, _OFFICE_DOCX_NOTE_LABELS.get(key), key)


def nisb_docx_convert_to_note(
    docx_path,
    uid: str = "",
    workspace_id: str = "",
    output_md_path: str = "",
    image_dirname: str = "images",
    overwrite: bool = False,
    skip_global_lock: bool = False,
    locale: str = "en",
):
    """
    Convert a DOCX into Markdown plus extracted images.

    Image references are rewritten to nisb://file?path=... URLs.

    Default output:
    - md: <stem>_docx.md
    - images: <stem>_docx_images/
    """
    user_lock_path = ""
    target_lock_path = ""

    try:
        # MCP dict args, snake_case only.
        if isinstance(docx_path, dict):
            args = docx_path
            docx_path = args.get("docx_path", "")
            uid = args.get("uid", uid) or uid
            workspace_id = args.get("workspace_id", workspace_id) or workspace_id
            output_md_path = args.get("output_md_path", output_md_path) or output_md_path
            image_dirname = args.get("image_dirname", image_dirname) or image_dirname
            overwrite = bool(args.get("overwrite", overwrite))
            skip_global_lock = bool(args.get("skip_global_lock", skip_global_lock))
            locale = args.get("locale", args.get("ui_locale", args.get("language", locale))) or locale

        try:
            import mammoth
        except Exception as e:
            return {"success": False, "message": "Missing dependency: mammoth.", "detail": str(e)}

        try:
            import html2text
        except Exception as e:
            return {"success": False, "message": "Missing dependency: html2text.", "detail": str(e)}

        uid = _safe_uid(uid)
        workspace_id = _safe_workspace_id(workspace_id)
        locale = normalize_backend_locale(locale)

        docx_rel = _strip_invisible(_safe_rel_path(docx_path))
        if "?" in docx_rel:
            docx_rel = docx_rel.split("?", 1)[0]
        if "#" in docx_rel:
            docx_rel = docx_rel.split("#", 1)[0]
        docx_rel = _strip_invisible(docx_rel)

        ext0 = os.path.splitext(docx_rel)[1].lower()
        if ext0 != ".docx":
            return {"success": False, "message": "docx_path must end with .docx", "debug_docx_path_repr": repr(docx_rel), "debug_ext": ext0}

        abs_docx = _resolve_under_user(uid, docx_rel)
        if not os.path.exists(abs_docx):
            return {"success": False, "message": f"DOCX not found: {docx_rel}"}

        try:
            st = os.stat(abs_docx)
            src_size = int(st.st_size)
            src_mtime = int(st.st_mtime)
        except Exception:
            src_size = 0
            src_mtime = 0

        docx_dir_rel = os.path.dirname(docx_rel).replace("\\", "/").strip("/")
        docx_stem = os.path.basename(docx_rel).rsplit(".", 1)[0]

        if output_md_path:
            md_rel = _strip_invisible(_safe_rel_path(output_md_path))
            if os.path.splitext(md_rel)[1].lower() != ".md":
                return {"success": False, "message": "output_md_path must end with .md"}
        else:
            md_rel = f"{docx_dir_rel}/{docx_stem}_docx.md" if docx_dir_rel else f"{docx_stem}_docx.md"

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
                if str(m.get("source_path") or "") != docx_rel:
                    return False
                ms = m.get("source_size", None)
                mm = m.get("source_mtime", None)
                if ms is not None and int(ms or 0) != int(src_size or 0):
                    return False
                if mm is not None and int(mm or 0) != int(src_mtime or 0):
                    return False
                if str(m.get("tool") or "") != "nisb_docx_convert_to_note":
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
                    "message": "Target markdown already exists (same docx).",
                    "already_exists": True,
                    "uid": uid,
                    "docx_path": docx_rel,
                    "md_path": md_rel,
                    "images_dir": images_rel,
                    "mode": "single",
                }
            return {"success": False, "message": f"Target markdown exists (overwrite=false): {md_rel}", "md_path": md_rel}

        if overwrite and os.path.exists(abs_md):
            m0 = _safe_read_json(manifest_abs)
            if not _manifest_matches(m0):
                return {"success": False, "message": "Refuse to overwrite: manifest missing or not match docx_path.", "md_path": md_rel}

        # IMPORTANT: lock_payload must exist regardless of skip_global_lock.
        lock_payload = json.dumps(
            {"pid": os.getpid(), "uid": uid, "source_path": docx_rel, "started_at": int(time.time()), "tool": "nisb_docx_convert_to_note"},
            ensure_ascii=False,
        )

        # global lock (optional)
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

        # target lock (always)
        target_lock_path = abs_md + ".office_convert.lock"
        try:
            _acquire_lock(target_lock_path, lock_payload)
        except FileExistsError:
            return {"success": False, "message": "Conversion is already running for this target (lock exists).", "uid": uid, "docx_path": docx_rel, "target_lock_path": target_lock_path}

        # overwrite cleanup (safe)
        if overwrite:
            try:
                if os.path.exists(abs_md):
                    os.remove(abs_md)
            except Exception:
                pass
            _rm_tree_safe(abs_images_dir)

        os.makedirs(abs_images_dir, exist_ok=True)

        # Header.
        header = []
        header.append(f"# {docx_stem}")
        header.append("")
        header.append(f"> {_office_docx_note_label(locale, 'source_docx')}: {docx_rel}")
        header.append(f"> {_office_docx_note_label(locale, 'images')}: {images_rel}")
        header.append("")
        header.append("---")
        header.append("")
        _atomic_write_text(abs_md, "\n".join(header))

        # Convert DOCX to HTML and extract images.
        img_counter = [0]

        def _handle_image(image):
            img_counter[0] += 1
            ct = str(getattr(image, "content_type", "") or "").lower()
            ext = "png"
            if ct.endswith("jpeg") or ct.endswith("jpg"):
                ext = "jpg"
            elif ct.endswith("png"):
                ext = "png"
            elif ct.endswith("gif"):
                ext = "gif"
            elif ct.endswith("bmp"):
                ext = "bmp"
            elif ct.endswith("svg+xml"):
                ext = "svg"
            elif "/" in ct:
                ext2 = ct.split("/")[-1].strip() or "png"
                ext = re.sub(r"[^a-z0-9]+", "", ext2)[:8] or "png"

            fn = f"img_{img_counter[0]:04d}.{ext}"
            abs_img = os.path.join(abs_images_dir, fn)
            with image.open() as f:
                data = f.read()
            with open(abs_img, "wb") as out:
                out.write(data)
            return {"src": fn}

        with open(abs_docx, "rb") as f:
            result = mammoth.convert_to_html(f, convert_image=mammoth.images.img_element(_handle_image))

        html = str(getattr(result, "value", "") or "")

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        md_body = h.handle(html)

        md_body2 = _rewrite_md_images(md_body or "", images_rel_dir=images_rel)
        _append_text(abs_md, md_body2 or "")

        warnings = []
        try:
            msgs = getattr(result, "messages", None)
            if msgs:
                warnings = [str(x) for x in msgs][:50]
        except Exception:
            warnings = []

        _atomic_write_json(manifest_abs, {
            "tool": "nisb_docx_convert_to_note",
            "uid": uid,
            "source_path": docx_rel,
            "source_size": src_size,
            "source_mtime": src_mtime,
            "md_path": md_rel,
            "images_dir": images_rel,
            "created_at": int(time.time()),
        })

        return {
            "success": True,
            "message": "DOCX converted (single).",
            "uid": uid,
            "docx_path": docx_rel,
            "md_path": md_rel,
            "images_dir": images_rel,
            "mode": "single",
            "warnings": warnings,
        }

    except Exception as e:
        return {"success": False, "message": f"DOCX convert failed: {str(e)}"}
    finally:
        _release_lock(target_lock_path)
        _release_lock(user_lock_path)

