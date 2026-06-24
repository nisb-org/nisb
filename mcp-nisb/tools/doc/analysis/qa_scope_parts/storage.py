from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from tools.doc.analysis import doc_qa as dq  # type: ignore
from .common import clean_id


QA_JSONL = "qa.jsonl"
QA_MANIFEST_JSON = "qa_manifest.json"
QA_TOMBSTONES_JSONL = "qa_tombstones.jsonl"
QA_SEG_PREFIX = "qa_"
QA_SEG_EXT = ".jsonl"

QA_SEG_ROTATE_BYTES = int(os.getenv("NISB_QA_SEG_ROTATE_BYTES", str(8 * 1024 * 1024)))
QA_LIST_MAX_SEGMENTS = 12
QA_FIND_MAX_SEGMENTS = 60


def store_scope_from_args(args: Dict[str, Any]) -> str:
    s = clean_id(
        args.get("store_scope")
        or args.get("storeScope")
        or args.get("scope_store")
        or args.get("scope")
        or "doc"
    ).lower()

    if s not in ("doc", "library", "global"):
        s = "doc"
    return s


def evidence_scope_from_args(args: Dict[str, Any], *, fallback: str) -> str:
    s = clean_id(args.get("evidence_scope") or args.get("evidenceScope") or "").lower()
    if not s:
        s = fallback
    if s not in ("doc", "library", "global"):
        s = fallback
    return s


def resolve_store_dir(
    args: Dict[str, Any],
    *,
    store_scope: str,
    library_id: Optional[str],
    doc_id: Optional[str],
) -> Tuple[Path, Dict[str, Any]]:
    user_base = dq._resolve_user_base(args)

    dbg: Dict[str, Any] = {
        "store_scope": store_scope,
        "user_base": str(user_base),
        "library_id": library_id,
        "doc_id": doc_id,
    }

    if store_scope == "doc":
        if not library_id or not doc_id:
            p = user_base / "libraries" / (library_id or "_") / "docs" / (doc_id or "_")
            dbg["picked"] = str(p)
            return p, dbg

        doc_dir, dbg2 = dq._resolve_doc_dir(args, library_id=library_id, doc_id=doc_id)
        dbg.update({
            "picked": str(doc_dir),
            "doc_dir_dbg": dbg2,
        })
        return doc_dir, dbg

    if store_scope == "library":
        if not library_id:
            p = user_base / "libraries" / "_"
            dbg["picked"] = str(p)
            return p, dbg

        p = user_base / "libraries" / library_id
        dbg["picked"] = str(p)
        return p, dbg

    p = user_base / "cross_library"
    dbg["picked"] = str(p)
    return p, dbg


def qa_path_for_doc(store_dir: Path) -> Path:
    return store_dir / "analysis" / QA_JSONL


def analysis_dir(store_dir: Path) -> Path:
    return store_dir / "analysis"


def manifest_path(store_dir: Path) -> Path:
    return analysis_dir(store_dir) / QA_MANIFEST_JSON


def tombstones_path(store_dir: Path) -> Path:
    return analysis_dir(store_dir) / QA_TOMBSTONES_JSONL


def ensure_analysis_dir(store_dir: Path) -> None:
    analysis_dir(store_dir).mkdir(parents=True, exist_ok=True)


def load_manifest(store_dir: Path) -> Dict[str, Any]:
    mp = manifest_path(store_dir)
    if not mp.exists():
        return {
            "version": 1,
            "rotate_bytes": QA_SEG_ROTATE_BYTES,
            "active": None,
            "segments": [],
        }

    try:
        obj = json.loads(mp.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    return {
        "version": 1,
        "rotate_bytes": QA_SEG_ROTATE_BYTES,
        "active": None,
        "segments": [],
        "corrupted_manifest": True,
    }


def save_manifest(store_dir: Path, manifest: Dict[str, Any]) -> None:
    ensure_analysis_dir(store_dir)
    mp = manifest_path(store_dir)
    tmp = mp.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(mp))


def segment_filename(idx: int) -> str:
    return f"{QA_SEG_PREFIX}{idx:06d}{QA_SEG_EXT}"


def list_existing_segments_from_disk(store_dir: Path) -> List[str]:
    ad = analysis_dir(store_dir)
    if not ad.exists():
        return []

    out: List[str] = []
    for p in ad.iterdir():
        if not p.is_file():
            continue
        if p.name.startswith(QA_SEG_PREFIX) and p.name.endswith(QA_SEG_EXT):
            out.append(p.name)

    out.sort()
    return out


def maybe_bootstrap_manifest(store_dir: Path) -> Dict[str, Any]:
    ensure_analysis_dir(store_dir)
    manifest = load_manifest(store_dir)

    if manifest.get("segments") and manifest.get("active"):
        return manifest

    segments: List[Dict[str, Any]] = []
    active: Optional[str] = None

    legacy = analysis_dir(store_dir) / QA_JSONL
    if legacy.exists():
        segments.append({
            "file": QA_JSONL,
            "kind": "legacy_single",
            "bytes": legacy.stat().st_size,
        })

    disk_segs = list_existing_segments_from_disk(store_dir)
    for fn in disk_segs:
        p = analysis_dir(store_dir) / fn
        segments.append({
            "file": fn,
            "kind": "segment",
            "bytes": p.stat().st_size,
        })

    if disk_segs:
        active = disk_segs[-1]
    else:
        active = segment_filename(1)
        p = analysis_dir(store_dir) / active
        if not p.exists():
            p.write_text("", encoding="utf-8")
        segments.append({
            "file": active,
            "kind": "segment",
            "bytes": p.stat().st_size,
        })

    manifest = {
        "version": 1,
        "rotate_bytes": int(manifest.get("rotate_bytes") or QA_SEG_ROTATE_BYTES),
        "active": active,
        "segments": segments,
    }
    save_manifest(store_dir, manifest)
    return manifest


def rotate_if_needed(store_dir: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    rotate_bytes = int(manifest.get("rotate_bytes") or QA_SEG_ROTATE_BYTES)
    active = str(manifest.get("active") or "").strip()

    if not active:
        return maybe_bootstrap_manifest(store_dir)

    ap = analysis_dir(store_dir) / active
    if ap.exists() and ap.stat().st_size < rotate_bytes:
        return manifest

    max_idx = 0
    for seg in (manifest.get("segments") or []):
        fn = str(seg.get("file") or "")
        if fn.startswith(QA_SEG_PREFIX) and fn.endswith(QA_SEG_EXT):
            mid = fn[len(QA_SEG_PREFIX):-len(QA_SEG_EXT)]
            try:
                max_idx = max(max_idx, int(mid))
            except Exception:
                pass

    next_fn = segment_filename(max_idx + 1 if max_idx > 0 else 1)
    next_path = analysis_dir(store_dir) / next_fn
    if not next_path.exists():
        next_path.write_text("", encoding="utf-8")

    segs = list(manifest.get("segments") or [])
    segs.append({
        "file": next_fn,
        "kind": "segment",
        "bytes": next_path.stat().st_size,
    })

    manifest2 = {
        **manifest,
        "active": next_fn,
        "segments": segs,
    }
    save_manifest(store_dir, manifest2)
    return manifest2


def append_jsonl_segmented(store_dir: Path, rec: Dict[str, Any]) -> Tuple[Path, Dict[str, Any]]:
    manifest = maybe_bootstrap_manifest(store_dir)
    manifest = rotate_if_needed(store_dir, manifest)

    active = str(manifest.get("active") or "").strip()
    if not active:
        active = segment_filename(1)
        manifest["active"] = active

    fp = analysis_dir(store_dir) / active
    ensure_analysis_dir(store_dir)

    line = json.dumps(rec, ensure_ascii=False) + "\n"
    with fp.open("a", encoding="utf-8") as f:
        f.write(line)

    try:
        sz = fp.stat().st_size
    except Exception:
        sz = None

    segs: List[Dict[str, Any]] = []
    for seg in (manifest.get("segments") or []):
        if str(seg.get("file") or "") == fp.name:
            seg2 = dict(seg)
            if sz is not None:
                seg2["bytes"] = int(sz)
            segs.append(seg2)
        else:
            segs.append(seg)

    manifest2 = {
        **manifest,
        "segments": segs,
    }
    save_manifest(store_dir, manifest2)

    dbg = {
        "manifest": str(manifest_path(store_dir)),
        "active_segment": fp.name,
        "active_bytes": sz,
    }
    return fp, dbg


def read_jsonl_lines(path: Path, max_rows: int) -> List[dict]:
    return dq._safe_read_jsonl(path, max_rows=max_rows)


def list_segment_files_for_read(store_dir: Path, max_segments: int) -> List[Path]:
    manifest = maybe_bootstrap_manifest(store_dir)
    seg_entries = list(manifest.get("segments") or [])
    seg_entries.sort(key=lambda x: str(x.get("file") or ""))

    tail = seg_entries[-max_segments:] if max_segments > 0 else seg_entries

    out: List[Path] = []
    for seg in tail:
        fn = str(seg.get("file") or "")
        if not fn:
            continue
        p = analysis_dir(store_dir) / fn
        if p.exists():
            out.append(p)
    return out


def load_deleted_set_fast(store_dir: Path, max_rows: int = 200000) -> Set[str]:
    tp = tombstones_path(store_dir)
    if not tp.exists():
        return set()

    rows = dq._safe_read_jsonl(tp, max_rows=max_rows)
    out: Set[str] = set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        qa_id = clean_id(r.get("target_qa_id") or r.get("qa_id"))
        if qa_id:
            out.add(qa_id)
    return out


def delete_tombstone_append(store_dir: Path, ev: Dict[str, Any]) -> None:
    ensure_analysis_dir(store_dir)
    tp = tombstones_path(store_dir)
    dq._append_jsonl(tp, ev)


def find_qa_anywhere_segmented(store_dir: Path, qa_id: str) -> Optional[dict]:
    qa_id = clean_id(qa_id)
    if not qa_id:
        return None

    seg_paths = list_segment_files_for_read(store_dir, max_segments=QA_FIND_MAX_SEGMENTS)
    for p in reversed(seg_paths):
        try:
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    if str(obj.get("type") or "") != "qa":
                        continue
                    if clean_id(obj.get("qa_id")) == qa_id:
                        return obj
        except Exception:
            continue

    return None

