#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简化版内存诊断（不依赖 tracemalloc，只统计对象数量）"""

import gc
import sys
import time
from collections import Counter

print("📊 Collecting garbage and taking baseline snapshot...")
gc.collect()

# 获取所有对象类型统计
def get_object_stats():
    counts = Counter()
    for obj in gc.get_objects():
        counts[type(obj).__name__] += 1
    return counts

baseline = get_object_stats()
print(f"✅ Baseline: {len(gc.get_objects())} objects")

print("\n⏳ Waiting 30 seconds (trigger some queries now)...")
try:
    time.sleep(30)
except KeyboardInterrupt:
    pass

gc.collect()
current = get_object_stats()
print(f"✅ Current: {len(gc.get_objects())} objects")

# 计算增长最多的对象类型
growth = {}
for obj_type, count in current.items():
    baseline_count = baseline.get(obj_type, 0)
    delta = count - baseline_count
    if delta > 0:
        growth[obj_type] = (delta, count)

print("\n" + "="*60)
print("🔥 Top 15 Object Growth (Type → +Count)")
print("="*60)
for i, (obj_type, (delta, total)) in enumerate(sorted(growth.items(), key=lambda x: -x[1][0])[:15], 1):
    print(f"{i:2d}. {obj_type:30s} → +{delta:6d} (total: {total})")

# 检查常见泄漏源
print("\n" + "="*60)
print("🔍 Leak Suspects:")
print("="*60)
suspects = {
    "dict": "Large dicts (likely qamap/embedding_cache)",
    "list": "Growing lists (likely evidence/chunks accumulation)",
    "str": "String accumulation (likely LLM responses not cleaned)",
    "function": "Closures not released (check decorators)",
    "cell": "Closure variables leaked",
}
for obj_type, hint in suspects.items():
    if obj_type in growth and growth[obj_type][0] > 1000:
        print(f"⚠️  {obj_type}: +{growth[obj_type][0]} → {hint}")

