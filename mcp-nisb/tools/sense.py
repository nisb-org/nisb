#!/usr/bin/env python3
"""
NISB Tools - L1 Sense Layer (感觉输入层)
Phase 2.9.7 多用户版本 + Phase 5.1 竞态条件修复 + Phase 6.0 完善

提供原始记录功能
更新日期: 2025-11-03
"""

from datetime import datetime
import os
import sys
sys.path.insert(0, '/srv')

from core.schema import RawRecord, generate_raw_id, generate_note_id
from core.storage import (
    ensure_directories,
    save_raw_record,
    save_quick_note,
    load_json,
    save_json,
    process_new_record,
    list_quick_notes,
    search_notes,
    get_user_base_path,
    ensure_user_directory
)

from tools.recall.note_recall import nisb_sense_recall_note

from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_sense_record(args: dict) -> dict:
    """L1工具：记录原始对话"""
    
    # ✅ Phase 6.0确认：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    conversation = args.get("conversation", [])
    keywords = args.get("keywords", [])
    session_context = args.get("session_context", {})
    
    ensure_directories(base_path)
    
    raw_id = generate_raw_id()
    record = RawRecord(raw_id=raw_id, conversation=conversation)
    record.keywords = keywords
    record.session_context = session_context
    
    file_path = save_raw_record(base_path, record.to_dict())
    
    total_turns = len(conversation)
    total_chars = sum(len(msg.get("content", "")) for msg in conversation)
    
    text_to_process = " ".join([msg.get("content", "") for msg in conversation])
    if text_to_process.strip():
        try:
            process_new_record(
                base_path=base_path,
                record_id=raw_id,
                record_content=text_to_process,
                record_type="daily"
            )
        except Exception as e:
            print(f"[ERROR sense_record] 概念提取失败: {e}")
    
    return {
        "status": "success",
        "raw_id": raw_id,
        "timestamp": record.timestamp,
        "file_path": file_path,
        "stats": {
            "total_turns": total_turns,
            "total_chars": total_chars,
            "keywords_count": len(keywords)
        },
        "message": f"✅ 已记录对话：{raw_id}\n"
                   f"   回合数：{total_turns}\n"
                   f"   字符数：{total_chars}\n"
                   f"   关键词：{len(keywords)}个\n"
                   f"   💡 正在后台处理概念提取..."
    }

@auto_user_context
def nisb_sense_quick_note(args: dict) -> dict:
    """
    L1工具：快速笔记
    
    Phase 3.0.2 改进：
    - 显示自动提取的概念（解决黑盒问题）
    - 即时反馈提取结果
    
    Phase 4.1 改进：
    - 自动向量化笔记内容 ⭐
    
    Phase 6.0修复：
    - 完善user_context获取
    """
    
    # ✅ Phase 6.0确认：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    content = args.get("content", "")
    tags = args.get("tags", [])

    print(f"[DEBUG quick_note] 用户: {user_ctx.user_id}, 内容长度: {len(content)}字符", file=sys.stderr)
    if len(content) > 0:
        print(f"[DEBUG quick_note] 内容前100字: {content[:100]}", file=sys.stderr)
        print(f"[DEBUG quick_note] 内容后100字: {content[-100:]}", file=sys.stderr)
    
    MAX_SAFE_LENGTH = 1000000
    if len(content) > MAX_SAFE_LENGTH:
        return {
            "status": "warning",
            "note_id": None,
            "message": f"⚠️ 笔记过长（{len(content)}字符），可能被截断\n"
                       f"   建议：请使用 nisb_sense_quick_note_segment 分段保存\n"
                       f"   或让NISB Assistant自动分段\n"
                       f"   安全长度：<{MAX_SAFE_LENGTH}字符"
        }
   
    if not content.strip():
        return {
            "status": "error",
            "message": "❌ 内容不能为空"
        }
    
    ensure_directories(base_path)
    
    note_id = generate_note_id()
    
    note_data = {
        "id": note_id,
        "timestamp": datetime.now().isoformat(),
        "content": content,
        "tags": tags
    }
    
    # ⭐⭐⭐ Phase 4.1：自动向量化笔记 ⭐⭐⭐
    try:
        from core.openai_utils import get_embedding
        embedding = get_embedding(content)
        note_data["embedding"] = embedding
        print(f"[DEBUG quick_note] 向量化成功: {note_id}", file=sys.stderr)
    except Exception as e:
        print(f"[WARN quick_note] 向量化失败: {e}", file=sys.stderr)
    
    file_path = save_quick_note(base_path, note_data)
    
    # ⭐⭐⭐ Phase 3.0.2：提前提取概念并显示 ⭐⭐⭐
    extracted_concepts = []
    if content.strip():
        try:
            import jieba.analyse
            keywords = jieba.analyse.extract_tags(content, topK=30, withWeight=False)
            
            # 过滤停用词和黑名单
            from core.storage import _load_concept_blacklist
            blacklist = _load_concept_blacklist(base_path)
            
            for kw in keywords:
                kw_lower = kw.lower()
                if len(kw) >= 2 and not kw.isdigit():
                    if not blacklist or kw_lower not in blacklist:
                        extracted_concepts.append(kw)
            
            extracted_concepts = list(dict.fromkeys(extracted_concepts))[:10]
            
            print(f"[DEBUG quick_note] 提取概念: {extracted_concepts}", file=sys.stderr)
            
            process_new_record(
                base_path=base_path,
                record_id=note_id,
                record_content=content,
                record_type="quick_note"
            )
        except Exception as e:
            print(f"[ERROR quick_note] 概念提取失败: {e}", file=sys.stderr)
    
    message = f"✅ 已保存快速笔记：{note_id}\n"
    message += f"   内容：{content[:50]}...\n" if len(content) > 50 else f"   内容：{content}\n"
    message += f"   标签：{', '.join(tags) if tags else '无'}\n"
    message += f"   💾 保存位置: {file_path}\n"
    message += f"   🧠 向量化: {'成功' if 'embedding' in note_data else '失败'}\n"  # ⭐ 新增状态显示
    
    if extracted_concepts:
        message += f"\n🧠 自动提取的概念（{len(extracted_concepts)}个）：\n"
        message += f"   {', '.join(extracted_concepts)}\n"
        message += f"\n💡 提示：\n"
        message += f"   - 查询时请使用这些概念名称\n"
        message += f"   - 示例：nisb_query_all(concept='{extracted_concepts[0]}')"
    else:
        message += f"\n⚠️ 未提取到有效概念（内容可能过短或被过滤）"
    
    return {
        "status": "success",
        "note_id": note_id,
        "timestamp": note_data["timestamp"],
        "file_path": file_path,
        "extracted_concepts": extracted_concepts,
        "vectorized": "embedding" in note_data,  # ⭐ 新增字段
        "message": message
    }

@auto_user_context
def nisb_sense_mark_important(args: dict) -> dict:
    """L1工具：标记重要片段"""
    
    # ✅ Phase 6.0确认：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    raw_id = args.get("raw_id", "")
    highlight = args.get("highlight", "")
    reason = args.get("reason", "")
    
    if not raw_id or not highlight:
        return {
            "status": "error",
            "message": "❌ raw_id和highlight不能为空"
        }
    
    try:
        date_part = raw_id.split("_")[1]
        date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
        file_path = f"{base_path}/storage/raw/daily/{date_str}/{raw_id}.json"
        
        raw_data = load_json(file_path)
        if not raw_data:
            return {
                "status": "error",
                "message": f"❌ 找不到记录：{raw_id}"
            }
        
        if "session_context" not in raw_data:
            raw_data["session_context"] = {}
        
        if "important_marks" not in raw_data["session_context"]:
            raw_data["session_context"]["important_marks"] = []
        
        raw_data["session_context"]["important_marks"].append({
            "timestamp": datetime.now().isoformat(),
            "highlight": highlight,
            "reason": reason
        })
        
        save_json(file_path, raw_data)
        
        return {
            "status": "success",
            "message": f"✅ 已标记重要片段\n"
                       f"   记录：{raw_id}\n"
                       f"   内容：{highlight[:50]}...\n"
                       f"   原因：{reason if reason else '未说明'}"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ 标记失败：{str(e)}"
        }

@auto_user_context
def nisb_sense_quick_note_segment(args: dict) -> dict:
    """L1工具：分段保存长笔记"""
    
    # ✅ Phase 6.0确认：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
   
    content = args.get("content", "")
    note_id = args.get("note_id")
    tags = args.get("tags", [])
    finalize = args.get("finalize", False)
    
    temp_dir = os.path.join(base_path, "storage/temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    if not note_id:
        note_id = generate_note_id()
        temp_file = os.path.join(temp_dir, f"{note_id}.txt")
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[DEBUG segment] 用户: {user_ctx.user_id}, 创建新笔记: {note_id}, 第1段: {len(content)}字符", file=sys.stderr)
        
        if finalize:
            note_data = {
                "id": note_id,
                "timestamp": datetime.now().isoformat(),
                "content": content,
                "tags": tags
            }
            file_path = save_quick_note(base_path, note_data)
            os.remove(temp_file)
            
            if content.strip():
                try:
                    process_new_record(
                        base_path=base_path,
                        record_id=note_id,
                        record_content=content,
                        record_type="quick_note"
                    )
                except Exception as e:
                    print(f"[ERROR segment] 概念提取失败: {e}", file=sys.stderr)
            
            return {
                "status": "success",
                "note_id": note_id,
                "file_path": file_path,
                "total_length": len(content),
                "message": f"✅ 笔记保存完成\n"
                           f"   笔记ID：{note_id}\n"
                           f"   长度：{len(content)}字符\n"
                           f"   标签：{', '.join(tags) if tags else '无'}"
            }
        
        return {
            "status": "success",
            "note_id": note_id,
            "segment_num": 1,
            "message": f"✅ 第1段已保存（{len(content)}字符）\n"
                       f"   笔记ID：{note_id}\n"
                       f"   请继续传递此ID保存后续段落"
        }
    
    temp_file = os.path.join(temp_dir, f"{note_id}.txt")
    
    if not os.path.exists(temp_file):
        return {
            "status": "error",
            "message": f"❌ 找不到临时文件（note_id: {note_id}）\n"
                       f"   可能已超时或ID错误"
        }
    
    with open(temp_file, 'a', encoding='utf-8') as f:
        f.write(content)
    
    with open(temp_file, 'r', encoding='utf-8') as f:
        current_content = f.read()
    
    segment_num = content.count('\n') + 1
    
    print(f"[DEBUG segment] 用户: {user_ctx.user_id}, 追加段落: {note_id}, 累计: {len(current_content)}字符", file=sys.stderr)
    
    if finalize:
        full_content = current_content
        
        note_data = {
            "id": note_id,
            "timestamp": datetime.now().isoformat(),
            "content": full_content,
            "tags": tags
        }
        
        file_path = save_quick_note(base_path, note_data)
        
        os.remove(temp_file)
        
        print(f"[DEBUG segment] 用户: {user_ctx.user_id}, 完成保存: {note_id}, 总长度: {len(full_content)}字符", file=sys.stderr)
        
        if full_content.strip():
            try:
                process_new_record(
                    base_path=base_path,
                    record_id=note_id,
                    record_content=full_content,
                    record_type="quick_note"
                )
            except Exception as e:
                print(f"[ERROR segment] 概念提取失败: {e}", file=sys.stderr)
        
        return {
            "status": "success",
            "note_id": note_id,
            "file_path": file_path,
            "total_length": len(full_content),
            "message": f"✅ 长笔记保存完成\n"
                       f"   笔记ID：{note_id}\n"
                       f"   总长度：{len(full_content)}字符\n"
                       f"   标签：{', '.join(tags) if tags else '无'}\n"
                       f"   💡 正在后台处理概念提取..."
        }
    
    return {
        "status": "success",
        "note_id": note_id,
        "current_length": len(current_content),
        "message": f"✅ 第{segment_num}段已保存（累计{len(current_content)}字符）\n"
                   f"   继续传递note_id保存后续段落"
    }

@auto_user_context
def nisb_sense_list_notes(args: dict) -> dict:
    """L1工具：列出最近的笔记"""
    
    # ✅ Phase 6.0确认：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    limit = args.get("limit", 10)
    date_filter = args.get("date")
    
    try:
        notes = list_quick_notes(base_path, limit=limit, date_filter=date_filter)
        
        if not notes:
            return {
                "status": "success",
                "notes": [],
                "total": 0,
                "message": "📝 暂无笔记记录"
            }
        
        lines = ["📝 最近的笔记：\n"]
        for i, note in enumerate(notes, 1):
            timestamp = note.get("timestamp", "")
            note_id = note.get("id", "")
            preview = note.get("content", "")[:50].replace("\n", " ")
            tags_str = ", ".join([f"#{t}" for t in note.get("tags", [])])
            
            lines.append(
                f"{i}. [{timestamp[:16]}] {note_id}\n"
                f"   预览: {preview}...\n"
                f"   标签: {tags_str if tags_str else '无'}\n"
            )
        
        message = "\n".join(lines)
        message += f"\n共 {len(notes)} 条笔记"
        
        return {
            "status": "success",
            "notes": notes,
            "total": len(notes),
            "message": message
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ 查询失败：{str(e)}"
        }

@auto_user_context
def nisb_sense_search_notes(args: dict) -> dict:
    """L1工具：搜索笔记内容"""
    
    # ✅ Phase 6.0确认：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    query = args.get("query", "")
    limit = args.get("limit", 5)
    
    if not query:
        return {
            "status": "error",
            "message": "❌ 缺少query参数"
        }
    
    try:
        results = search_notes(base_path, query, limit=limit)
        
        if not results:
            return {
                "status": "success",
                "results": [],
                "total": 0,
                "message": f"🔍 未找到包含「{query}」的笔记"
            }
        
        lines = [f"🔍 搜索「{query}」，找到 {len(results)} 条笔记：\n"]
        
        for i, result in enumerate(results, 1):
            timestamp = result.get("timestamp", "")
            note_id = result.get("id", "")
            snippet = result.get("snippet", "")
            tags_str = ", ".join([f"#{t}" for t in result.get("tags", [])])
            
            lines.append(
                f"{i}. [{timestamp[:16]}] {note_id}\n"
                f"   {snippet}...\n"
                f"   标签: {tags_str if tags_str else '无'}\n"
            )
        
        message = "\n".join(lines)
        
        return {
            "status": "success",
            "results": results,
            "total": len(results),
            "message": message
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ 搜索失败：{str(e)}"
        }

