#!/usr/bin/env python3
"""
NISB Tools - L2 Work Layer (工作记忆层)
Phase 2.9.7 多用户版本
Phase 3.0.2 新增：nisb_list_concepts（解决黑盒问题）
Phase 6.0 修复：多用户隔离完善

提供快速查询、激活、概念列表功能
"""

from datetime import datetime
import sys
sys.path.insert(0, '/srv')

from core.storage import (
    ensure_directories,
    load_hot_cache,
    load_concepts_index,
    search_concepts_simple,
    get_system_stats,
    save_hot_cache,
    save_concepts_index,
    get_user_base_path,
    ensure_user_directory
)
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_work_query(args: dict) -> dict:
    """L2工具：查询工作记忆"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
   
    query = args.get("query", "")
    limit = args.get("limit", 10)
    
    if not query.strip():
        return {
            "status": "error",
            "message": "❌ 查询关键词不能为空"
        }
    
    ensure_directories(base_path)
    
    start_time = datetime.now()
    results = search_concepts_simple(base_path, query, limit)
    end_time = datetime.now()
    search_time_ms = int((end_time - start_time).total_seconds() * 1000)
    
    if not results:
        message = f"🔍 未找到匹配「{query}」的概念"
    else:
        lines = [f"🔍 找到 {len(results)} 个匹配「{query}」的概念：\n"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. {r['name_zh']} ({r['name']})\n"
                f"   激活权重: {r['activation_weight']:.2f}\n"
                f"   最后活跃: {r['last_active'][:10]}"
            )
        message = "\n\n".join(lines)
    
    return {
        "status": "success",
        "results": results,
        "total": len(results),
        "search_time_ms": search_time_ms,
        "message": message
    }

@auto_user_context
def nisb_work_hot(args: dict) -> dict:
    """L2工具：获取热门概念"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    limit = args.get("limit", 10)
    period = args.get("period", "week")
    
    ensure_directories(base_path)
    
    hot_cache = load_hot_cache(base_path)
    concepts = hot_cache.get("concepts", [])
    
    concepts.sort(key=lambda x: x.get("activation_weight", 0), reverse=True)
    hot_concepts = concepts[:limit]
    
    if not hot_concepts:
        message = "📊 暂无热门概念数据"
    else:
        lines = [f"🔥 最近{period}的热门概念（Top {len(hot_concepts)}）：\n"]
        for i, c in enumerate(hot_concepts, 1):
            lines.append(
                f"{i}. {c.get('name_zh', '')} ({c.get('name', '')})\n"
                f"   激活权重: {c.get('activation_weight', 0):.2f}"
            )
        message = "\n\n".join(lines)
    
    return {
        "status": "success",
        "hot_concepts": hot_concepts,
        "last_updated": hot_cache.get("generated_at"),
        "message": message
    }

@auto_user_context
def nisb_work_stats(args: dict) -> dict:
    """L2工具：获取系统统计"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
   
    ensure_directories(base_path)
    
    stats = get_system_stats(base_path)
    
    message = f"""📊 NISB系统统计

概念总数：{stats['total_concepts']}
热门概念：{stats['hot_concepts_count']}
原始记录：{stats['total_raw_records']}

缓存更新：{stats['cache_updated'][:19] if stats['cache_updated'] else '未生成'}
索引更新：{stats['index_updated'][:19] if stats['index_updated'] else '未生成'}

系统状态：运行正常 ✅"""
    
    return {
        "status": "success",
        "stats": stats,
        "message": message
    }

@auto_user_context
def nisb_work_activate(args: dict) -> dict:
    """
    激活概念（Phase 3.0完整版：激活扩散 + Hebbian学习）
    
    参数:
        concept_id: string (必填，概念名称或ID)
        strength: float (可选，激活强度，默认0.1)
        spread: boolean (可选，是否激活扩散，默认True) ⭐ Phase 3.0新增
        max_depth: integer (可选，扩散最大深度，默认3) ⭐ Phase 3.0新增
        user_id: string (自动注入)
    
    返回:
        {
          status,
          activation_new,
          spread_to: [...],
          hebbian_updates: 5,
          message
        }
    """
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    # 参数解析
    concept_id = args.get("concept_id", "").strip()
    strength = float(args.get("strength", 0.1))
    enable_spread = args.get("spread", True)
    max_depth = int(args.get("max_depth", 3))
    
    if not concept_id:
        return {"status": "error", "message": "❌ concept_id不能为空"}
    
    # 加载概念索引
    from core.storage import load_concepts_index, save_concepts_index
    index = load_concepts_index(base_path)
    concepts = index.get("concepts", {})
    
    # 支持概念名称输入
    original_input = concept_id
    if not concept_id.startswith("concept_"):
        found = None
        for cid, cdata in concepts.items():
            name = cdata.get("name", "").lower()
            name_zh = cdata.get("name_zh", "").lower()
            if name == concept_id.lower() or name_zh == concept_id.lower():
                found = cid
                break
        
        if not found:
            return {"status": "error", "message": f"❌ 找不到概念：{concept_id}"}
        concept_id = found
    
    if concept_id not in concepts:
        return {"status": "error", "message": f"❌ 概念不存在：{concept_id}"}
    
    concept = concepts[concept_id]
    concept_name = concept.get("name_zh") or concept.get("name")
    
    # ========== Phase 2.x 原有逻辑：更新激活权重 ==========
    old_weight = concept.get("activation_weight", 0.5)
    new_weight = min(1.0, old_weight + strength)
    
    concept["activation_weight"] = new_weight
    concept["last_active"] = datetime.now().isoformat()
    concept["discussion_count"] = concept.get("discussion_count", 0) + 1
    
    # 更新状态
    if new_weight >= 0.7:
        concept["status"] = "hot"
    elif new_weight >= 0.4:
        concept["status"] = "warm"
    else:
        concept["status"] = "cold"
    
    # 保存概念索引
    save_concepts_index(base_path, index)
    
    # ========== Phase 3.0 新增：激活扩散 + Hebbian学习 ==========
    spread_to = []
    hebbian_updates = 0
    
    if enable_spread:
        try:
            # 导入Relations模块
            from core.relations import get_relations_by_concept, strengthen_relation
            
            # 执行激活扩散（DFS，最多3跳）
            visited = set([concept_id])
            
            def _dfs(current_id, current_strength, depth, path):
                nonlocal hebbian_updates
                
                # 终止条件
                if depth >= max_depth or current_strength < 0.05:
                    return
                
                # 获取当前概念的所有关系
                relations = get_relations_by_concept(base_path, current_id, min_strength=0.3)
                
                for rel in relations:
                    target_id = rel["to_id"]
                    
                    # 跳过已访问的节点（避免循环）
                    if target_id in visited:
                        continue
                    
                    visited.add(target_id)
                    
                    # 计算扩散强度（衰减）
                    spread_strength = current_strength * rel["strength"]
                    
                    # 激活目标概念
                    if target_id in concepts:
                        target_concept = concepts[target_id]
                        target_old = target_concept.get("activation_weight", 0.5)
                        target_new = min(1.0, target_old + spread_strength)
                        
                        target_concept["activation_weight"] = target_new
                        target_concept["last_active"] = datetime.now().isoformat()
                        
                        # 更新状态
                        if target_new >= 0.7:
                            target_concept["status"] = "hot"
                        elif target_new >= 0.4:
                            target_concept["status"] = "warm"
                        else:
                            target_concept["status"] = "cold"
                        
                        # 记录扩散路径
                        target_name = target_concept.get("name_zh") or target_concept.get("name")
                        path_names = [concepts[cid].get("name_zh") or concepts[cid].get("name") for cid in path]
                        
                        spread_to.append({
                            "concept_id": target_id,
                            "concept_name": target_name,
                            "strength": spread_strength,
                            "depth": depth,
                            "path": path_names + [target_name],
                            "activation_old": target_old,
                            "activation_new": target_new
                        })
                        
                        # ⭐ Hebbian学习：增强突触
                        strengthen_result = strengthen_relation(base_path, current_id, target_id, delta=0.01)
                        if strengthen_result["status"] == "success":
                            hebbian_updates += 1
                        
                        # 递归扩散
                        _dfs(target_id, spread_strength, depth + 1, path + [target_id])
            
            # 从源概念开始扩散
            _dfs(concept_id, strength, 0, [concept_id])
            
            # 保存更新后的概念索引（包含所有被激活的概念）
            save_concepts_index(base_path, index)
            
        except Exception as e:
            # 如果Relations模块未初始化或出错，不影响原有功能
            print(f"[WARN] 激活扩散失败（可能Relations未初始化）：{e}")
            spread_to = []
            hebbian_updates = 0
    
    # 更新热缓存
    from core.storage import rebuild_hot_cache
    rebuild_hot_cache(base_path)
    
    # ========== 格式化输出 ==========
    lines = [f"⚡ 激活成功：{concept_name}\n"]
    lines.append(f"激活权重：{old_weight:.2f} → {new_weight:.2f}")
    lines.append(f"状态：{concept['status']}")
    lines.append(f"讨论次数：{concept['discussion_count']}")
    
    if enable_spread and spread_to:
        lines.append(f"\n🌊 激活扩散：{len(spread_to)}个相关概念")
        lines.append(f"💪 Hebbian学习：增强{hebbian_updates}条突触\n")
        
        # 按深度分组显示
        by_depth = {}
        for item in spread_to:
            depth = item["depth"]
            if depth not in by_depth:
                by_depth[depth] = []
            by_depth[depth].append(item)
        
        for depth in sorted(by_depth.keys()):
            items = by_depth[depth]
            lines.append(f"【{depth + 1}跳】{len(items)}个概念")
            
            # 显示前5个
            for item in items[:5]:
                lines.append(f"  → {item['concept_name']}")
                lines.append(f"     强度：{item['strength']:.3f}，激活：{item['activation_old']:.2f}→{item['activation_new']:.2f}")
            
            if len(items) > 5:
                lines.append(f"  ... 还有{len(items) - 5}个")
    
    elif enable_spread:
        lines.append(f"\n⚠️  激活扩散：未发现相关概念")
        lines.append("💡 提示：使用 nisb_discover_relations 自动建立关系网络")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "concept_id": concept_id,
        "concept_name": concept_name,
        "activation_old": old_weight,
        "activation_new": new_weight,
        "status": concept["status"],
        "spread_enabled": enable_spread,
        "spread_to": spread_to,
        "hebbian_updates": hebbian_updates,
        "message": message
    }


# ⭐⭐⭐ Phase 3.0.2 新增：层次3功能 ⭐⭐⭐
@auto_user_context
def nisb_list_concepts(args: dict) -> dict:
    """
    列出系统中的所有概念（支持过滤、排序、分页）
    
    Phase 3.0.2 改进版：
    - ✅ 智能分页（避免输出过长）
    - ✅ 统计摘要（快速了解概念分布）
    - ✅ 导出到文件（处理大数据集）
    """
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    # 参数解析
    search = args.get("search", "").strip()
    limit = min(int(args.get("limit", 50)), 100)
    offset = max(int(args.get("offset", 0)), 0)
    sort_by = args.get("sort_by", "weight").lower()
    status_filter = args.get("status_filter", "all").lower()
    show_summary = args.get("show_summary", True)
    export = args.get("export", False)
    
    # ⭐ 修复：预定义字典，避免f-string语法错误
    sort_names = {'weight': '按权重', 'name': '按名称', 'time': '按时间'}
    status_icons = {'hot': '🔥', 'warm': '🌡️', 'cold': '❄️'}
    
    # 验证参数
    if sort_by not in ["weight", "name", "time"]:
        sort_by = "weight"
    
    if status_filter not in ["hot", "warm", "cold", "all"]:
        status_filter = "all"
    
    # 加载索引
    ensure_directories(base_path)
    index = load_concepts_index(base_path)
    concepts = index.get("concepts", {})
    
    if not concepts:
        return {
            "status": "success",
            "concepts": [],
            "total": 0,
            "filtered": 0,
            "message": "⚠️ 系统中暂无概念\n\n💡 提示：使用 nisb_sense_quick_note 保存笔记后会自动提取概念"
        }
    
    # 构建概念列表
    concept_list = []
    for cid, cdata in concepts.items():
        name = cdata.get("name", "")
        name_zh = cdata.get("name_zh", "")
        display_name = name_zh if name_zh else name
        
        weight = cdata.get("activation_weight", 0)
        status = cdata.get("status", "cold")
        last_active = cdata.get("last_active", "")
        discussion_count = cdata.get("discussion_count", 0)
        
        # 搜索过滤
        if search:
            search_lower = search.lower()
            if (search_lower not in name.lower() and 
                search_lower not in name_zh and
                name.lower() not in search_lower and
                name_zh not in search):
                continue
        
        # 状态过滤
        if status_filter != "all" and status != status_filter:
            continue
        
        concept_list.append({
            "id": cid,
            "name": display_name,
            "weight": weight,
            "status": status,
            "last_active": last_active,
            "discussion_count": discussion_count
        })
    
    # 排序
    if sort_by == "weight":
        concept_list.sort(key=lambda x: x["weight"], reverse=True)
    elif sort_by == "time":
        concept_list.sort(key=lambda x: x["last_active"], reverse=True)
    else:  # name
        concept_list.sort(key=lambda x: x["name"])
    
    # 统计摘要
    filtered_count = len(concept_list)
    
    summary = {}
    if show_summary:
        status_counts = {"hot": 0, "warm": 0, "cold": 0}
        for c in concept_list:
            status_counts[c["status"]] = status_counts.get(c["status"], 0) + 1
        
        weights = [c["weight"] for c in concept_list]
        avg_weight = sum(weights) / len(weights) if weights else 0
        max_weight = max(weights) if weights else 0
        min_weight = min(weights) if weights else 0
        
        summary = {
            "total": len(concepts),
            "filtered": filtered_count,
            "status_counts": status_counts,
            "weight_stats": {
                "avg": round(avg_weight, 2),
                "max": round(max_weight, 2),
                "min": round(min_weight, 2)
            }
        }
    
    # 导出到文件
    export_file = None
    if export:
        import json
        
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "total": len(concepts),
            "filtered": filtered_count,
            "filters": {
                "search": search or None,
                "status_filter": status_filter,
                "sort_by": sort_by
            },
            "concepts": concept_list
        }
        
        export_dir = f"{base_path}/storage/exports"
        import os
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = f"{export_dir}/concepts_{timestamp}.json"
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    # 分页
    total_pages = (filtered_count + limit - 1) // limit if limit > 0 else 1
    current_page = (offset // limit) + 1 if limit > 0 else 1
    
    if limit == 0:
        display_list = []
        has_more = False
    else:
        display_list = concept_list[offset:offset + limit]
        has_more = (offset + limit) < filtered_count
    
    # 格式化输出
    lines = [f"📚 系统概念列表（共{len(concepts)}个）\n"]
    
    # 统计摘要
    if show_summary:
        lines.append(f"📊 统计摘要：")
        lines.append(f"   🔥 热门：{summary['status_counts']['hot']}个")
        lines.append(f"   🌡️ 温热：{summary['status_counts']['warm']}个")
        lines.append(f"   ❄️ 冷门：{summary['status_counts']['cold']}个")
        lines.append(f"   📈 平均权重：{summary['weight_stats']['avg']:.2f}\n")
    
    # 过滤和排序信息
    if search:
        lines.append(f"🔍 搜索：{search}，找到{filtered_count}个")
    
    if status_filter != "all":
        lines.append(f"🎯 状态过滤：{status_filter}")
    
    # ⭐ 修复：使用预定义的字典
    lines.append(f"📊 排序方式：{sort_names[sort_by]}")
    
    # 分页信息
    if limit > 0:
        lines.append(f"📄 第{current_page}页（共{total_pages}页），显示{len(display_list)}个\n")
    else:
        lines.append(f"📄 仅显示摘要（设置limit>0查看列表）\n")
    
    # 显示概念列表
    if display_list:
        for i, c in enumerate(display_list, offset + 1):
            icon = status_icons.get(c["status"], "")
            lines.append(f"{i:3d}. {c['name']} {icon}")
            lines.append(f"      权重：{c['weight']:.2f}，讨论：{c['discussion_count']}次，最后活跃：{c['last_active'][:10]}")
    
    # 导出信息
    if export_file:
        lines.append(f"\n💾 已导出到文件：")
        lines.append(f"   {export_file}")
        lines.append(f"   包含{filtered_count}个概念的完整数据")
    
    # 分页提示
    if has_more:
        next_offset = offset + limit
        lines.append(f"\n💡 查看下一页：")
        lines.append(f"   nisb_list_concepts(limit={limit}, offset={next_offset})")
    
    # 大数据集警告
    if filtered_count > 200 and not export:
        lines.append(f"\n⚠️ 概念数量较多（{filtered_count}个）")
        lines.append(f"   建议：nisb_list_concepts(export=True) 导出完整数据到文件")
    
    # 使用提示
    if not search and limit > 0:
        lines.append(f"\n💡 提示：")
        lines.append(f"   - 搜索概念：nisb_list_concepts(search='关键词')")
        lines.append(f"   - 只看摘要：nisb_list_concepts(limit=0)")
        lines.append(f"   - 导出数据：nisb_list_concepts(export=True)")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "concepts": display_list,
        "total": len(concepts),
        "filtered": filtered_count,
        "page": current_page,
        "total_pages": total_pages,
        "has_more": has_more,
        "offset": offset,
        "limit": limit,
        "sort_by": sort_by,
        "status_filter": status_filter,
        "summary": summary if show_summary else None,
        "export_file": export_file,
        "message": message
    }

