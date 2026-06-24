#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus批量入库工具
一次性导入多个episodes
"""

import time
from .ingest import nisb_corpus_ingest
from .enrich import nisb_corpus_enrich


def nisb_corpus_batch_ingest(args: dict) -> dict:
    """
    批量入库多个episodes
    
    Args:
        brain_id: 大脑ID（必填）
        episodes: list[dict] - episode数据列表
            每个元素格式：
            {
              "episode_number": 301,
              "L1_segments": [...],
              "L2_pattern": {...},
              "L3_cases": [...]
            }
        auto_enrich: bool - 是否自动生成embeddings（默认True）
    
    Returns:
        {
          "status": "success",
          "brain_id": "brain_utopia",
          "total_episodes": 30,
          "success_count": 30,
          "failed": [],
          "embeddings_generated": True,
          "total_time_seconds": 45.2,
          "message": "..."
        }
    """
    brain_id = args.get("brain_id")
    episodes = args.get("episodes", [])
    auto_enrich = args.get("auto_enrich", True)
    
    if not brain_id:
        return {"status": "error", "message": "❌ brain_id不能为空"}
    
    if not episodes:
        return {"status": "error", "message": "❌ episodes不能为空"}
    
    # ========== 批量入库 ==========
    start_time = time.time()
    success_count = 0
    failed = []
    
    for i, episode_data in enumerate(episodes, 1):
        episode_num = episode_data.get("episode_number")
        
        print(f"⏳ [{i}/{len(episodes)}] 入库 Episode {episode_num}...")
        
        try:
            # 调用单个入库函数
            result = nisb_corpus_ingest({
                "brain_id": brain_id,
                "episode_number": episode_num,
                "L1_segments": episode_data.get("L1_segments", []),
                "L2_pattern": episode_data.get("L2_pattern", {}),
                "L3_cases": episode_data.get("L3_cases", [])
            })
            
            if result.get("status") == "success":
                success_count += 1
                print(f"   ✅ Episode {episode_num} 入库成功")
            else:
                failed.append({
                    "episode": episode_num,
                    "error": result.get("message", "未知错误")
                })
                print(f"   ❌ Episode {episode_num} 入库失败")
        
        except Exception as e:
            failed.append({
                "episode": episode_num,
                "error": str(e)
            })
            print(f"   ❌ Episode {episode_num} 异常：{e}")
    
    ingest_time = time.time() - start_time
    
    # ========== 自动生成embeddings ==========
    embeddings_generated = False
    enrich_time = 0
    
    if auto_enrich and success_count > 0:
        print(f"\n⏳ 正在为所有episodes生成embeddings...")
        enrich_start = time.time()
        
        try:
            enrich_result = nisb_corpus_enrich({
                "brain_id": brain_id,
                "force": False
            })
            
            if enrich_result.get("status") == "success":
                embeddings_generated = True
                print(f"✅ Embeddings生成完成")
            else:
                print(f"⚠️  Embeddings生成失败：{enrich_result.get('message')}")
        
        except Exception as e:
            print(f"⚠️  Embeddings生成异常：{e}")
        
        enrich_time = time.time() - enrich_start
    
    total_time = ingest_time + enrich_time
    
    # ========== 构建返回消息 ==========
    message_lines = [
        f"✅ 批量入库完成：{brain_id}",
        f"   总episodes：{len(episodes)}个",
        f"   成功：{success_count}个",
        f"   失败：{len(failed)}个"
    ]
    
    if failed:
        message_lines.append(f"\n❌ 失败列表：")
        for fail in failed[:5]:  # 最多显示5个
            message_lines.append(f"   - Episode {fail['episode']}: {fail['error'][:50]}")
    
    message_lines.append(f"\n⏱️  入库耗时：{ingest_time:.1f}秒")
    
    if embeddings_generated:
        message_lines.append(f"   Embeddings生成：{enrich_time:.1f}秒")
        message_lines.append(f"   总耗时：{total_time:.1f}秒")
    
    return {
        "status": "success",
        "brain_id": brain_id,
        "total_episodes": len(episodes),
        "success_count": success_count,
        "failed": failed,
        "embeddings_generated": embeddings_generated,
        "total_time_seconds": total_time,
        "message": "\n".join(message_lines)
    }


__all__ = ['nisb_corpus_batch_ingest']

