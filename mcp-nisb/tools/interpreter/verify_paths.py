#!/usr/bin/env python3
"""
✅ Phase 5.1修复：移除硬编码/data/documents，改为动态获取
"""
import sys
sys.path.insert(0, '/srv')

print("=" * 70)
print("NISB路径验证脚本")
print("=" * 70)

user_id = 'lc_68743b4c94dfb248f77f6e2e'

# 测试1
print("\n【1】core.storage 模块")
try:
    from core.storage import get_user_base_path, ensure_user_directory
    print("✅ 导入成功")
    ensure_user_directory(user_id, None, None)
    base_path = get_user_base_path(user_id)
    print(f"✅ base_path: {base_path}")
except Exception as e:
    print(f"❌ 错误: {e}")

# 测试2
print("\n【2】filesystem.config")
try:
    from tools.filesystem.config import get_agent_files_path
    agent_path = get_agent_files_path(user_id)
    print(f"✅ agent_path: {agent_path}")
    
    import os
    from pathlib import Path
    charts = Path(agent_path) / "charts"
    print(f"✅ charts存在: {charts.exists()}")
    
    if charts.exists():
        files = list(charts.iterdir())
        print(f"✅ 文件数: {len(files)}")
        for f in files:
            print(f"  - {f.name}")
except Exception as e:
    print(f"❌ 错误: {e}")

# 测试3
print("\n【3】SecureNISBKernel")
try:
    from tools.interpreter.secure_kernel import SecureNISBKernel
    # ✅ 修复：移除硬编码/data/documents，改为动态获取
    from core.user_context import get_user_ctx
    base_path = get_user_ctx().base
    
    kernel = SecureNISBKernel(user_id, base_path)
    print(f"✅ user_root: {kernel.user_root}")
    print(f"✅ 存在: {kernel.user_root.exists()}")
    charts = kernel.user_root / "charts"
    if charts.exists():
        print(f"✅ charts文件: {len(list(charts.iterdir()))}")
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

# 测试4
print("\n【4】nisb_file_list")
try:
    from tools.filesystem.search import nisb_file_list
    result = nisb_file_list({
        'path': 'charts',
        'user_id': user_id
    })
    print(f"✅ 返回: {result.get('message', result.get('text', 'N/A'))[:200]}")
except Exception as e:
    print(f"❌ 错误: {e}")

print("\n" + "=" * 70)

