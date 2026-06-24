#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hebbian Learning Pipeline (Filesystem/Note) - Production Ready

与 tools/chat/hebbian.py 保持统一架构：
- 调用 core.hebbian_pipeline.process_text_event（统一入口）
- 支持任意长度文档（智能分段）
- 完善的错误处理和用户反馈

对外接口：
    nisb_note_to_brain(args) -> dict
    nisb_batch_notes_to_brain(args) -> dict
"""

import sys
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, '/srv')


def nisb_note_to_brain(args: dict) -> Dict[str, Any]:
    """MCP 工具：单个笔记进脑（生产级）"""
    filename: str | None = None
    try:
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        filename = args.get("filename")
        concept_language = args.get("concept_language", "auto")
        concept_backend = args.get("concept_backend", "llm_gpt4o_mini")
        
        if not filename:
            return {"success": False, "message": "❌ 必须提供 filename"}
        
        from .config import get_base_path
        base_path = get_base_path(user_id, email, name)
        file_path = Path(base_path) / filename
        
        if not file_path.exists():
            return {"success": False, "message": f"❌ 文件不存在：{filename}"}
        
        # ⭐ 读取文件（强制 UTF-8）
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError as e:
            return {
                "success": False,
                "message": (
                    "❌ 文件编码错误（请确保是 UTF-8）\n\n"
                    f"📁 {filename}\n\n"
                    f"详情：{e}"
                )
            }
        
        if not content.strip():
            return {"success": False, "message": f"❌ 笔记内容为空：{filename}"}
        
        # ⭐ 调用统一入口
        from core.hebbian_pipeline import process_text_event

        result = process_text_event(
            base_path=base_path,
            source_type="note",
            source_id=filename,
            text=content,
            concept_language=concept_language,
            concept_backend=concept_backend,
            top_k=15,
        )

        # ⭐⭐⭐ 关键修复：
        #   - result 为 None：Hebbian 管道早退（无概念 / 无共现）→ 视为失败
        #   - result 为 dict 且 concepts > 0：视为成功（即使 created=0，概念早已存在）
        if not result or result.get("concepts", 0) <= 0:
            return {
                "success": False,
                "message": (
                    "❌ 概念提取失败（可能是 LLM 超时或文本格式异常）\n\n"
                    f"📁 {filename}\n"
                    f"📊 文件大小：{len(content)} 字符\n\n"
                    "💡 建议：\n"
                    "1. 检查文件编码是否为 UTF-8\n"
                    "2. 尝试缩短文件长度（< 50KB）\n"
                    "3. 查看后端日志排查详细错误\n"
                    "4. 使用批量进脑工具（自动跳过失败文件）"
                ),
                "stats": {
                    "concepts": 0,
                    "source_id": filename,
                    "file_size": len(content)
                }
            }

        # ✅ 真正成功：只要 concepts > 0，就算本次“进脑成功”
        concepts_count = result.get("concepts", 0)
        pairs_count = result.get("pairs", 0)
        created_count = result.get("created", 0)
        skipped_count = result.get("skipped", 0)

        # 文案上区分三种情况，但都算 success：
        # 1) 第一次进脑：created>0, skipped≈0
        # 2) 重复进脑：created=0, skipped>0
        # 3) 混合：两者都有
        message_lines = [
            "✅ 笔记已进脑",
            "",
            f"📁 {filename}",
            f"🧠 提取了 {concepts_count} 个概念",
            f"🔗 检测到 {pairs_count} 对共现关系",
        ]
        if created_count > 0:
            message_lines.append(f"➕ 新建了 {created_count} 条突触连接")
        if skipped_count > 0:
            message_lines.append(f"♻️ 更新了 {skipped_count} 条已有连接权重")
        message_lines.append("")
        message_lines.append("💡 使用图谱工具查看关系网络")

        return {
            "success": True,
            "message": "\n".join(message_lines),
            "stats": {
                "concepts": concepts_count,
                "pairs": pairs_count,
                "created": created_count,
                "skipped": skipped_count,
                "source_id": filename,
                "file_size": len(content)
            }
        }
    
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"[ERROR note_to_brain] {filename}: {err_msg}", file=sys.stderr)
        return {
            "success": False,
            "message": f"❌ 进脑失败：{str(e)}\n\n{err_msg}"
        }


def nisb_batch_notes_to_brain(args: dict) -> Dict[str, Any]:
    """MCP 工具：批量笔记进脑（生产级）"""
    try:
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        directory = args.get("directory", "agent_files")
        file_pattern = args.get("file_pattern", "*.md")
        concept_language = args.get("concept_language", "auto")
        concept_backend = args.get("concept_backend", "llm_gpt4o_mini")
        
        from .config import get_base_path
        base_path = get_base_path(user_id, email, name)
        dir_path = Path(base_path) / directory
        
        if not dir_path.exists():
            return {"success": False, "message": f"❌ 目录不存在：{directory}"}
        
        from core.hebbian_pipeline import process_text_event
        
        processed = 0
        failed = 0
        skipped = 0
        failed_files: list[str] = []
        
        for file_path in dir_path.rglob(file_pattern):
            # 跳过隐藏文件
            if any(part.startswith('.') for part in file_path.parts):
                continue
            
            try:
                # 读取文件
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    failed += 1
                    failed_files.append(f"{file_path.name} (编码错误)")
                    print(f"[WARN batch] 跳过非 UTF-8 文件：{file_path}", file=sys.stderr)
                    continue
                
                if not content.strip():
                    skipped += 1
                    continue
                
                relative_path = str(file_path.relative_to(base_path))
                
                # 调用统一入口
                result = process_text_event(
                    base_path=base_path,
                    source_type="note",
                    source_id=relative_path,
                    text=content,
                    concept_language=concept_language,
                    concept_backend=concept_backend,
                    top_k=15,
                )
                
                # ⭐ 保持原有语义：只有 concepts>0 才算“成功进脑”
                if result and result.get("concepts", 0) > 0:
                    processed += 1
                else:
                    failed += 1
                    failed_files.append(f"{file_path.name} (概念提取失败)")
                
            except Exception as e:
                failed += 1
                failed_files.append(f"{file_path.name} ({str(e)[:30]}...)")
                print(f"[ERROR batch] {file_path}: {e}", file=sys.stderr)
        
        # 生成详细报告
        fail_detail = ""
        if failed_files:
            fail_detail = "\n\n❌ 失败文件列表：\n" + "\n".join(f"  • {f}" for f in failed_files[:10])
            if len(failed_files) > 10:
                fail_detail += f"\n  ... 及其他 {len(failed_files) - 10} 个文件"
        
        return {
            "success": True,
            "message": (
                "✅ 批量进脑完成\n\n"
                f"📂 目录：{directory}\n"
                f"✔️ 成功：{processed} 个文件\n"
                f"⊘ 跳过（空文件）：{skipped} 个\n"
                f"❌ 失败：{failed} 个"
                f"{fail_detail}\n\n"
                "💡 使用图谱工具查看关系网络"
            ),
            "stats": {
                "processed": processed,
                "skipped": skipped,
                "failed": failed,
                "failed_files": failed_files
            }
        }
    
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"[ERROR batch_notes_to_brain] {err_msg}", file=sys.stderr)
        return {
            "success": False,
            "message": f"❌ 批量进脑失败：{str(e)}\n\n{err_msg}"
        }


__all__ = ['nisb_note_to_brain', 'nisb_batch_notes_to_brain']

