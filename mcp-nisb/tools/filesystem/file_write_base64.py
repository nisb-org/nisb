import os
import re
import json
import base64
import hashlib
import tempfile
import mimetypes
from datetime import datetime
from typing import Dict, Any, Tuple

from .config import (
    get_agent_files_path,
    get_base_path,
    ensure_directories,
    detect_category,
)
from .security import validate_path_safety, validate_filename
from .backup import create_backup, should_backup
from .utils import (
    generate_file_id,
    save_metadata,
)
from tools.timeline import _append_timeline_activity


_UPLOAD_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{6,80}$")


def _atomic_write_json(path: str, data: dict) -> None:
    """
    原子写 JSON：临时文件必须与目标文件在同一文件系统（同一目录最稳），
    否则 os.replace/os.rename 会报 EXDEV / Invalid cross-device link。[web:54]
    """
    dirpath = os.path.dirname(path) or "."
    os.makedirs(dirpath, exist_ok=True)

    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=dirpath)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        fd = None
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        try:
            if fd is not None:
                os.close(fd)
        except Exception:
            pass
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _sha256_file(abs_path: str) -> str:
    h = hashlib.sha256()
    with open(abs_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _guess_mime(filename: str) -> str:
    mt, _ = mimetypes.guess_type(filename)
    return mt or "application/octet-stream"


def _resolve_file_path(
    user_id: str,
    email: str,
    name: str,
    filename: str,
    auto_categorize: bool,
) -> Tuple[str, str]:
    base_path = get_base_path(user_id, email, name)

    if filename.startswith("storage/"):
        file_path = os.path.join(base_path, filename)
        category = "storage"
        return file_path, category

    if filename.startswith("agent_files/"):
        file_path = os.path.join(base_path, filename)
        category = "agent_files"
        return file_path, category

    agent_base = get_agent_files_path(user_id, email, name)
    if auto_categorize:
        category = detect_category(filename)
        file_path = os.path.join(agent_base, category, filename)
    else:
        category = "root"
        file_path = os.path.join(agent_base, filename)

    return file_path, category


def _ensure_user(user_id: str, email: str, name: str) -> None:
    from core.storage import ensure_user_directory
    ensure_user_directory(user_id, email, name)


def _backup_if_needed(user_id: str, email: str, name: str, file_path: str, filename: str, category: str, operation: str) -> None:
    try:
        if should_backup(file_path, user_id, email, name):
            affected = [file_path] if os.path.exists(file_path) else []
            backup_result = create_backup(
                user_id,
                email,
                name,
                operation=operation,
                affected_files=affected,
                metadata={"filename": filename, "category": category},
            )
            if backup_result.get("success"):
                print(f"[BACKUP] {operation} backup_id={backup_result.get('backup_id')}")
    except Exception:
        pass


def nisb_file_write_base64(args: dict) -> Dict[str, Any]:
    user_id = "user_001"
    email = None
    name = None
    try:
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")

        _ensure_user(user_id, email, name)

        filename = args.get("filename")
        data_base64 = args.get("data_base64")
        description = args.get("description", "")
        tags = args.get("tags", [])
        overwrite = bool(args.get("overwrite", False))
        auto_categorize = bool(args.get("auto_categorize", False))

        is_valid, error_msg = validate_filename(filename)
        if not is_valid:
            return {"success": False, "message": error_msg}

        if not isinstance(data_base64, str) or not data_base64.strip():
            return {"success": False, "message": "data_base64 is required"}

        if data_base64.strip().startswith("data:"):
            return {"success": False, "message": "data_base64 must be raw base64 (no data: prefix)"}

        ensure_directories(user_id, email, name)
        file_path, category = _resolve_file_path(user_id, email, name, filename, auto_categorize)

        is_safe, error_msg, _needs_protection = validate_path_safety(file_path, user_id, email, name)
        if not is_safe:
            return {"success": False, "message": error_msg}

        if os.path.exists(file_path) and (not overwrite):
            return {"success": False, "message": f"❌ 文件已存在：{filename}（overwrite=false）"}

        _backup_if_needed(user_id, email, name, file_path, filename, category, operation="file_write_base64")

        try:
            raw = base64.b64decode(data_base64, validate=True)
        except Exception as e:
            return {"success": False, "message": f"❌ base64 解码失败：{str(e)}"}

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        tmp_path = file_path + ".tmp_write"
        with open(tmp_path, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)

        file_id = generate_file_id(filename)
        sha256 = hashlib.sha256(raw).hexdigest()
        now_iso = datetime.now().isoformat()
        meta = {
            "file_id": file_id,
            "filename": filename,
            "file_path": file_path,
            "file_type": "binary",
            "mime_type": _guess_mime(filename),
            "category": category,
            "description": description,
            "tags": tags,
            "created_at": now_iso,
            "updated_at": now_iso,
            "size_bytes": len(raw),
            "sha256": sha256,
            "analysis": {},
        }
        try:
            save_metadata(user_id, file_id, meta, email, name)
        except Exception:
            pass

        try:
            base_path = get_base_path(user_id, email, name)
            _append_timeline_activity(
                base_path=base_path,
                event={
                    "type": "document",
                    "date": now_iso,
                    "title": filename,
                    "path": filename,
                    "extra": {"action": "upload_binary", "category": category, "bytes": len(raw)},
                },
            )
        except Exception:
            pass

        return {
            "success": True,
            "message": f"✅ 二进制写入成功：{filename}（{len(raw)} bytes）",
            "file_id": file_id,
            "filename": filename,
            "file_path": file_path,
            "bytes": len(raw),
            "sha256": sha256,
            "mime": _guess_mime(filename),
        }
    except Exception as e:
        return {"success": False, "message": f"❌ 写入失败：{str(e)}"}


def nisb_file_write_base64_chunk(args: dict) -> Dict[str, Any]:
    user_id = "user_001"
    email = None
    name = None
    tmp_path = ""
    meta_path = ""
    try:
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")

        _ensure_user(user_id, email, name)

        filename = args.get("filename")
        upload_id = str(args.get("upload_id") or "").strip()
        chunk_index = int(args.get("chunk_index", 0))
        total_chunks = int(args.get("total_chunks", 1))
        data_base64 = args.get("data_base64")

        overwrite = bool(args.get("overwrite", False))
        auto_categorize = bool(args.get("auto_categorize", False))
        description = args.get("description", "")
        tags = args.get("tags", [])

        is_valid, error_msg = validate_filename(filename)
        if not is_valid:
            return {"success": False, "message": error_msg}

        if not upload_id or not _UPLOAD_ID_RE.fullmatch(upload_id):
            return {"success": False, "message": "upload_id is invalid"}

        if chunk_index < 0 or total_chunks <= 0 or chunk_index >= total_chunks:
            return {"success": False, "message": "chunk_index/total_chunks is invalid"}

        if not isinstance(data_base64, str) or not data_base64.strip():
            return {"success": False, "message": "data_base64 is required"}

        if data_base64.strip().startswith("data:"):
            return {"success": False, "message": "data_base64 must be raw base64 (no data: prefix)"}

        ensure_directories(user_id, email, name)
        file_path, category = _resolve_file_path(user_id, email, name, filename, auto_categorize)

        is_safe, error_msg, _needs_protection = validate_path_safety(file_path, user_id, email, name)
        if not is_safe:
            return {"success": False, "message": error_msg}

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        tmp_path = file_path + f".uploading_{upload_id}"
        meta_path = tmp_path + ".json"

        if chunk_index == 0:
            if os.path.exists(file_path) and (not overwrite):
                return {"success": False, "message": f"❌ 文件已存在：{filename}（overwrite=false）"}

            if os.path.exists(file_path) and overwrite:
                _backup_if_needed(user_id, email, name, file_path, filename, category, operation="file_write_base64_chunk_overwrite")

            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            try:
                if os.path.exists(meta_path):
                    os.remove(meta_path)
            except Exception:
                pass

            with open(tmp_path, "wb") as f:
                f.write(b"")

            _atomic_write_json(
                meta_path,
                {
                    "filename": filename,
                    "category": category,
                    "upload_id": upload_id,
                    "total_chunks": total_chunks,
                    "next_chunk": 0,
                    "created_at": datetime.now().isoformat(),
                },
            )

        if not os.path.exists(tmp_path) or not os.path.exists(meta_path):
            return {"success": False, "message": "❌ 未找到上传会话（请从 chunk_index=0 重新开始）"}

        try:
            meta = json.load(open(meta_path, "r", encoding="utf-8"))
        except Exception:
            return {"success": False, "message": "❌ 上传会话损坏（meta 读取失败）"}

        expected = int(meta.get("next_chunk", 0))
        meta_total = int(meta.get("total_chunks", total_chunks))
        if meta_total != total_chunks:
            return {"success": False, "message": "❌ total_chunks 不一致（请重新开始）"}
        if chunk_index != expected:
            return {"success": False, "message": f"❌ chunk 顺序错误：expected={expected}, got={chunk_index}"}

        try:
            raw = base64.b64decode(data_base64, validate=True)
        except Exception as e:
            return {"success": False, "message": f"❌ base64 解码失败：{str(e)}"}

        with open(tmp_path, "ab") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())

        meta["next_chunk"] = expected + 1
        _atomic_write_json(meta_path, meta)

        if meta["next_chunk"] < total_chunks:
            return {
                "success": True,
                "status": "partial",
                "message": f"✅ chunk {chunk_index + 1}/{total_chunks} received",
                "filename": filename,
                "file_path": file_path,
                "upload_id": upload_id,
                "next_chunk": meta["next_chunk"],
            }

        os.replace(tmp_path, file_path)
        try:
            os.remove(meta_path)
        except Exception:
            pass

        file_id = generate_file_id(filename)
        sha256 = _sha256_file(file_path)
        size = int(os.path.getsize(file_path))
        now_iso = datetime.now().isoformat()
        meta2 = {
            "file_id": file_id,
            "filename": filename,
            "file_path": file_path,
            "file_type": "binary",
            "mime_type": _guess_mime(filename),
            "category": category,
            "description": description,
            "tags": tags,
            "created_at": now_iso,
            "updated_at": now_iso,
            "size_bytes": size,
            "sha256": sha256,
            "analysis": {},
        }
        try:
            save_metadata(user_id, file_id, meta2, email, name)
        except Exception:
            pass

        try:
            base_path = get_base_path(user_id, email, name)
            _append_timeline_activity(
                base_path=base_path,
                event={
                    "type": "document",
                    "date": now_iso,
                    "title": filename,
                    "path": filename,
                    "extra": {"action": "upload_binary_chunked", "category": category, "bytes": size},
                },
            )
        except Exception:
            pass

        return {
            "success": True,
            "status": "final",
            "message": f"✅ 分片上传完成：{filename}（{size} bytes）",
            "file_id": file_id,
            "filename": filename,
            "file_path": file_path,
            "bytes": size,
            "sha256": sha256,
            "mime": _guess_mime(filename),
        }
    except Exception as e:
        # 若在 chunk_index==0 早期失败，尽量清理残留 uploading 文件，避免目录里挂垃圾
        try:
            if tmp_path and os.path.exists(tmp_path) and os.path.getsize(tmp_path) == 0:
                os.remove(tmp_path)
        except Exception:
            pass
        try:
            if meta_path and os.path.exists(meta_path):
                os.remove(meta_path)
        except Exception:
            pass
        return {"success": False, "message": f"❌ 分片写入失败：{str(e)}"}

