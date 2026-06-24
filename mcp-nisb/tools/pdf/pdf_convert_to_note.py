# /opt/mcp-gateway/mcp-nisb/tools/pdf/pdf_convert_to_note.py
import os
import re
import time
import json
import shutil
import tempfile
import gc
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


def _to_nisb_file_link(rel_path: str, workspace_id: str) -> str:
    rel_path = str(rel_path or "").replace("\\", "/").lstrip("/")
    ws = str(workspace_id or "").strip()
    if ws:
        return "nisb://file?ws=" + quote(ws, safe="") + "&type=file&path=" + quote(rel_path, safe="")
    return _to_nisb_path_only(rel_path)


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
    return f"/data/users/{uid}/.locks/nisb_pdf_convert.lock"


_PDF_NOTE_LABELS = {
    "source_pdf": {"en": "Source PDF", "zh-CN": "来源 PDF"},
    "images": {"en": "Images", "zh-CN": "图片"},
    "output_dir": {"en": "Output directory", "zh-CN": "输出目录"},
    "contents": {"en": "Contents", "zh-CN": "目录"},
    "start_page": {"en": "Start page", "zh-CN": "起始页"},
    "part": {"en": "Part", "zh-CN": "部分"},
}


def _pdf_note_label(locale: str, key: str) -> str:
    return i18n_text(locale, _PDF_NOTE_LABELS.get(key), key)


def nisb_pdf_convert_to_note(
    pdf_path,
    uid: str = "",
    workspace_id: str = "",
    output_md_path: str = "",
    image_dirname: str = "images",
    image_format: str = "png",
    dpi: int = 150,
    overwrite: bool = False,
    pages_per_batch: int = 3,
    max_seconds: int = 1800,
    split_mode: str = "auto",            # auto | single | split
    split_threshold_pages: int = 120,    # auto: >该页数则 split
    split_pages: int = 25,               # 兼容旧参数：作为“单 part 最大页数”上限（防极端）
    write_images: bool = True,
    target_lines_per_part: int = 10000,  # Split part by approximate line count.
    resume: bool = False,                # Continue from previous progress.
    resume_from_page: int = -1,          # 0-based page index; -1 uses progress.pages_done.
    locale: str = "en"                   # UI locale for generated note wrapper text.
):
    """
    Convert a PDF into Markdown plus extracted images.

    Image references are rewritten to nisb://file?path=... URLs so NISB can
    render them consistently.

    Split mode behavior:
    - If the target exists and its manifest matches the same PDF:
      - resume=false returns success=true + already_exists=true.
      - resume=true continues from progress.pages_done or resume_from_page.
    """
    user_lock_path = ""
    target_lock_path = ""
    _progress_path_for_error = ""
    _progress_state_for_error = {}

    try:
        # MCP dict args
        if isinstance(pdf_path, dict):
            args = pdf_path
            pdf_path = args.get("pdf_path", "")
            uid = args.get("uid", uid) or uid
            workspace_id = args.get("workspace_id", workspace_id) or workspace_id
            output_md_path = args.get("output_md_path", output_md_path) or output_md_path
            image_dirname = args.get("image_dirname", image_dirname) or image_dirname
            image_format = args.get("image_format", image_format) or image_format
            overwrite = bool(args.get("overwrite", overwrite))
            write_images = bool(args.get("write_images", write_images))
            split_mode = str(args.get("split_mode", split_mode) or split_mode)
            resume = bool(args.get("resume", resume))
            locale = args.get("locale", args.get("ui_locale", args.get("language", locale))) or locale
            try:
                resume_from_page = int(args.get("resume_from_page", resume_from_page))
            except Exception:
                resume_from_page = resume_from_page

            try:
                dpi = int(args.get("dpi", dpi))
            except Exception:
                pass
            try:
                pages_per_batch = int(args.get("pages_per_batch", pages_per_batch))
            except Exception:
                pass
            try:
                max_seconds = int(args.get("max_seconds", max_seconds))
            except Exception:
                pass
            try:
                split_threshold_pages = int(args.get("split_threshold_pages", split_threshold_pages))
            except Exception:
                pass
            try:
                split_pages = int(args.get("split_pages", split_pages))
            except Exception:
                pass
            try:
                if "target_lines_per_part" in args:
                    target_lines_per_part = int(args.get("target_lines_per_part"))
            except Exception:
                pass

        try:
            import pymupdf4llm
        except Exception as e:
            return {"success": False, "message": "Missing dependency: pymupdf4llm.", "detail": str(e)}

        try:
            import fitz  # PyMuPDF
        except Exception as e:
            return {"success": False, "message": "Missing dependency: PyMuPDF (pymupdf).", "detail": str(e)}

        uid = _safe_uid(uid)
        workspace_id = _safe_workspace_id(workspace_id)
        locale = normalize_backend_locale(locale)

        pdf_rel = _strip_invisible(_safe_rel_path(pdf_path))
        if "?" in pdf_rel:
            pdf_rel = pdf_rel.split("?", 1)[0]
        if "#" in pdf_rel:
            pdf_rel = pdf_rel.split("#", 1)[0]
        pdf_rel = _strip_invisible(pdf_rel)

        ext0 = os.path.splitext(pdf_rel)[1].lower()
        if ext0 != ".pdf":
            return {"success": False, "message": "pdf_path must end with .pdf", "debug_pdf_path_repr": repr(pdf_rel), "debug_ext": ext0}

        abs_pdf = _resolve_under_user(uid, pdf_rel)
        if not os.path.exists(abs_pdf):
            return {"success": False, "message": f"PDF not found: {pdf_rel}"}

        try:
            st = os.stat(abs_pdf)
            pdf_size = int(st.st_size)
            pdf_mtime = int(st.st_mtime)
        except Exception:
            pdf_size = 0
            pdf_mtime = 0

        doc0 = fitz.open(abs_pdf)
        try:
            total_pages = int(doc0.page_count or 0)
        finally:
            try:
                doc0.close()
            except Exception:
                pass

        mode = (split_mode or "auto").strip().lower()
        if mode not in ("auto", "single", "split"):
            return {"success": False, "message": "split_mode must be one of: auto|single|split"}
        if mode == "auto":
            mode = "split" if total_pages > int(split_threshold_pages or 120) else "single"

        fmt = str(image_format or "png").lstrip(".")
        if pages_per_batch < 1:
            pages_per_batch = 1
        if split_pages < 1:
            split_pages = 25
        if max_seconds < 60:
            max_seconds = 60
        if target_lines_per_part < 2000:
            target_lines_per_part = 2000

        # Low-memory guard: reduce DPI for very large PDFs.
        if total_pages > 300 and int(dpi or 150) >= 150:
            dpi = 110

        t0 = time.time()

        pdf_dir_rel = os.path.dirname(pdf_rel).replace("\\", "/").strip("/")
        pdf_stem = os.path.basename(pdf_rel).rsplit(".", 1)[0]

        def _manifest_matches(m: dict) -> bool:
            try:
                if not isinstance(m, dict):
                    return False
                if str(m.get("pdf_path") or "") != pdf_rel:
                    return False
                ms = m.get("pdf_size", None)
                mm = m.get("pdf_mtime", None)
                if ms is not None and int(ms or 0) != int(pdf_size or 0):
                    return False
                if mm is not None and int(mm or 0) != int(pdf_mtime or 0):
                    return False
                return True
            except Exception:
                return False

        # Pre-check output target and choose the target lock path.
        if mode == "single":
            if output_md_path:
                md_rel = _strip_invisible(_safe_rel_path(output_md_path))
                if os.path.splitext(md_rel)[1].lower() != ".md":
                    return {"success": False, "message": "output_md_path must end with .md (single mode)"}
            else:
                md_rel = re.sub(r"\.pdf$", ".md", pdf_rel, flags=re.IGNORECASE)

            abs_md = _resolve_under_user(uid, md_rel)
            if os.path.exists(abs_md) and not overwrite:
                return {"success": False, "message": f"Target markdown exists (overwrite=false): {md_rel}", "md_path": md_rel}

            target_lock_path = abs_md + ".pdf_convert.lock"

        else:
            base_dir_rel = f"{pdf_dir_rel}/{pdf_stem}_md" if pdf_dir_rel else f"{pdf_stem}_md"
            index_md_rel = f"{base_dir_rel}/index.md"

            if output_md_path:
                out_rel = _strip_invisible(_safe_rel_path(output_md_path))
                if out_rel.lower().endswith(".md"):
                    index_md_rel = out_rel
                    base_dir_rel = os.path.dirname(index_md_rel).replace("\\", "/").strip("/")
                else:
                    base_dir_rel = out_rel.rstrip("/").rstrip("\\")
                    index_md_rel = f"{base_dir_rel}/index.md"

            abs_base_dir = _resolve_under_user(uid, base_dir_rel)
            abs_index = _resolve_under_user(uid, index_md_rel)
            manifest_path = _resolve_under_user(uid, f"{base_dir_rel}/.nisb_pdf_convert_manifest.json")
            progress_path0 = abs_index + ".progress.json"

            if os.path.exists(abs_base_dir) and not overwrite:
                m0 = _safe_read_json(manifest_path)
                if _manifest_matches(m0) and (not bool(resume)):
                    prog0 = _safe_read_json(progress_path0)
                    return {
                        "success": True,
                        "message": "Target directory already exists (same pdf).",
                        "mode": "split",
                        "already_exists": True,
                        "uid": uid,
                        "pdf_path": pdf_rel,
                        "base_dir": base_dir_rel,
                        "index_md_path": index_md_rel,
                        "progress": prog0
                    }

                if (not _manifest_matches(m0)) and (not bool(resume)):
                    return {
                        "success": False,
                        "message": f"Target directory exists (overwrite=false): {base_dir_rel}",
                        "index_md_path": index_md_rel,
                        "mode": "split"
                    }

                # resume=true continues into split mode, where progress is loaded.
                if bool(resume) and (not _manifest_matches(m0)):
                    return {
                        "success": False,
                        "message": "Resume refused: manifest missing or not match pdf_path.",
                        "mode": "split",
                        "uid": uid,
                        "pdf_path": pdf_rel,
                        "base_dir": base_dir_rel,
                        "index_md_path": index_md_rel
                    }

            if os.path.exists(abs_base_dir) and overwrite:
                ok = False
                try:
                    m = _safe_read_json(manifest_path)
                    if _manifest_matches(m):
                        ok = True
                except Exception:
                    ok = False
                if not ok:
                    return {"success": False, "message": "Refuse to overwrite: manifest missing or not match pdf_path.", "target_dir": base_dir_rel}

            target_lock_path = abs_index + ".pdf_convert.lock"

        # User-level global lock.
        user_lock_path = _user_global_lock_path(uid)
        lock_payload = json.dumps(
            {"pid": os.getpid(), "uid": uid, "pdf_path": pdf_rel, "started_at": int(time.time())},
            ensure_ascii=False
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
                "message": "Busy: another PDF conversion is running for this uid (max_concurrent=1).",
                "uid": uid,
                "lock_path": user_lock_path,
                "lock_content": existing
            }

        # Target-level lock.
        try:
            _acquire_lock(target_lock_path, lock_payload)
        except FileExistsError:
            return {
                "success": False,
                "message": "Conversion is already running for this target (lock exists).",
                "uid": uid,
                "pdf_path": pdf_rel,
                "target_lock_path": target_lock_path
            }

        # ===== single mode =====
        if mode == "single":
            if output_md_path:
                md_rel = _strip_invisible(_safe_rel_path(output_md_path))
            else:
                md_rel = re.sub(r"\.pdf$", ".md", pdf_rel, flags=re.IGNORECASE)

            abs_md = _resolve_under_user(uid, md_rel)

            md_dir_rel = os.path.dirname(md_rel).replace("\\", "/").strip("/")
            md_stem = os.path.splitext(os.path.basename(md_rel))[0]

            images_dirname2 = str(image_dirname or "images").strip().replace("\\", "/").strip("/")
            images_rel = f"{md_dir_rel}/{md_stem}_{images_dirname2}" if md_dir_rel else f"{md_stem}_{images_dirname2}"

            abs_images_dir = _resolve_under_user(uid, images_rel)
            os.makedirs(abs_images_dir, exist_ok=True)

            header = []
            header.append(f"# {md_stem}")
            header.append("")
            header.append(f"> {_pdf_note_label(locale, 'source_pdf')}: {pdf_rel}")
            header.append(f"> {_pdf_note_label(locale, 'images')}: {images_rel}")
            header.append("")
            header.append("---")
            header.append("")
            _atomic_write_text(abs_md, "\n".join(header))

            doc = fitz.open(abs_pdf)
            try:
                md_text = pymupdf4llm.to_markdown(
                    doc=doc,
                    write_images=bool(write_images),
                    image_path=abs_images_dir,
                    image_format=fmt,
                    dpi=int(dpi or 150),
                    embed_images=False,
                    force_text=True,
                    show_progress=False
                )
            finally:
                try:
                    doc.close()
                except Exception:
                    pass

            md_text2 = _rewrite_md_images(md_text or "", images_rel_dir=images_rel)
            _append_text(abs_md, md_text2 or "")

            return {
                "success": True,
                "message": "PDF converted (single).",
                "uid": uid,
                "pdf_path": pdf_rel,
                "md_path": md_rel,
                "images_dir": images_rel,
                "total_pages": total_pages,
                "elapsed_seconds": int(time.time() - t0),
                "mode": "single"
            }

        # ===== split mode =====
        base_dir_rel = f"{pdf_dir_rel}/{pdf_stem}_md" if pdf_dir_rel else f"{pdf_stem}_md"
        index_md_rel = f"{base_dir_rel}/index.md"
        if output_md_path:
            out_rel = _strip_invisible(_safe_rel_path(output_md_path))
            if out_rel.lower().endswith(".md"):
                index_md_rel = out_rel
                base_dir_rel = os.path.dirname(index_md_rel).replace("\\", "/").strip("/")
            else:
                base_dir_rel = out_rel.rstrip("/").rstrip("\\")
                index_md_rel = f"{base_dir_rel}/index.md"

        abs_base_dir = _resolve_under_user(uid, base_dir_rel)
        abs_index = _resolve_under_user(uid, index_md_rel)
        abs_parts_dir = _resolve_under_user(uid, f"{base_dir_rel}/parts")
        abs_images_root = _resolve_under_user(uid, f"{base_dir_rel}/images")
        progress_path = abs_index + ".progress.json"
        manifest_path = _resolve_under_user(uid, f"{base_dir_rel}/.nisb_pdf_convert_manifest.json")

        _progress_path_for_error = progress_path
        _progress_state_for_error = {
            "uid": uid,
            "pdf_path": pdf_rel,
            "index_md_path": index_md_rel,
            "base_dir": base_dir_rel,
            "total_pages": total_pages,
            "pages_done": 0,
            "started_at": int(t0),
        }

        # overwrite=true clears previous generated files and starts over.
        if os.path.exists(abs_base_dir) and overwrite:
            _rm_tree_safe(abs_parts_dir)
            _rm_tree_safe(abs_images_root)
            try:
                if os.path.exists(abs_index):
                    os.remove(abs_index)
            except Exception:
                pass
            try:
                if os.path.exists(progress_path):
                    os.remove(progress_path)
            except Exception:
                pass

        os.makedirs(abs_parts_dir, exist_ok=True)
        os.makedirs(abs_images_root, exist_ok=True)

        # Ensure a manifest exists; resume also uses it for safety checks.
        m_exist = _safe_read_json(manifest_path)
        if not _manifest_matches(m_exist):
            _atomic_write_json(manifest_path, {
                "pdf_path": pdf_rel,
                "pdf_size": pdf_size,
                "pdf_mtime": pdf_mtime,
                "uid": uid,
                "created_at": int(time.time()),
                "base_dir": base_dir_rel,
                "index_md_path": index_md_rel
            })

        title = pdf_stem

        # Fresh start writes index and progress; resume keeps the existing index when possible.
        if (not os.path.exists(abs_index)) or overwrite:
            index_lines = []
            index_lines.append(f"# {title}")
            index_lines.append("")
            index_lines.append(f"> {_pdf_note_label(locale, 'source_pdf')}: {pdf_rel}")
            index_lines.append(f"> {_pdf_note_label(locale, 'output_dir')}: {base_dir_rel}")
            index_lines.append("")
            index_lines.append(f"## {_pdf_note_label(locale, 'contents')}")
            index_lines.append("")
            _atomic_write_text(abs_index, "\n".join(index_lines))

        # Dynamic part state.
        part_start_page = 0
        part_seq = 0
        part_lines = 0
        part_tmp_tag = ""
        part_md_tmp_rel = ""
        abs_part_md_tmp = ""
        part_images_tmp_rel = ""
        abs_part_images_tmp = ""

        def _start_part(start_page: int) -> None:
            nonlocal part_seq, part_start_page, part_lines, part_tmp_tag, part_md_tmp_rel, abs_part_md_tmp, part_images_tmp_rel, abs_part_images_tmp
            part_seq += 1
            part_start_page = start_page
            part_lines = 0

            part_tmp_tag = f"tmp_{part_seq:04d}"
            part_md_tmp_rel = f"{base_dir_rel}/parts/part_{part_tmp_tag}.md"
            abs_part_md_tmp = _resolve_under_user(uid, part_md_tmp_rel)

            part_images_tmp_rel = f"{base_dir_rel}/images/{part_tmp_tag}"
            abs_part_images_tmp = _resolve_under_user(uid, part_images_tmp_rel)

            os.makedirs(abs_part_images_tmp, exist_ok=True)

            p1 = start_page + 1
            header = []
            header.append(f"# {title} · {_pdf_note_label(locale, 'part')} {part_seq}")
            header.append("")
            header.append(f"> {_pdf_note_label(locale, 'source_pdf')}: {pdf_rel}")
            header.append(f"> {_pdf_note_label(locale, 'start_page')}: {p1} / {total_pages}")
            header.append("")
            header.append("---")
            header.append("")
            _atomic_write_text(abs_part_md_tmp, "\n".join(header))

        def _close_part(end_page_inclusive: int) -> str:
            nonlocal abs_part_md_tmp, abs_part_images_tmp, part_images_tmp_rel, part_start_page

            p1 = part_start_page + 1
            p2 = end_page_inclusive + 1
            final_tag = f"p{p1:04d}_{p2:04d}"

            final_md_rel = f"{base_dir_rel}/parts/part_{final_tag}.md"
            final_md_abs = _resolve_under_user(uid, final_md_rel)

            final_img_rel = f"{base_dir_rel}/images/{final_tag}"
            final_img_abs = _resolve_under_user(uid, final_img_rel)

            try:
                with open(abs_part_md_tmp, "r", encoding="utf-8") as f:
                    txt = f.read()

                old_prefix = f"nisb://file?path={quote((part_images_tmp_rel + '/').lstrip('/'), safe='')}"
                new_prefix = f"nisb://file?path={quote((final_img_rel + '/').lstrip('/'), safe='')}"
                txt = txt.replace(old_prefix, new_prefix)
                txt = txt.replace(part_images_tmp_rel + "/", final_img_rel + "/")
                _atomic_write_text(final_md_abs, txt)
            except Exception:
                try:
                    os.replace(abs_part_md_tmp, final_md_abs)
                except Exception:
                    pass

            try:
                if os.path.exists(final_img_abs):
                    shutil.rmtree(final_img_abs, ignore_errors=True)
                if os.path.exists(abs_part_images_tmp):
                    os.replace(abs_part_images_tmp, final_img_abs)
            except Exception:
                pass

            try:
                if os.path.exists(abs_part_md_tmp):
                    os.remove(abs_part_md_tmp)
            except Exception:
                pass

            return final_md_rel

        def _append_index_link_if_missing(final_rel: str) -> None:
            link = _to_nisb_file_link(final_rel, workspace_id)
            bn = os.path.basename(final_rel)
            try:
                with open(abs_index, "r", encoding="utf-8") as f:
                    idx_txt = f.read()
                if bn in idx_txt:
                    return
            except Exception:
                pass
            _append_text(abs_index, f"- [{bn}]({link})\n")

        # ===== resume / fresh init =====
        prog_old = _safe_read_json(progress_path)
        do_resume = bool(resume) and (not overwrite) and _manifest_matches(_safe_read_json(manifest_path)) and os.path.exists(abs_base_dir)

        if do_resume:
            pages_done0 = 0
            try:
                pages_done0 = int(prog_old.get("pages_done") or 0)
            except Exception:
                pages_done0 = 0
            if isinstance(resume_from_page, int) and resume_from_page >= 0:
                pages_done0 = max(0, min(int(resume_from_page), total_pages))

            # Return directly when conversion has already completed.
            if str(prog_old.get("status") or "") == "done" and pages_done0 >= total_pages:
                return {
                    "success": True,
                    "message": "Already done.",
                    "mode": "split",
                    "already_exists": True,
                    "uid": uid,
                    "pdf_path": pdf_rel,
                    "base_dir": base_dir_rel,
                    "index_md_path": index_md_rel,
                    "progress": prog_old
                }

            # Finalize a tmp part left by a previous timeout if it exists.
            try:
                part_seq0 = int(prog_old.get("part_seq") or 0)
            except Exception:
                part_seq0 = 0
            try:
                part_start0 = int(prog_old.get("current_part_start_page") or 0)
            except Exception:
                part_start0 = 0

            # If progress lacks current_part_start_page, continue from pages_done0.
            if part_start0 < 0 or part_start0 > pages_done0:
                part_start0 = max(0, min(pages_done0, total_pages))

            if part_seq0 > 0 and pages_done0 > part_start0:
                tmp_tag0 = f"tmp_{part_seq0:04d}"
                tmp_md_rel0 = f"{base_dir_rel}/parts/part_{tmp_tag0}.md"
                tmp_md_abs0 = _resolve_under_user(uid, tmp_md_rel0)
                tmp_img_rel0 = f"{base_dir_rel}/images/{tmp_tag0}"
                tmp_img_abs0 = _resolve_under_user(uid, tmp_img_rel0)

                if os.path.exists(tmp_md_abs0) or os.path.isdir(tmp_img_abs0):
                    # Bind to the existing tmp part and close it.
                    part_seq = part_seq0
                    part_start_page = part_start0
                    part_tmp_tag = tmp_tag0
                    part_md_tmp_rel = tmp_md_rel0
                    abs_part_md_tmp = tmp_md_abs0
                    part_images_tmp_rel = tmp_img_rel0
                    abs_part_images_tmp = tmp_img_abs0
                    final_rel0 = _close_part(pages_done0 - 1)
                    _append_index_link_if_missing(final_rel0)

            # 从 pages_done0 继续：开一个新 tmp part
            cur_page = pages_done0
            pages_done = pages_done0
            part_seq = int(prog_old.get("part_seq") or 0)
            part_seq = max(0, part_seq)
            part_seq = part_seq  # _start_part increments it.
            _start_part(cur_page)

            _atomic_write_json(progress_path, {
                "status": "running",
                "uid": uid,
                "pdf_path": pdf_rel,
                "index_md_path": index_md_rel,
                "base_dir": base_dir_rel,
                "total_pages": total_pages,
                "pages_done": pages_done0,
                "part_seq": part_seq,
                "current_part_start_page": part_start_page,
                "started_at": int(prog_old.get("started_at") or time.time()),
                "updated_at": int(time.time()),
                "resumed_at": int(time.time())
            })
        else:
            # Fresh start.
            _start_part(0)
            cur_page = 0
            pages_done = 0
            _atomic_write_json(progress_path, {
                "status": "running",
                "uid": uid,
                "pdf_path": pdf_rel,
                "index_md_path": index_md_rel,
                "base_dir": base_dir_rel,
                "total_pages": total_pages,
                "pages_done": 0,
                "part_seq": part_seq,
                "current_part_start_page": part_start_page,
                "started_at": int(time.time()),
                "updated_at": int(time.time())
            })

        _progress_path_for_error = progress_path
        _progress_state_for_error = {
            "uid": uid,
            "pdf_path": pdf_rel,
            "index_md_path": index_md_rel,
            "base_dir": base_dir_rel,
            "total_pages": total_pages,
            "pages_done": pages_done,
            "started_at": int(t0),
        }

        doc = fitz.open(abs_pdf)
        try:
            while cur_page < total_pages:
                if time.time() - t0 > max_seconds:
                    _atomic_write_json(progress_path, {
                        "status": "timeout",
                        "uid": uid,
                        "pdf_path": pdf_rel,
                        "index_md_path": index_md_rel,
                        "base_dir": base_dir_rel,
                        "total_pages": total_pages,
                        "pages_done": pages_done,
                        "part_seq": part_seq,
                        "current_part_start_page": part_start_page,
                        "started_at": int(prog_old.get("started_at") or t0),
                        "updated_at": int(time.time())
                    })
                    return {
                        "success": False,
                        "message": f"Timeout: exceeded max_seconds={max_seconds}, partial parts written.",
                        "uid": uid,
                        "pdf_path": pdf_rel,
                        "index_md_path": index_md_rel,
                        "base_dir": base_dir_rel,
                        "total_pages": total_pages,
                        "pages_done": pages_done,
                        "mode": "split",
                        "partial": True
                    }

                b_end = min(total_pages, cur_page + pages_per_batch)
                page_list = list(range(cur_page, b_end))

                try:
                    md_part = pymupdf4llm.to_markdown(
                        doc=doc,
                        pages=page_list,
                        write_images=bool(write_images),
                        image_path=abs_part_images_tmp,
                        image_format=fmt,
                        dpi=int(dpi or 150),
                        embed_images=False,
                        force_text=True,
                        show_progress=False
                    )
                except Exception as e:
                    _atomic_write_json(progress_path, {
                        "status": "error",
                        "uid": uid,
                        "pdf_path": pdf_rel,
                        "index_md_path": index_md_rel,
                        "base_dir": base_dir_rel,
                        "total_pages": total_pages,
                        "pages_done": pages_done,
                        "cur_page": cur_page,
                        "batch_end": b_end,
                        "page_list": page_list,
                        "part_seq": part_seq,
                        "current_part_start_page": part_start_page,
                        "error": str(e),
                        "updated_at": int(time.time())
                    })
                    return {
                        "success": False,
                        "message": f"PDF convert failed in batch pages={page_list}: {str(e)}",
                        "uid": uid,
                        "pdf_path": pdf_rel,
                        "index_md_path": index_md_rel,
                        "base_dir": base_dir_rel,
                        "total_pages": total_pages,
                        "pages_done": pages_done,
                        "mode": "split",
                        "partial": True
                    }

                md_part2 = _rewrite_md_images(md_part or "", images_rel_dir=part_images_tmp_rel)
                _append_text(abs_part_md_tmp, md_part2 or "")
                part_lines += (md_part2.count("\n") + 1) if md_part2 else 0

                pages_done = b_end
                cur_page = b_end
                _progress_state_for_error["pages_done"] = pages_done

                _atomic_write_json(progress_path, {
                    "status": "running",
                    "uid": uid,
                    "pdf_path": pdf_rel,
                    "index_md_path": index_md_rel,
                    "base_dir": base_dir_rel,
                    "total_pages": total_pages,
                    "pages_done": pages_done,
                    "part_seq": part_seq,
                    "current_part_start_page": part_start_page,
                    "current_part_lines": part_lines,
                    "started_at": int(prog_old.get("started_at") or t0),
                    "updated_at": int(time.time())
                })

                try:
                    gc.collect()
                except Exception:
                    pass
                try:
                    fitz.TOOLS.store_shrink(100)
                except Exception:
                    pass

                pages_in_part = (cur_page - part_start_page)
                should_break = False
                if part_lines >= target_lines_per_part:
                    should_break = True
                if pages_in_part >= split_pages:
                    should_break = True

                if should_break and cur_page < total_pages:
                    final_rel = _close_part(cur_page - 1)
                    _append_index_link_if_missing(final_rel)
                    _start_part(cur_page)

            # Close the last part.
            final_rel = _close_part(total_pages - 1)
            _append_index_link_if_missing(final_rel)

            _atomic_write_json(progress_path, {
                "status": "done",
                "uid": uid,
                "pdf_path": pdf_rel,
                "index_md_path": index_md_rel,
                "base_dir": base_dir_rel,
                "total_pages": total_pages,
                "pages_done": total_pages,
                "part_seq": part_seq,
                "started_at": int(prog_old.get("started_at") or t0),
                "updated_at": int(time.time()),
                "elapsed_seconds": int(time.time() - t0)
            })

            return {
                "success": True,
                "message": "PDF converted (split).",
                "uid": uid,
                "pdf_path": pdf_rel,
                "index_md_path": index_md_rel,
                "base_dir": base_dir_rel,
                "parts_dir": f"{base_dir_rel}/parts",
                "images_dir": f"{base_dir_rel}/images",
                "total_pages": total_pages,
                "elapsed_seconds": int(time.time() - t0),
                "mode": "split",
                "target_lines_per_part": int(target_lines_per_part)
            }

        finally:
            try:
                doc.close()
            except Exception:
                pass

    except Exception as e:
        try:
            if _progress_path_for_error:
                data = {"status": "error", "error": str(e), "updated_at": int(time.time())}
                if isinstance(_progress_state_for_error, dict):
                    data.update(_progress_state_for_error)
                _atomic_write_json(_progress_path_for_error, data)
        except Exception:
            pass
        return {"success": False, "message": f"PDF convert failed: {str(e)}"}
    finally:
        _release_lock(target_lock_path)
        _release_lock(user_lock_path)

