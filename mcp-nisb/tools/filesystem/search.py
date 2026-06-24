"""
搜索功能模块（符合NISB规范）
⭐⭐⭐ Phase 3.5.1.1: 增强storage/内容搜索功能
"""

import os
import re
from typing import Dict, Any, List
from datetime import datetime
from .config import get_agent_files_path, get_base_path
from .utils import load_metadata, find_metadata_by_filename


def nisb_file_list(args: dict) -> Dict[str, Any]:
    """
    列出所有文件（符合NISB规范）
    ⭐ 支持path参数，支持storage/目录
    
    Args:
        args: 参数字典
            - path: 可选，指定目录（"agent_files", "storage", 或自定义路径）
            - file_type: 文件类型过滤
            - search: 搜索关键词（仅文件名）
            - limit: 返回数量限制
    """
    try:
        # ⭐ 提取多用户参数
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        
        # 参数
        custom_path = args.get("path")
        file_type = args.get("file_type")
        search = args.get("search")
        limit = args.get("limit", 20)
        
        # 确定搜索路径
        if custom_path:
            if custom_path == "storage":
                base_path = get_base_path(user_id, email, name)
                search_root = f"{base_path}/storage"
                display_name = "storage/"
            elif custom_path == "agent_files":
                search_root = get_agent_files_path(user_id, email, name)
                display_name = "agent_files/"
            else:
                # 自定义子路径
                base_path = get_base_path(user_id, email, name)
                search_root = f"{base_path}/{custom_path}"
                display_name = f"{custom_path}/"
        else:
            # 默认：agent_files
            search_root = get_agent_files_path(user_id, email, name)
            display_name = "agent_files/"
        
        # 检查路径是否存在
        if not os.path.exists(search_root):
            return {
                "success": True,
                "message": f"📁 {display_name} 暂无文件\n\n💡 创建文件：nisb_file_create(filename='...', content='...')",
                "files": []
            }
        
        # ⭐⭐⭐ 两种模式：元数据模式 vs 文件扫描模式
        meta_dir = f"{search_root}/.metadata" if "agent_files" in search_root else None
        
        files = []
        
        if meta_dir and os.path.exists(meta_dir):
            # 模式1：使用元数据（agent_files目录）
            for meta_file in os.listdir(meta_dir):
                if not meta_file.endswith('.json'):
                    continue
                
                metadata = load_metadata(user_id, meta_file.replace('.json', ''), email, name)
                if not metadata or metadata.get('deleted'):
                    continue
                
                # 过滤
                if file_type and metadata.get('file_type') != file_type:
                    continue
                
                if search:
                    search_lower = search.lower()
                    if (search_lower not in metadata.get('filename', '').lower() and
                        search_lower not in metadata.get('description', '').lower()):
                        continue
                
                files.append(metadata)
        
        else:
            # 模式2：直接扫描文件（storage目录）
            for root, dirs, filenames in os.walk(search_root):
                # 跳过隐藏目录
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for filename in filenames:
                    if filename.startswith('.'):
                        continue
                    
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, search_root)
                    
                    # 简单过滤（仅文件名）
                    if search and search.lower() not in filename.lower():
                        continue
                    
                    # 构建简化元数据
                    try:
                        stat = os.stat(file_path)
                        file_ext = os.path.splitext(filename)[1].lower()
                        
                        # 简单类型识别
                        type_map = {
                            '.py': 'python', '.js': 'javascript', '.json': 'json',
                            '.md': 'markdown', '.txt': 'text', '.csv': 'csv'
                        }
                        
                        files.append({
                            'filename': rel_path,
                            'file_path': file_path,
                            'file_type': type_map.get(file_ext, 'unknown'),
                            'size_bytes': stat.st_size,
                            'updated_at': stat.st_mtime,
                            'category': os.path.dirname(rel_path) or 'root',
                            'description': f'Storage文件: {filename}',
                            'file_id': None  # storage文件没有file_id
                        })
                    except Exception as e:
                        print(f"[WARN] 无法读取文件 {file_path}: {e}")
                        continue
        
        # 排序
        files.sort(key=lambda x: x.get('updated_at', 0) if isinstance(x.get('updated_at'), (int, float)) else x.get('updated_at', ''), reverse=True)
        total = len(files)
        files = files[:limit]
        
        # 构建输出
        lines = [f"📁 {display_name} 文件列表（共{total}个）\n"]
        
        # 统计
        type_counts = {}
        for f in files:
            ftype = f.get('file_type', 'unknown')
            type_counts[ftype] = type_counts.get(ftype, 0) + 1
        
        if type_counts:
            lines.append("📊 文件类型：")
            for ftype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"   • {ftype}: {count}个")
        
        lines.append(f"\n📄 最近{len(files)}个文件：\n")
        
        for i, f in enumerate(files, 1):
            lines.append(f"{i}. {f['filename']} ({f.get('file_type', 'unknown')})")
            lines.append(f"   📂 {f.get('category', 'unknown')}")
            
            # 处理时间戳
            updated = f.get('updated_at', '')
            if isinstance(updated, (int, float)):
                updated = datetime.fromtimestamp(updated).strftime('%Y-%m-%d')
            elif isinstance(updated, str):
                updated = updated[:10]
            lines.append(f"   🔄 {updated}")
            
            if f.get('description'):
                lines.append(f"   📝 {f['description']}")
            
            # 显示读取命令
            if f.get('file_id'):
                lines.append(f"   💡 nisb_file_read(file_id='{f['file_id']}')")
            else:
                # storage文件使用相对路径
                read_path = f"{display_name.rstrip('/')}/{f['filename']}"
                lines.append(f"   💡 nisb_file_read(filename='{read_path}')")
            
            lines.append("")
        
        # ⭐ 添加提示
        if custom_path == "storage":
            lines.append("🛡️ Storage目录：所有操作将自动备份")
        
        return {
            "success": True,
            "message": "\n".join(lines),
            "files": files,
            "total": total
        }
    
    except Exception as e:
        import traceback
        return {"success": False, "message": f"❌ 列表获取失败：{str(e)}\n\n{traceback.format_exc()}"}

def nisb_file_search(args: dict) -> Dict[str, Any]:
    """
    搜索文件（符合NISB规范）
    ⭐⭐⭐ Phase 3.5.1.2: 修复链接显示 + 增强storage/内容搜索
    
    Args:
        args: 参数字典
            - keyword: 搜索关键词（必需）
            - path: 可选，指定目录（"agent_files", "storage", 或自定义路径）
            - search_in: 搜索范围列表 ["filename", "content", "description"]
            - limit: 返回数量限制
            - case_sensitive: 是否区分大小写（默认False）
    """
    try:
        # 提取多用户参数
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        
        # 搜索参数（兼容多种参数名）
        keyword = args.get("keyword") or args.get("query") or args.get("search")
        custom_path = args.get("path") or args.get("file_type") or args.get("directory")
        search_in = args.get("search_in", ["filename", "content"])
        limit = args.get("limit", 10)
        case_sensitive = args.get("case_sensitive", False)
        
        if not keyword:
            return {"success": False, "message": "❌ 缺少keyword参数"}
        
        # 确定搜索路径
        if custom_path:
            if custom_path == "storage":
                base_path = get_base_path(user_id, email, name)
                search_root = f"{base_path}/storage"
                display_name = "storage/"
                use_metadata = False
            elif custom_path == "agent_files":
                search_root = get_agent_files_path(user_id, email, name)
                display_name = "agent_files/"
                use_metadata = True
            else:
                base_path = get_base_path(user_id, email, name)
                search_root = f"{base_path}/{custom_path}"
                display_name = f"{custom_path}/"
                use_metadata = False
        else:
            search_root = get_agent_files_path(user_id, email, name)
            display_name = "agent_files/"
            use_metadata = True
        
        # 检查路径
        if not os.path.exists(search_root):
            return {
                "success": True,
                "message": f"📁 {display_name} 暂无文件",
                "results": []
            }
        
        # 准备关键词
        search_keyword = keyword if case_sensitive else keyword.lower()
        
        results = []
        
        # ⭐⭐⭐ 两种搜索模式
        if use_metadata:
            # 模式1：元数据搜索（agent_files）
            meta_dir = f"{search_root}/.metadata"
            if os.path.exists(meta_dir):
                for meta_file in os.listdir(meta_dir):
                    if not meta_file.endswith('.json'):
                        continue
                    
                    metadata = load_metadata(user_id, meta_file.replace('.json', ''), email, name)
                    if not metadata or metadata.get('deleted'):
                        continue
                    
                    matches = []
                    
                    # 搜索文件名
                    if "filename" in search_in:
                        filename = metadata.get('filename', '')
                        if not case_sensitive:
                            filename = filename.lower()
                        if search_keyword in filename:
                            matches.append(("filename", metadata.get('filename', '')))
                    
                    # 搜索描述
                    if "description" in search_in:
                        desc = metadata.get('description', '')
                        if not case_sensitive:
                            desc = desc.lower()
                        if search_keyword in desc:
                            matches.append(("description", metadata.get('description', '')))
                    
                    # 搜索内容（读取文件）
                    if "content" in search_in and matches:  # 只有文件名或描述匹配时才读取内容
                        try:
                            with open(metadata['file_path'], 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            content_check = content if case_sensitive else content.lower()
                            if search_keyword in content_check:
                                # 提取匹配片段
                                snippet = _extract_snippet(content, keyword, case_sensitive)
                                matches.append(("content", snippet))
                        except:
                            pass
                    
                    if matches:
                        results.append({
                            'metadata': metadata,
                            'matches': matches,
                            'match_count': len(matches)
                        })
        
        else:
            # 模式2：文件系统搜索（storage）⭐⭐⭐
            for root, dirs, filenames in os.walk(search_root):
                # 跳过隐藏目录
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for filename in filenames:
                    if filename.startswith('.'):
                        continue
                    
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, search_root)
                    
                    matches = []
                    
                    # 搜索文件名
                    if "filename" in search_in:
                        filename_check = filename if case_sensitive else filename.lower()
                        if search_keyword in filename_check:
                            matches.append(("filename", filename))
                    
                    # 搜索内容
                    if "content" in search_in:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            content_check = content if case_sensitive else content.lower()
                            if search_keyword in content_check:
                                snippet = _extract_snippet(content, keyword, case_sensitive)
                                matches.append(("content", snippet))
                        except (UnicodeDecodeError, PermissionError):
                            # 跳过二进制文件或无权限文件
                            pass
                        except Exception as e:
                            print(f"[WARN] 读取文件失败 {file_path}: {e}")
                    
                    if matches:
                        # 构建简化元数据
                        try:
                            stat = os.stat(file_path)
                            results.append({
                                'metadata': {
                                    'filename': rel_path,
                                    'file_path': file_path,
                                    'size_bytes': stat.st_size,
                                    'updated_at': stat.st_mtime,
                                    'file_id': None
                                },
                                'matches': matches,
                                'match_count': len(matches)
                            })
                        except Exception as e:
                            print(f"[WARN] 获取文件信息失败 {file_path}: {e}")
        
        # 排序（匹配数量降序）
        results.sort(key=lambda x: x['match_count'], reverse=True)
        total = len(results)
        results = results[:limit]
        
        # 构建输出
        if not results:
            return {
                "success": True,
                "message": f"🔍 在 {display_name} 中未找到包含 '{keyword}' 的文件\n\n"
                          f"💡 搜索范围：{', '.join(search_in)}\n"
                          f"💡 尝试：nisb_file_list(path='{custom_path or 'agent_files'}', search='{keyword}')",
                "results": []
            }
        
        lines = [f"🔍 搜索结果（关键词：'{keyword}'）\n"]
        lines.append(f"📁 目录：{display_name}")
        lines.append(f"📊 找到 {total} 个匹配文件（显示前 {len(results)} 个）\n")
        
        for i, result in enumerate(results, 1):
            meta = result['metadata']
            matches = result['matches']
            
            lines.append(f"{i}. {meta.get('filename', 'unknown')}")
            lines.append(f"   📂 匹配：{len(matches)} 处")
            
            for match_type, match_text in matches:
                if match_type == "filename":
                    lines.append(f"   ✓ 文件名：{_highlight_keyword(match_text, keyword, case_sensitive)}")
                elif match_type == "description":
                    lines.append(f"   ✓ 描述：{_highlight_keyword(match_text, keyword, case_sensitive)}")
                elif match_type == "content":
                    lines.append(f"   ✓ 内容：{_highlight_keyword(match_text, keyword, case_sensitive)}")
            
            # ⭐⭐⭐ 修复：使用反引号避免被解析为链接
            if meta.get('file_id'):
                lines.append(f"   💡 读取命令: nisb_file_read(file_id='{meta['file_id']}')`")
            else:
                read_path = f"{display_name.rstrip('/')}/{meta.get('filename', '')}"
                lines.append(f"   💡 读取命令: nisb_file_read(filename='{read_path}')`")
            
            lines.append("")
        
        return {
            "success": True,
            "message": "\n".join(lines),
            "results": results,
            "total": total
        }
    
    except Exception as e:
        import traceback
        return {"success": False, "message": f"❌ 搜索失败：{str(e)}\n\n{traceback.format_exc()}"}

def nisb_file_info(args: dict) -> Dict[str, Any]:
    """
    获取文件详细信息（符合NISB规范）
    """
    try:
        # ⭐ 提取多用户参数
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        
        file_id = args.get("file_id")
        
        metadata = load_metadata(user_id, file_id, email, name)
        if not metadata:
            return {"success": False, "message": f"❌ 文件不存在：{file_id}"}
        
        msg_lines = [
            f"📄 文件详情\n",
            f"🆔 ID：{metadata['file_id']}",
            f"📁 文件名：{metadata['filename']}",
            f"📂 分类：{metadata.get('category', 'unknown')}",
            f"📦 类型：{metadata.get('file_type', 'unknown')}",
            f"📏 大小：{metadata.get('char_count', 0)} 字符",
            f"📅 创建：{metadata.get('created_at', '')[:19]}",
            f"🔄 更新：{metadata.get('updated_at', '')[:19]}\n"
        ]
        
        if metadata.get('description'):
            msg_lines.append(f"📝 描述：{metadata['description']}")
        
        if metadata.get('tags'):
            msg_lines.append(f"🏷️ 标签：{', '.join(metadata['tags'])}")
        
        analysis = metadata.get('analysis', {})
        if analysis.get('functions'):
            msg_lines.append(f"\n📦 函数：{', '.join(analysis['functions'][:10])}")
        if analysis.get('imports'):
            msg_lines.append(f"🔗 依赖：{', '.join(analysis['imports'][:10])}")
        
        return {
            "success": True,
            "message": "\n".join(msg_lines),
            "metadata": metadata
        }
    
    except Exception as e:
        return {"success": False, "message": f"❌ 获取失败：{str(e)}"}


# ============================================================
# 辅助函数
# ============================================================

def _extract_snippet(content: str, keyword: str, case_sensitive: bool, context_size: int = 50) -> str:
    """
    提取匹配关键词的上下文片段
    
    Args:
        content: 文件内容
        keyword: 搜索关键词
        case_sensitive: 是否区分大小写
        context_size: 上下文字符数
    
    Returns:
        匹配片段
    """
    try:
        # 查找关键词位置
        search_content = content if case_sensitive else content.lower()
        search_keyword = keyword if case_sensitive else keyword.lower()
        
        pos = search_content.find(search_keyword)
        if pos == -1:
            return ""
        
        # 提取上下文
        start = max(0, pos - context_size)
        end = min(len(content), pos + len(keyword) + context_size)
        
        snippet = content[start:end]
        
        # 添加省略号
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    except Exception as e:
        return f"[提取失败: {str(e)}]"


def _highlight_keyword(text: str, keyword: str, case_sensitive: bool) -> str:
    """
    高亮关键词（使用**标记）
    
    Args:
        text: 原文本
        keyword: 关键词
        case_sensitive: 是否区分大小写
    
    Returns:
        高亮后的文本
    """
    try:
        if not case_sensitive:
            # 不区分大小写：查找所有匹配
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            return pattern.sub(lambda m: f"**{m.group()}**", text)
        else:
            # 区分大小写：直接替换
            return text.replace(keyword, f"**{keyword}**")
    
    except Exception as e:
        return text

