#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内存泄漏诊断工具（运行后等待 30 秒再按 Ctrl+C 查看报告）"""

import gc
import tracemalloc
import time
import sys
from pathlib import Path

# 启动内存追踪
tracemalloc.start()

# 模拟你的工作流：导入所有工具模块
sys.path.insert(0, '/opt/mcp-gateway/mcp-nisb')
sys.path.insert(0, '/srv')

print("📊 Loading all NISB modules...")
from tools.doc import nisb_doc_search_hybrid, nisb_library_doc_evidence
from tools.doc.analysis.qascope import nisb_qa_scope_ask
from tools.rss import nisb_rss_semantic_search

# 强制触发一次完整 GC
gc.collect()
snapshot1 = tracemalloc.take_snapshot()
print("✅ Baseline snapshot taken")

print("\n⏳ Simulating 30s workload (press Ctrl+C to stop early)...")
try:
    time.sleep(30)
except KeyboardInterrupt:
    pass

gc.collect()
snapshot2 = tracemalloc.take_snapshot()

# 对比内存增长
top_stats = snapshot2.compare_to(snapshot1, 'lineno')

print("\n" + "="*60)
print("🔥 Top 10 Memory Growth Sources (KB)")
print("="*60)
for i, stat in enumerate(top_stats[:10], 1):
    frame = stat.traceback[0]
    size_kb = stat.size_diff / 1024
    print(f"{i}. {frame.filename}:{frame.lineno} → +{size_kb:.1f} KB")
    print(f"   Count: {stat.count_diff:+d} objects")

print("\n" + "="*60)
print("📈 Current Memory Snapshot (Top 10)")
print("="*60)
for i, stat in enumerate(snapshot2.statistics('lineno')[:10], 1):
    frame = stat.traceback[0]
    size_mb = stat.size / (1024 * 1024)
    print(f"{i}. {frame.filename}:{frame.lineno} → {size_mb:.2f} MB")

