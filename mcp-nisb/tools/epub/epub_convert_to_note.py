# /opt/mcp-gateway/mcp-nisb/tools/epub/epub_convert_to_note.py
import os
import re
import time
import json
import shutil
import zipfile
import hashlib
import tempfile
import posixpath
from html.parser import HTMLParser
from urllib.parse import unquote, quote
from xml.etree import ElementTree as ET
from typing import Dict, Any, Union, List, Tuple

from tools.i18n.backend_i18n import i18n_text, normalize_backend_locale


USER_ROOT = "/data/users"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _safe_uid(uid: str) -> str:
    s = str(uid or "").strip()
    if not s:
        return os.environ.get("NISB_USER_ID", "") or "nisb_default_user"
    if not re.fullmatch(r"[A-Za-z0-9_\\-]{1,64}", s):
        return os.environ.get("NISB_USER_ID", "") or "nisb_default_user"
    return s


def _safe_rel_path(p: str) -> str:
    s = str(p or "").strip().replace("\\", "/")
    s = s.lstrip("/")
    if not s:
        raise ValueError("epub_path is required")

    parts = [x for x in s.split("/") if x not in ("", ".")]
    if any(x == ".." for x in parts):
        raise ValueError("invalid path: contains ..")

    rel = "/".join(parts)

    allowed_prefixes = (
        "agent_files/",
        "storage/",
        "libraries/",
        "bookmarks/",
        "annotations/",
    )
    if not any(rel.startswith(px) for px in allowed_prefixes):
        raise ValueError(f"invalid path: must start with one of {allowed_prefixes}")

    return rel


def _resolve_under_user(uid: str, rel: str) -> str:
    base = os.path.join(USER_ROOT, uid)
    abs_path = os.path.normpath(os.path.join(base, rel))

    base_norm = os.path.normpath(base) + os.sep
    abs_norm = os.path.normpath(abs_path)
    if not abs_norm.startswith(base_norm):
        raise ValueError("path escapes user root")

    return abs_norm


def _ensure_parent_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def _norm_rel_path(p: str) -> str:
    s = str(p or "").strip().replace("\\", "/")
    s = s.lstrip("/")
    s = re.sub(r"/+", "/", s)
    return s


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


def _slug_filename(name: str, default: str = "image") -> str:
    base = os.path.basename(str(name or "").replace("\\", "/"))
    base = unquote(base)
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", base).strip("_")
    if not base:
        base = default
    return base


def _read_zip_text(zf: zipfile.ZipFile, name: str) -> str:
    b = zf.read(name)
    try:
        return b.decode("utf-8")
    except Exception:
        return b.decode("utf-8", errors="ignore")


def _parse_container_rootfile(zf: zipfile.ZipFile) -> str:
    xml = _read_zip_text(zf, "META-INF/container.xml")
    root = ET.fromstring(xml)
    ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfiles = root.findall(".//c:rootfile", ns) or root.findall(".//rootfile")
    if not rootfiles:
        raise ValueError("Invalid EPUB: container.xml has no rootfile")
    full_path = (rootfiles[0].attrib.get("full-path") or "").strip()
    if not full_path:
        raise ValueError("Invalid EPUB: rootfile full-path missing")
    return full_path


def _parse_opf(zf: zipfile.ZipFile, opf_path: str) -> Tuple[Dict[str, Dict[str, str]], List[str]]:
    xml = _read_zip_text(zf, opf_path)
    root = ET.fromstring(xml)

    def _strip_ns(tag: str) -> str:
        return tag.split("}", 1)[-1] if "}" in tag else tag

    manifest: Dict[str, Dict[str, str]] = {}
    spine: List[str] = []

    for elem in root.iter():
        t = _strip_ns(elem.tag)
        if t == "item":
            item_id = (elem.attrib.get("id") or "").strip()
            href = (elem.attrib.get("href") or "").strip()
            media_type = (elem.attrib.get("media-type") or "").strip()
            if item_id and href:
                manifest[item_id] = {"href": href, "media_type": media_type}
        elif t == "itemref":
            idref = (elem.attrib.get("idref") or "").strip()
            if idref:
                spine.append(idref)

    return manifest, spine

def _norm_epub_href(base_dir: str, href: str) -> str:
    """
    Normalize href to a zip entry path (POSIX).
    - Strips fragment/query
    - Resolves relative href against base_dir (POSIX)
    - Rejects remote/data URIs
    """
    h = unquote(str(href or "")).replace("\\", "/").strip()
    if not h:
        return ""

    # drop fragment & query
    h = h.split("#", 1)[0].split("?", 1)[0].strip()
    if not h:
        return ""

    low = h.lower()
    if low.startswith(("http://", "https://", "data:", "mailto:", "tel:", "javascript:")):
        return ""

    # EPUB has no "webroot": leading "/" is not meaningful in a zip container
    h = h.lstrip("/")

    base = str(base_dir or "").replace("\\", "/").strip().strip("/")
    if base:
        joined = base + "/" + h
    else:
        joined = h

    joined = re.sub(r"/+", "/", joined)

    # IMPORTANT: use posix normpath (zip paths)
    normed = posixpath.normpath(joined)
    normed = normed.lstrip("./")

    # guard: never escape container root
    if normed == ".." or normed.startswith("../"):
        return ""

    return normed

def _to_nisb_file_link(rel_path: str, workspace_id: str) -> str:
    rel_path = _norm_rel_path(rel_path)
    ws = str(workspace_id or "").strip()
    if ws:
        return "nisb://file?ws=" + quote(ws, safe="") + "&type=file&path=" + quote(rel_path, safe="")
    return "nisb://file?path=" + quote(rel_path, safe="")

class _HtmlToMd(HTMLParser):
    def __init__(self, img_resolver):
        super().__init__(convert_charrefs=True)
        self.img_resolver = img_resolver
        self.out = []
        self._buf = []
        self._in_pre = False
        self._link_href = None
        self._link_text = []
        self._heading_level = None

        # picture support
        self._picture_depth = 0
        self._picture_sources = []  # list of src candidates

        # base href (rare in epub, but harmless)
        self._base_href = ""

    def _flush_text(self):
        if not self._buf:
            return
        text = "".join(self._buf)
        self._buf = []
        if not self._in_pre:
            text = re.sub(r"\s+", " ", text)
        self.out.append(text)

    def _norm_attrs(self, attrs):
        a = {}
        for k, v in (attrs or {}).items():
            kk = str(k or "").strip().lower()
            if not kk:
                continue
            a[kk] = "" if v is None else str(v)
        return a

    def _pick_first_from_srcset(self, srcset: str) -> str:
        s = str(srcset or "").strip()
        if not s:
            return ""
        first = s.split(",", 1)[0].strip()
        if not first:
            return ""
        return first.split()[0].strip()

    def _is_placeholder_src(self, src: str) -> bool:
        s = (src or "").strip().lower()
        if not s:
            return True
        if s.startswith("data:image/"):
            return True
        # common 1x1 gif placeholder
        if s.startswith("data:") and "gif" in s:
            return True
        return False

    def _apply_base_href(self, href: str) -> str:
        h = (href or "").strip()
        if not h:
            return ""
        # if absolute scheme, keep
        low = h.lower()
        if low.startswith(("http://", "https://", "data:", "mailto:", "tel:", "javascript:")):
            return h
        # if base href provided and href is relative, prefix it
        b = (self._base_href or "").strip()
        if b and not h.startswith(("/", "\\")) and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", h):
            # simple join (zip resolver later will normpath)
            return b.rstrip("/") + "/" + h
        return h

    def _pick_lazy_img_src(self, a: dict) -> str:
        """
        Prefer real image src for lazy-loading patterns. [web:52]
        """
        # common lazy attrs in the wild
        cand_keys = [
            "data-src",
            "data-original",
            "data-lazy-src",
            "data-actualsrc",
            "nitro-lazy-src",
            "data-url",
        ]
        for k in cand_keys:
            v = (a.get(k) or "").strip()
            if v:
                return v

        # srcset-based lazy
        for k in ["data-srcset", "data-original-srcset", "nitro-lazy-srcset"]:
            v = (a.get(k) or "").strip()
            if v:
                return self._pick_first_from_srcset(v)

        return ""

    def _pick_img_src(self, a: dict) -> str:
        # 1) lazy first (real image)
        lazy = self._pick_lazy_img_src(a)
        if lazy:
            return self._apply_base_href(lazy)

        # 2) normal src
        src = (a.get("src") or "").strip()
        if src:
            return self._apply_base_href(src)

        # 3) srcset fallback
        srcset = (a.get("srcset") or "").strip()
        if srcset:
            return self._apply_base_href(self._pick_first_from_srcset(srcset))

        return ""

    def _pick_svg_image_href(self, a: dict) -> str:
        # SVG2 prefers 'href' over deprecated 'xlink:href' [web:39][web:37]
        href = (a.get("href") or "").strip()
        if href:
            return self._apply_base_href(href)
        xhref = (a.get("xlink:href") or "").strip()
        if xhref:
            return self._apply_base_href(xhref)
        # odd books may use src
        src = (a.get("src") or "").strip()
        if src:
            return self._apply_base_href(src)
        return ""

    def _pick_alt(self, a: dict) -> str:
        return (a.get("alt") or a.get("aria-label") or a.get("title") or a.get("id") or "").strip()

    def _extract_urls_from_style(self, style_text: str):
        """
        Extract url(...) targets from inline style, e.g. background-image:url(x). [web:62]
        """
        s = str(style_text or "")
        if not s:
            return []
        # findall url( ... )
        urls = re.findall(r"url\(\s*([^\)]+)\s*\)", s, flags=re.IGNORECASE)
        out = []
        for u in urls:
            u = u.strip().strip('"').strip("'").strip()
            if not u:
                continue
            out.append(self._apply_base_href(u))
        return out

    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower().strip()
        attrs = dict(attrs or [])
        a = self._norm_attrs(attrs)

        if tag in ("p", "div", "section", "article"):
            self._flush_text()
            self.out.append("\n\n")
        elif tag == "br":
            self._flush_text()
            self.out.append("\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush_text()
            self._heading_level = int(tag[1])
            self.out.append("\n\n" + ("#" * self._heading_level) + " ")
        elif tag == "pre":
            self._flush_text()
            self._in_pre = True
            self.out.append("\n\n```\n")
        elif tag == "code":
            if not self._in_pre:
                self._flush_text()
                self.out.append("`")
        elif tag == "a":
            self._flush_text()
            self._link_href = a.get("href", "") or ""
            self._link_text = []
        elif tag == "base":
            # base href
            bh = (a.get("href") or "").strip()
            if bh and not bh.lower().startswith(("http://", "https://", "data:", "mailto:", "tel:", "javascript:")):
                self._base_href = bh.strip().lstrip("/")
        elif tag == "picture":
            self._picture_depth += 1
            self._picture_sources = []
        elif tag == "source":
            # picture/source candidate
            if self._picture_depth > 0:
                srcset = (a.get("srcset") or a.get("data-srcset") or "").strip()
                if srcset:
                    cand = self._pick_first_from_srcset(srcset)
                    if cand:
                        self._picture_sources.append(self._apply_base_href(cand))

        # inline style background images
        style_text = (a.get("style") or "").strip()
        if style_text:
            urls = self._extract_urls_from_style(style_text)
            for u in urls:
                md_img = self.img_resolver(u, "background")
                if md_img:
                    self._flush_text()
                    self.out.append("\n\n" + md_img + "\n\n")

        # images
        if tag == "img":
            self._flush_text()
            alt = self._pick_alt(a)

            src = self._pick_img_src(a)

            # if inside picture and img src is placeholder, use first <source> candidate
            if self._picture_depth > 0 and self._is_placeholder_src(src) and self._picture_sources:
                src = self._picture_sources

            if src:
                md_img = self.img_resolver(src, alt)
                if md_img:
                    self.out.append("\n\n" + md_img + "\n\n")

        elif tag in ("image", "feimage"):
            # SVG embedded image
            self._flush_text()
            alt = self._pick_alt(a) or "svg"
            href = self._pick_svg_image_href(a)
            if href:
                md_img = self.img_resolver(href, alt)
                if md_img:
                    self.out.append("\n\n" + md_img + "\n\n")

    def handle_endtag(self, tag):
        tag = (tag or "").lower().strip()

        if tag in ("p", "div", "section", "article"):
            self._flush_text()
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush_text()
            self._heading_level = None
        elif tag == "pre":
            self._flush_text()
            self._in_pre = False
            self.out.append("\n```\n")
        elif tag == "code":
            if not self._in_pre:
                self._flush_text()
                self.out.append("`")
        elif tag == "a":
            self._flush_text()
            txt = "".join(self._link_text).strip()
            href = (self._link_href or "").strip()
            self._link_href = None
            self._link_text = []
            if txt and href:
                self.out.append(f"[{txt}]({href})")
            elif txt:
                self.out.append(txt)
        elif tag == "picture":
            if self._picture_depth > 0:
                self._picture_depth -= 1
            if self._picture_depth == 0:
                self._picture_sources = []

    def handle_data(self, data):
        if data is None:
            return
        if self._link_href is not None:
            self._link_text.append(str(data))
            return
        self._buf.append(str(data))

    def get_markdown(self) -> str:
        self._flush_text()
        s = "".join(self.out)
        s = re.sub(r"\n{4,}", "\n\n\n", s)
        s = s.strip() + "\n"
        return s

def _list_dir_entries(abs_dir: str) -> List[str]:
    try:
        xs = os.listdir(abs_dir)
    except Exception:
        return []
    out = []
    for x in xs:
        if x in (".", "..", ".DS_Store", "Thumbs.db"):
            continue
        out.append(x)
    return out


def _dir_is_empty(abs_dir: str) -> bool:
    return len(_list_dir_entries(abs_dir)) == 0


def _looks_like_nisb_convert_dir(abs_dir: str) -> bool:
    entries = _list_dir_entries(abs_dir)
    if not entries:
        return True

    allowed = {
        "index.md",
        "parts",
        "images",
        ".nisb_epub_convert_manifest.json",
        ".progress.json",
        "index.md.progress.json",
        "index.md.progress",
    }
    for e in entries:
        if e not in allowed:
            return False
    return True


def _read_json_safe(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            x = json.load(f)
        if isinstance(x, dict):
            return x
    except Exception:
        pass
    return {}


def _count_lines(s: str) -> int:
    if not s:
        return 0
    return s.count("\n") + 1


def _migrate_dir_files(src_dir: str, dst_dir: str) -> int:
    if not src_dir or not os.path.exists(src_dir) or not os.path.isdir(src_dir):
        return 0
    os.makedirs(dst_dir, exist_ok=True)
    moved = 0
    for name in os.listdir(src_dir):
        if name in (".", ".."):
            continue
        sp = os.path.join(src_dir, name)
        if not os.path.isfile(sp):
            continue
        dp = os.path.join(dst_dir, name)
        try:
            if os.path.exists(dp):
                os.remove(dp)
        except Exception:
            pass
        try:
            shutil.move(sp, dp)
            moved += 1
        except Exception:
            try:
                shutil.copy2(sp, dp)
                os.remove(sp)
                moved += 1
            except Exception:
                pass
    try:
        if _dir_is_empty(src_dir):
            os.rmdir(src_dir)
    except Exception:
        pass
    return moved


_EPUB_NOTE_LABELS = {
    "source_epub": {"en": "Source EPUB", "zh-CN": "来源 EPUB"},
    "output_dir": {"en": "Output directory", "zh-CN": "输出目录"},
    "contents": {"en": "Contents", "zh-CN": "目录"},
    "sections": {"en": "Sections", "zh-CN": "Sections"},
    "part": {"en": "Part", "zh-CN": "部分"},
}


def _epub_note_label(locale: str, key: str) -> str:
    return i18n_text(locale, _EPUB_NOTE_LABELS.get(key), key)


def nisb_epub_convert_to_note(
    epub_path: Union[str, Dict[str, Any]],
    uid: str = "",
    workspace_id: str = "",
    output_md_path: str = "",
    image_dirname: str = "images",
    overwrite: bool = False,
    max_seconds: int = 1800,
    split_mode: str = "auto",               # auto | single | split
    split_threshold_lines: int = 20000,     # auto switches to split after this many lines.
    target_lines_per_part: int = 10000,     # split target lines per part.
    md_part_max_lines: int = 2000,          # hard line cap target for each Markdown part.
    locale: str = "en"                      # UI locale for generated note wrapper text.
) -> Dict[str, Any]:
    """
    Convert an EPUB into Markdown plus extracted images.

    md_part_max_lines behavior:
    - Split output tries to keep each part below this line cap.
    - Very large single sections may exceed the cap when they cannot be split safely.
    - auto/single switches to split when accumulated lines exceed the effective threshold.
    - When switching, extracted images are migrated and buffered Markdown image URLs are rewritten.
    """
    t0 = time.time()
    try:
        # MCP dict args (snake_case only)
        if isinstance(epub_path, dict):
            args = epub_path
            epub_path = args.get("epub_path") or ""
            uid = args.get("uid") or uid or ""
            workspace_id = args.get("workspace_id") or workspace_id or ""
            output_md_path = args.get("output_md_path") or output_md_path or ""
            image_dirname = args.get("image_dirname") or image_dirname or "images"
            overwrite = bool(args.get("overwrite", overwrite))
            split_mode = str(args.get("split_mode") or split_mode or "auto").strip()
            locale = args.get("locale", args.get("ui_locale", args.get("language", locale))) or locale
            try:
                if "max_seconds" in args:
                    max_seconds = int(args.get("max_seconds"))
            except Exception:
                pass
            try:
                if "split_threshold_lines" in args:
                    split_threshold_lines = int(args.get("split_threshold_lines"))
            except Exception:
                pass
            try:
                if "target_lines_per_part" in args:
                    target_lines_per_part = int(args.get("target_lines_per_part"))
            except Exception:
                pass
            try:
                if "md_part_max_lines" in args:
                    md_part_max_lines = int(args.get("md_part_max_lines"))
            except Exception:
                pass

        uid = _safe_uid(uid)
        locale = normalize_backend_locale(locale)


        rel_epub = _safe_rel_path(str(epub_path or ""))
        abs_epub = _resolve_under_user(uid, rel_epub)

        if not os.path.exists(abs_epub) or not os.path.isfile(abs_epub):
            return {"success": False, "message": f"EPUB not found: {rel_epub}", "uid": uid, "epub_path": rel_epub}

        if not abs_epub.lower().endswith(".epub"):
            return {"success": False, "message": "Input is not .epub"}

        mode = (split_mode or "auto").strip().lower()
        if mode not in ("auto", "single", "split"):
            return {"success": False, "message": "split_mode must be one of: auto|single|split"}

        if max_seconds < 60:
            max_seconds = 60

        if split_threshold_lines < 1000:
            split_threshold_lines = 1000

        if target_lines_per_part < 200:
            target_lines_per_part = 200

        if md_part_max_lines < 200:
            md_part_max_lines = 200

        # Hard cap.
        effective_target_lines = min(int(target_lines_per_part), int(md_part_max_lines))
        effective_switch_threshold = min(int(split_threshold_lines), int(md_part_max_lines))

        # Default output Markdown path for single mode.
        rel_md = str(output_md_path or "").strip()
        if rel_md:
            rel_md = _safe_rel_path(rel_md)
        else:
            d = os.path.dirname(rel_epub)
            base = os.path.basename(rel_epub)
            stem0 = re.sub(r"\.epub$", "", base, flags=re.I)
            rel_md = (d + "/" if d else "") + f"{stem0}.md"

        abs_md = _resolve_under_user(uid, rel_md)
        stem = os.path.splitext(os.path.basename(rel_md))[0]
        img_dir_rel_single = os.path.join(os.path.dirname(rel_md), f"{stem}_{image_dirname}").replace("\\", "/").strip("/")
        abs_img_dir_single = _resolve_under_user(uid, img_dir_rel_single)

        # Split outputs are based on the EPUB filename, not the Markdown filename.
        epub_dir_rel = os.path.dirname(rel_epub).replace("\\", "/").strip("/")
        epub_stem = os.path.basename(rel_epub).rsplit(".", 1)[0]

        base_dir_rel = f"{epub_dir_rel}/{epub_stem}_md" if epub_dir_rel else f"{epub_stem}_md"
        index_md_rel = f"{base_dir_rel}/index.md"

        abs_base_dir = _resolve_under_user(uid, base_dir_rel)
        abs_index = _resolve_under_user(uid, index_md_rel)
        abs_parts_dir = _resolve_under_user(uid, f"{base_dir_rel}/parts")
        images_rel_split = f"{base_dir_rel}/images"
        abs_images_split = _resolve_under_user(uid, images_rel_split)
        manifest_path = _resolve_under_user(uid, f"{base_dir_rel}/.nisb_epub_convert_manifest.json")

        def _check_overwrite_split_target() -> Union[None, Dict[str, Any]]:
            if os.path.exists(abs_base_dir) and not overwrite:
                return {
                    "success": False,
                    "message": f"Target directory exists (overwrite=false): {base_dir_rel}",
                    "index_md_path": index_md_rel,
                    "mode": "split"
                }
            if os.path.exists(abs_base_dir) and overwrite:
                ok = False
                if os.path.exists(manifest_path):
                    m = _read_json_safe(manifest_path)
                    if str(m.get("epub_path") or "") == rel_epub:
                        ok = True
                if not ok:
                    if _dir_is_empty(abs_base_dir) or _looks_like_nisb_convert_dir(abs_base_dir):
                        ok = True
                if not ok:
                    return {
                        "success": False,
                        "message": "Refuse to overwrite: manifest missing or not match epub_path.",
                        "target_dir": base_dir_rel,
                        "manifest_path": f"{base_dir_rel}/.nisb_epub_convert_manifest.json"
                    }
                shutil.rmtree(abs_base_dir, ignore_errors=True)
            return None

        def _prepare_split_dirs_and_index() -> None:
            os.makedirs(abs_parts_dir, exist_ok=True)
            os.makedirs(abs_images_split, exist_ok=True)
            _atomic_write_json(manifest_path, {
                "epub_path": rel_epub,
                "uid": uid,
                "created_at": int(time.time()),
                "base_dir": base_dir_rel,
                "index_md_path": index_md_rel,
                "md_part_max_lines": int(md_part_max_lines),
            })
            idx_lines = []
            idx_lines.append(f"# {epub_stem}")
            idx_lines.append("")
            idx_lines.append(f"> {_epub_note_label(locale, 'source_epub')}: {rel_epub}")
            idx_lines.append(f"> {_epub_note_label(locale, 'output_dir')}: {base_dir_rel}")
            idx_lines.append(f"> md_part_max_lines: {int(md_part_max_lines)}")
            idx_lines.append("")
            idx_lines.append(f"## {_epub_note_label(locale, 'contents')}")
            idx_lines.append("")
            _atomic_write_text(abs_index, "\n".join(idx_lines) + "\n")

        # --- pre-check targets (do NOT create dirs on refuse) ---
        if mode == "split":
            refuse = _check_overwrite_split_target()
            if refuse:
                return refuse
        else:
            if os.path.exists(abs_md) and not overwrite:
                return {"success": False, "message": f"Target markdown exists (overwrite=false): {rel_md}"}
            if os.path.exists(abs_img_dir_single) and not overwrite:
                return {"success": False, "message": f"Target images dir exists (overwrite=false): {img_dir_rel_single}"}

        # --- prepare output dirs/files ---
        if mode == "split":
            _prepare_split_dirs_and_index()
        else:
            _ensure_parent_dir(abs_md)
            if overwrite and os.path.exists(abs_img_dir_single):
                shutil.rmtree(abs_img_dir_single, ignore_errors=True)
            os.makedirs(abs_img_dir_single, exist_ok=True)

        # ---- stats for debugging and manifest ----
        img_refs_total = 0
        img_saved_total = 0
        img_failed_total = 0
        img_failed_samples: List[str] = []

        # --- convert ---
        with zipfile.ZipFile(abs_epub, "r") as zf:
            zf_names = zf.namelist()
            zf_name_map = {}
            try:
                for n in zf_names:
                    ln = str(n).lower()
                    if ln not in zf_name_map:
                        zf_name_map[ln] = n
            except Exception:
                zf_name_map = {}

            opf_path = _parse_container_rootfile(zf)
            opf_dir = os.path.dirname(opf_path).replace("\\", "/")

            manifest, spine = _parse_opf(zf, opf_path)

            html_items: List[str] = []
            for idref in spine:
                it = manifest.get(idref)
                if not it:
                    continue
                href = it.get("href") or ""
                mt = (it.get("media_type") or "").lower()
                if mt and ("html" not in mt and "xhtml" not in mt):
                    continue
                html_items.append(_norm_epub_href(opf_dir, href))

            if not html_items:
                for it in manifest.values():
                    href = it.get("href") or ""
                    mt = (it.get("media_type") or "").lower()
                    if "html" in mt or "xhtml" in mt:
                        html_items.append(_norm_epub_href(opf_dir, href))

            if not html_items:
                return {"success": False, "message": "No HTML/XHTML items found in EPUB."}

            img_map: Dict[str, str] = {}  # zip_entry_name -> saved_filename

            def _try_read_zip_bytes(zip_name: str) -> bytes:
                if not zip_name:
                    raise KeyError("empty zip_name")
                try:
                    return zf.read(zip_name)
                except Exception:
                    alt = zf_name_map.get(str(zip_name).lower())
                    if alt:
                        return zf.read(alt)
                    raise

            def extract_image_by_href(href: str, abs_img_dir: str, base_dir_in_epub: str) -> str:
                """
                Resolve href against:
                  1) current html dir
                  2) opf_dir
                  3) container root
                then extract from zip to abs_img_dir.
                """
                nonlocal img_saved_total, img_failed_total, img_failed_samples

                raw = unquote(str(href or "")).replace("\\", "/").strip()
                if not raw:
                    return ""

                candidates: List[str] = []
                c1 = _norm_epub_href(base_dir_in_epub, raw)
                if c1:
                    candidates.append(c1)
                c2 = _norm_epub_href(opf_dir, raw)
                if c2 and c2 not in candidates:
                    candidates.append(c2)
                c3 = _norm_epub_href("", raw)
                if c3 and c3 not in candidates:
                    candidates.append(c3)

                if not candidates:
                    return ""

                found_name = ""
                data = b""
                for cand in candidates:
                    try:
                        data = _try_read_zip_bytes(cand)
                        found_name = zf_name_map.get(cand.lower(), cand) if zf_name_map else cand
                        break
                    except Exception:
                        continue

                if not found_name or not data:
                    img_failed_total += 1
                    if len(img_failed_samples) < 30:
                        img_failed_samples.append(raw)
                    return ""

                if found_name in img_map:
                    return img_map[found_name]

                fn = _slug_filename(found_name, default="image")
                if "." not in fn:
                    fn += ".bin"

                h = hashlib.sha1(data).hexdigest()[:10]
                name0, ext0 = os.path.splitext(fn)
                saved = f"{name0}_{h}{ext0}"

                out_path = os.path.join(abs_img_dir, saved)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "wb") as f:
                    f.write(data)

                img_map[found_name] = saved
                img_saved_total += 1
                return saved

            def make_img_resolver(abs_img_dir: str, img_dir_rel: str, base_dir_in_epub: str):
                def img_resolver(src: str, alt: str) -> str:
                    nonlocal img_refs_total
                    img_refs_total += 1

                    saved = extract_image_by_href(src, abs_img_dir=abs_img_dir, base_dir_in_epub=base_dir_in_epub)
                    if not saved:
                        return ""

                    alt_s = str(alt or "").strip().replace("[", "\\[").replace("]", "\\]")
                    img_rel_path = (str(img_dir_rel).rstrip("/") + "/" + saved).replace("\\", "/").lstrip("/")
                    url = "nisb://file?path=" + quote(img_rel_path, safe="")
                    return f"![{alt_s}]({url})"
                return img_resolver

            # Single-mode buffered sections, used if auto switches to split.
            single_header = []
            single_header.append("<!-- generated_by: nisb_epub_convert_to_note -->")
            single_header.append(f"<!-- source_epub: {rel_epub} -->")
            single_header.append(f"<!-- generated_at: {_now_iso()} -->")
            single_header.append("")
            single_header_text = "\n".join(single_header) + "\n"

            buffered_sections: List[Tuple[int, str]] = []  # (section_idx, md)
            total_lines_seen = 0

            # Split part state.
            part_seq = 0
            part_start_i = 0
            part_lines = 0
            current_part_abs = ""
            current_part_rel = ""

            split_ready = (mode == "split")

            def start_new_part(start_i: int) -> None:
                nonlocal part_seq, part_start_i, part_lines, current_part_abs, current_part_rel
                part_seq += 1
                part_start_i = start_i
                part_lines = 0
                tmp_tag = f"tmp_{part_seq:04d}"
                current_part_rel = f"{base_dir_rel}/parts/part_{tmp_tag}.md"
                current_part_abs = _resolve_under_user(uid, current_part_rel)

                header = []
                header.append(f"# {epub_stem} · {_epub_note_label(locale, 'part')} {part_seq}")
                header.append("")
                header.append(f"> {_epub_note_label(locale, 'source_epub')}: {rel_epub}")
                header.append(f"> {_epub_note_label(locale, 'sections')}: {start_i + 1}-{start_i + 1} / {len(html_items)}")
                header.append(f"> md_part_max_lines: {int(md_part_max_lines)}")
                header.append("")
                header.append("---")
                header.append("")
                _atomic_write_text(current_part_abs, "\n".join(header) + "\n")
                part_lines = _count_lines("\n".join(header) + "\n")

            def close_part(end_i: int) -> str:
                nonlocal current_part_abs, current_part_rel, part_start_i
                if not current_part_abs:
                    return ""
                tag = f"c{(part_start_i + 1):04d}_{(end_i + 1):04d}"
                final_rel = f"{base_dir_rel}/parts/part_{tag}.md"
                final_abs = _resolve_under_user(uid, final_rel)
                try:
                    if os.path.exists(final_abs):
                        os.remove(final_abs)
                except Exception:
                    pass
                try:
                    os.replace(current_part_abs, final_abs)
                except Exception:
                    try:
                        with open(current_part_abs, "r", encoding="utf-8") as f:
                            txt = f.read()
                        _atomic_write_text(final_abs, txt)
                        os.remove(current_part_abs)
                    except Exception:
                        pass

                current_part_abs = final_abs
                current_part_rel = final_rel
                return final_rel

            def append_index_link_for_part(start_i: int, end_i: int, part_rel: str) -> None:
                link = _to_nisb_file_link(part_rel, workspace_id)
                _append_text(abs_index, f"- [c{(start_i + 1):04d}_{(end_i + 1):04d}]({link})\n")

            def ensure_split_ready(overwrite_check: bool = True) -> Union[None, Dict[str, Any]]:
                nonlocal split_ready
                if split_ready:
                    return None
                if overwrite_check:
                    refuse = _check_overwrite_split_target()
                    if refuse:
                        return refuse
                _prepare_split_dirs_and_index()
                start_new_part(0)
                split_ready = True
                return None

            def _rewrite_img_prefix(md_text: str, old_img_dir_rel: str, new_img_dir_rel: str) -> str:
                if not md_text:
                    return md_text
                old_prefix = "nisb://file?path=" + quote((old_img_dir_rel.rstrip("/") + "/"), safe="")
                new_prefix = "nisb://file?path=" + quote((new_img_dir_rel.rstrip("/") + "/"), safe="")
                return md_text.replace(old_prefix, new_prefix)

            def append_section_to_split(section_i: int, md_text: str, is_last: bool) -> Union[None, Dict[str, Any]]:
                nonlocal part_lines, part_start_i

                if not split_ready:
                    refuse = ensure_split_ready(overwrite_check=True)
                    if refuse:
                        return refuse

                md_text = (md_text or "").strip()
                if not md_text:
                    return None

                md_lines = _count_lines(md_text + "\n")
                sep_text = "\n\n---\n\n"
                sep_lines = _count_lines(sep_text)

                # Hard cap: if adding this section would exceed md_part_max_lines, close current part first
                if current_part_abs and part_lines > 0:
                    projected = part_lines + sep_lines + md_lines
                    if projected > int(md_part_max_lines) and section_i > part_start_i:
                        part_rel = close_part(section_i - 1)
                        if part_rel:
                            append_index_link_for_part(part_start_i, section_i - 1, part_rel)
                        start_new_part(section_i)

                # Append with separator if not beginning
                if current_part_abs and part_lines > 0:
                    _append_text(current_part_abs, sep_text)
                    part_lines += sep_lines

                _append_text(current_part_abs, md_text + "\n")
                part_lines += md_lines

                # Soft target close (still capped by md_part_max_lines)
                if (not is_last) and part_lines >= int(effective_target_lines) and section_i >= part_start_i:
                    part_rel = close_part(section_i)
                    if part_rel:
                        append_index_link_for_part(part_start_i, section_i, part_rel)
                    start_new_part(section_i + 1)

                return None

            # Open the first part when split mode is requested initially.
            if mode == "split":
                start_new_part(0)

            switched_to_split = False

            for idx, hp in enumerate(html_items):
                if max_seconds and (time.time() - t0) > max_seconds:
                    return {"success": False, "message": f"Timeout (max_seconds={max_seconds})"}

                try:
                    html = _read_zip_text(zf, hp)
                except Exception:
                    continue

                html_dir_in_epub = os.path.dirname(hp).replace("\\", "/").strip("/")

                # Resolver based on the current output mode.
                if mode == "split":
                    img_resolver = make_img_resolver(abs_images_split, images_rel_split, base_dir_in_epub=html_dir_in_epub)
                else:
                    img_resolver = make_img_resolver(abs_img_dir_single, img_dir_rel_single, base_dir_in_epub=html_dir_in_epub)

                parser = _HtmlToMd(img_resolver=img_resolver)
                try:
                    parser.feed(html)
                except Exception:
                    pass

                md = (parser.get_markdown() or "").strip()
                if not md:
                    continue

                md_lines = _count_lines(md + "\n")
                total_lines_seen += md_lines

                # Decide if we must switch to split due to unified max lines
                if (mode in ("auto", "single")) and (not switched_to_split) and total_lines_seen > int(effective_switch_threshold):
                    # Switch to split mode.
                    refuse = ensure_split_ready(overwrite_check=True)
                    if refuse:
                        return refuse

                    # Migrate images and rewrite buffered Markdown image prefixes.
                    _migrate_dir_files(abs_img_dir_single, abs_images_split)
                    buffered_sections = [(si, _rewrite_img_prefix(txt, img_dir_rel_single, images_rel_split)) for si, txt in buffered_sections]

                    # All following images go to the split images directory.
                    mode = "split"
                    switched_to_split = True

                    # Dump buffered sections into split parts with the line cap.
                    for bi, bmd in buffered_sections:
                        err = append_section_to_split(bi, bmd, is_last=False)
                        if err:
                            return err
                    buffered_sections = []

                    # re-parse current html again but with split resolver to avoid mixed dirs
                    img_resolver2 = make_img_resolver(abs_images_split, images_rel_split, base_dir_in_epub=html_dir_in_epub)
                    parser2 = _HtmlToMd(img_resolver=img_resolver2)
                    try:
                        parser2.feed(html)
                    except Exception:
                        pass
                    md = (parser2.get_markdown() or "").strip()
                    if not md:
                        continue

                # Write content.
                if mode in ("auto", "single"):
                    buffered_sections.append((idx, md))
                else:
                    err = append_section_to_split(idx, md, is_last=(idx == len(html_items) - 1))
                    if err:
                        return err

        # Finalize output.
        if mode in ("auto", "single"):
            parts = [single_header_text]
            for i, (si, txt) in enumerate(buffered_sections):
                if i > 0:
                    parts.append("\n\n---\n\n")
                parts.append((txt or "").strip() + "\n")
            md_text = "".join(parts).strip() + "\n"
            _atomic_write_text(abs_md, md_text)

            images_count = 0
            try:
                images_count = len([x for x in os.listdir(abs_img_dir_single) if os.path.isfile(os.path.join(abs_img_dir_single, x))])
            except Exception:
                images_count = 0

            return {
                "success": True,
                "message": "EPUB converted (single).",
                "uid": uid,
                "md_path": rel_md,
                "images_dir": img_dir_rel_single,
                "images_count": images_count,
                "mode": "single",
                "md_part_max_lines": int(md_part_max_lines),
                "img_refs_total": int(img_refs_total),
                "img_saved_total": int(img_saved_total),
                "img_failed_total": int(img_failed_total),
                "img_failed_samples": img_failed_samples[:30],
            }

        # Finalize the last split part and ensure split output exists.
        if not split_ready:
            refuse = ensure_split_ready(overwrite_check=False)
            if refuse:
                return refuse

        last_end = len(html_items) - 1
        final_rel = close_part(last_end)
        if final_rel:
            append_index_link_for_part(part_start_i, last_end, final_rel)

        images_count = 0
        try:
            images_count = len([x for x in os.listdir(abs_images_split) if os.path.isfile(os.path.join(abs_images_split, x))])
        except Exception:
            images_count = 0

        # Update manifest for observability.
        try:
            m0 = _read_json_safe(manifest_path)
            m0["converted_at"] = int(time.time())
            m0["images_count"] = int(images_count)
            m0["img_refs_total"] = int(img_refs_total)
            m0["img_saved_total"] = int(img_saved_total)
            m0["img_failed_total"] = int(img_failed_total)
            m0["img_failed_samples"] = img_failed_samples[:30]
            _atomic_write_json(manifest_path, m0)
        except Exception:
            pass

        return {
            "success": True,
            "message": "EPUB converted (split).",
            "uid": uid,
            "index_md_path": index_md_rel,
            "base_dir": base_dir_rel,
            "parts_dir": f"{base_dir_rel}/parts",
            "images_dir": images_rel_split,
            "images_count": images_count,
            "mode": "split",
            "md_part_max_lines": int(md_part_max_lines),
            "target_lines_per_part": int(effective_target_lines),
            "switch_threshold_lines": int(effective_switch_threshold),
            "img_refs_total": int(img_refs_total),
            "img_saved_total": int(img_saved_total),
            "img_failed_total": int(img_failed_total),
            "img_failed_samples": img_failed_samples[:30],
        }

    except Exception as e:
        return {"success": False, "message": str(e)}

