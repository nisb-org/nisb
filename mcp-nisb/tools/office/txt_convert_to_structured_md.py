import os
import re
import time
import json
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from tools.i18n.backend_i18n import normalize_backend_locale


RULESET_VERSION = "txt_structured_md_v1"


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


def _atomic_write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".md", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
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
    return f"/data/users/{uid}/.locks/nisb_txt_convert.lock"


def _read_text_best_effort(abs_txt: str, max_bytes: int = 50 * 1024 * 1024) -> Tuple[str, str]:
    with open(abs_txt, "rb") as f:
        b = f.read(int(max_bytes or 0) if max_bytes else 50 * 1024 * 1024)

    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return b.decode(enc), enc
        except Exception:
            pass
    return b.decode("latin-1", errors="replace"), "latin-1"


def _default_output_md_path(txt_rel: str) -> str:
    p = str(txt_rel or "").replace("\\", "/")
    if p.lower().endswith(".txt"):
        stem = p[:-4]
    else:
        stem = p
    return f"{stem}_txt.md"


def _compile_rules() -> List[Tuple[int, re.Pattern]]:
    zh_num = r"[一二三四五六七八九十百千万零〇两俩壹贰叁肆伍陆柒捌玖拾佰仟0-9]+"
    roman = r"[ivxlcdm]+"
    en_num = (
        r"[0-9]+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
        r"nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred"
    )
    sep = r"[\s\.:：\-—–_、，,\)）\]\】]*"

    rules: List[Tuple[int, re.Pattern]] = []

    # Chinese top-level containers: 卷/部/篇/册/集
    rules.append((1, re.compile(rf"^\s*第\s*{zh_num}\s*(卷|部|篇|册|集)\s*.*$", re.IGNORECASE)))
    rules.append((1, re.compile(rf"^\s*(卷|部|篇|册|集)\s*{zh_num}\s*.*$", re.IGNORECASE)))

    # Chinese front/back matter and common fiction/non-fiction markers
    rules.append((
        1,
        re.compile(
            r"^\s*(序|序章|序言|前言|引言|导言|楔子|总序|自序|绪论|后记|跋|尾声|终章|附录|番外)\s*([\.:：\-—–、].*)?$",
            re.IGNORECASE,
        ),
    ))

    # Chinese chapters: 章/回/话
    rules.append((2, re.compile(rf"^\s*第\s*{zh_num}\s*(章|回|话)\s*.*$", re.IGNORECASE)))
    rules.append((2, re.compile(rf"^\s*{zh_num}\s*(章|回|话)\s*.*$", re.IGNORECASE)))

    # Chinese sections
    rules.append((3, re.compile(rf"^\s*第\s*{zh_num}\s*(节|小节)\s*.*$", re.IGNORECASE)))
    rules.append((3, re.compile(rf"^\s*{zh_num}\s*(节|小节)\s*.*$", re.IGNORECASE)))

    # Numbered headings: 1.1 Title / 2.3.4 Title
    rules.append((3, re.compile(r"^\s*[0-9]+(\.[0-9]+){1,3}\s+\S.{0,100}$", re.IGNORECASE)))

    # Chinese list-like headings: 一、背景 / （一）范围 / 1. 背景
    rules.append((
        2,
        re.compile(
            r"^\s*[（(]?\s*[一二三四五六七八九十百千零〇两壹贰叁肆伍陆柒捌玖拾0-9]{1,4}\s*[、\.．\)）]\s*\S.{0,100}$",
            re.IGNORECASE,
        ),
    ))

    # English top-level containers
    rules.append((1, re.compile(rf"^\s*(book|part|volume){sep}({en_num})\b.*$", re.IGNORECASE)))
    rules.append((
        1,
        re.compile(
            r"^\s*(preface|foreword|introduction|prologue|epilogue|afterword|appendix|conclusion|abstract|summary|references|bibliography|acknowledgements|acknowledgments)\b.*$",
            re.IGNORECASE,
        ),
    ))

    # English chapters
    rules.append((2, re.compile(rf"^\s*(chapter|chap\.){sep}({en_num})\b.*$", re.IGNORECASE)))

    # Roman-numbered headings: I. Title / II) Title
    rules.append((2, re.compile(rf"^\s*({roman})\s*[\.\)]\s+\S.{{0,100}}$", re.IGNORECASE)))

    # English sections
    rules.append((3, re.compile(rf"^\s*(section|sec\.){sep}([0-9]+|[0-9]+(\.[0-9]+)+|{roman})\b.*$", re.IGNORECASE)))

    return rules


def _normalize_heading_text(s: str) -> str:
    t = str(s or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _looks_like_heading_candidate(s: str) -> bool:
    t = str(s or "").strip()
    if not t:
        return False
    if len(t) > 140:
        return False

    strong_prefix = re.match(
        r"^(第|卷|部|篇|册|集|序|序章|序言|前言|引言|导言|楔子|总序|自序|绪论|后记|跋|尾声|终章|附录|番外|book\b|part\b|volume\b|chapter\b|chap\.|section\b|sec\.|preface\b|foreword\b|introduction\b|prologue\b|epilogue\b|afterword\b|appendix\b|conclusion\b|abstract\b|summary\b|references\b|bibliography\b|acknowledgements\b|acknowledgments\b)",
        t,
        re.IGNORECASE,
    )
    if strong_prefix:
        return True

    if len(t) > 90:
        return False
    if re.search(r"[。！？!?]$", t):
        return False
    if len(re.findall(r"[，,；;]", t)) >= 3:
        return False
    return True


def _to_md_structured(text: str, max_lines: int = 200000) -> Tuple[str, Dict[str, Any]]:
    all_lines = text.splitlines()
    truncated = False

    if max_lines and len(all_lines) > int(max_lines):
        lines = all_lines[: int(max_lines)]
        truncated = True
    else:
        lines = all_lines

    rules = _compile_rules()
    out: List[str] = []
    paragraph_buf: List[str] = []

    def flush_paragraph():
        nonlocal paragraph_buf, out
        if not paragraph_buf:
            return
        para = "  \n".join([x.rstrip() for x in paragraph_buf]).strip()
        if para:
            out.append(para)
            out.append("")
        paragraph_buf = []

    for raw in lines:
        line = str(raw or "").rstrip("\n\r")
        stripped = line.strip()

        if stripped == "":
            flush_paragraph()
            continue

        if _looks_like_heading_candidate(stripped):
            level_hit: Optional[int] = None
            for level, pat in rules:
                if pat.match(stripped):
                    level_hit = level
                    break
            if level_hit is not None:
                flush_paragraph()
                hashes = "#" * int(level_hit)
                out.append(f"{hashes} {_normalize_heading_text(stripped)}")
                out.append("")
                continue

        paragraph_buf.append(stripped)

    flush_paragraph()
    while out and out[-1] == "":
        out.pop()

    meta = {
        "ruleset_version": RULESET_VERSION,
        "lines_in": len(all_lines),
        "lines_used": len(lines),
        "truncated": truncated,
    }
    return ("\n".join(out) + "\n"), meta


def nisb_txt_convert_to_structured_md(
    txt_path,
    uid: str = "",
    workspace_id: str = "",
    output_md_path: str = "",
    overwrite: bool = False,
    language_hint: str = "auto",
    max_lines: int = 200000,
    locale: str = "en",
):
    """
    Convert a TXT file into structured Markdown using lightweight heading rules.
    """
    user_lock_path = ""
    target_lock_path = ""

    try:
        if isinstance(txt_path, dict):
            args = txt_path
            txt_path = args.get("txt_path", "")
            uid = args.get("uid", uid) or uid
            workspace_id = args.get("workspace_id", workspace_id) or workspace_id
            output_md_path = args.get("output_md_path", output_md_path) or output_md_path
            overwrite = bool(args.get("overwrite", overwrite))
            language_hint = args.get("language_hint", language_hint) or language_hint
            locale = args.get("locale", args.get("ui_locale", args.get("language", locale))) or locale
            try:
                max_lines = int(args.get("max_lines", max_lines))
            except Exception:
                pass

        uid = _safe_uid(uid)
        workspace_id = _safe_workspace_id(workspace_id)
        locale = normalize_backend_locale(locale)

        txt_rel = _strip_invisible(_safe_rel_path(txt_path))
        if "?" in txt_rel:
            txt_rel = txt_rel.split("?", 1)[0]
        if "#" in txt_rel:
            txt_rel = txt_rel.split("#", 1)[0]
        txt_rel = _strip_invisible(txt_rel)

        ext = os.path.splitext(txt_rel)[1].lower()
        if ext != ".txt":
            return {"success": False, "message": "txt_path must end with .txt", "debug_txt_path_repr": repr(txt_rel), "debug_ext": ext}

        abs_txt = _resolve_under_user(uid, txt_rel)
        if not os.path.exists(abs_txt):
            return {"success": False, "message": f"TXT not found: {txt_rel}", "uid": uid, "txt_path": txt_rel}

        try:
            st = os.stat(abs_txt)
            src_size = int(st.st_size)
            src_mtime = int(st.st_mtime)
        except Exception:
            src_size = 0
            src_mtime = 0

        if not output_md_path:
            output_md_path = _default_output_md_path(txt_rel)

        md_rel = _strip_invisible(_safe_rel_path(output_md_path))
        if not md_rel.lower().endswith(".md"):
            return {"success": False, "message": "output_md_path must end with .md", "output_md_path": md_rel}

        abs_md = _resolve_under_user(uid, md_rel)

        user_lock_path = _user_global_lock_path(uid)
        lock_payload = json.dumps(
            {
                "pid": os.getpid(),
                "uid": uid,
                "source_path": txt_rel,
                "target_path": md_rel,
                "started_at": int(time.time()),
                "tool": "nisb_txt_convert_to_structured_md",
                "ruleset_version": RULESET_VERSION,
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
                "message": "Busy: another txt conversion is running for this uid (max_concurrent=1).",
                "uid": uid,
                "lock_path": user_lock_path,
                "lock_content": existing,
            }

        target_lock_path = abs_md + ".txt_to_structured_md.lock"
        try:
            _acquire_lock(target_lock_path, lock_payload)
        except FileExistsError:
            return {
                "success": False,
                "message": "Conversion is already running for this target (lock exists).",
                "uid": uid,
                "txt_path": txt_rel,
                "md_path": md_rel,
                "target_lock_path": target_lock_path,
            }

        manifest_abs = abs_md + ".txt_structured_md.manifest.json"

        def _manifest_matches(m: dict) -> bool:
            try:
                if not isinstance(m, dict):
                    return False
                if str(m.get("tool") or "") != "nisb_txt_convert_to_structured_md":
                    return False
                if str(m.get("ruleset_version") or "") != RULESET_VERSION:
                    return False
                if str(m.get("source_txt_path") or "") != txt_rel:
                    return False
                if int(m.get("source_size") or 0) != int(src_size or 0):
                    return False
                if int(m.get("source_mtime") or 0) != int(src_mtime or 0):
                    return False
                if str(m.get("output_md_path") or "") != md_rel:
                    return False
                return True
            except Exception:
                return False

        if os.path.exists(abs_md) and (not overwrite):
            m0 = _safe_read_json(manifest_abs)
            if _manifest_matches(m0):
                return {"success": True, "md_path": md_rel, "already_exists": True, "message": "Already converted (manifest hit)."}
            return {"success": False, "md_path": md_rel, "already_exists": True, "message": f"Target MD exists (overwrite=false): {md_rel}"}

        if overwrite and os.path.exists(abs_md):
            m0 = _safe_read_json(manifest_abs)
            if not _manifest_matches(m0):
                return {"success": False, "message": "Refuse to overwrite: manifest missing or not match txt_path/ruleset.", "md_path": md_rel}

        raw_text, enc_used = _read_text_best_effort(abs_txt)
        try:
            md_text, convert_meta = _to_md_structured(raw_text, max_lines=max_lines)
        except Exception:
            md_text = (raw_text or "").strip() + "\n"
            convert_meta = {"ruleset_version": RULESET_VERSION, "fallback": True}

        _atomic_write_text(abs_md, md_text)

        _atomic_write_json(
            manifest_abs,
            {
                "tool": "nisb_txt_convert_to_structured_md",
                "uid": uid,
                "workspace_id": workspace_id,
                "source_txt_path": txt_rel,
                "source_size": src_size,
                "source_mtime": src_mtime,
                "output_md_path": md_rel,
                "language_hint": str(language_hint or "auto"),
                "locale": locale,
                "max_lines": int(max_lines or 0),
                "encoding_used": enc_used,
                "convert_meta": convert_meta,
                "ruleset_version": RULESET_VERSION,
                "created_at": int(time.time()),
            },
        )

        return {"success": True, "md_path": md_rel, "already_exists": False, "message": "Converted."}

    except Exception as e:
        return {"success": False, "message": f"TXT convert failed: {str(e)}"}
    finally:
        _release_lock(target_lock_path)
        _release_lock(user_lock_path)

