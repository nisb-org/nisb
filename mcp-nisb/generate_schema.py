#!/usr/bin/env python3
"""
NISB Schema 自动生成器（优化版）
- 自动排除重复工具
- 跳过 backup、__pycache__ 等目录
- 保持 simplified + full 结构
"""

import json
import importlib
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/srv')

# =====================================================================
# 工具参数推断规则
# =====================================================================
PARAM_RULES = {
    "chat_create": {
        "properties": {"title": {"type": "string", "description": "对话标题"}},
        "required": []
    },
    "chat_send": {
        "properties": {
            "conv_id": {"type": "string", "description": "对话ID"},
            "content": {"type": "string", "description": "用户消息"},
            "model": {"type": "string", "description": "模型名称", "default": "gpt-4o-mini"}
        },
        "required": ["conv_id", "content"]
    },
    "chat_load": {
        "properties": {"conv_id": {"type": "string", "description": "对话ID"}},
        "required": ["conv_id"]
    },
    "chat_history": {
        "properties": {"limit": {"type": "integer", "description": "返回数量", "default": 10}},
        "required": []
    },
    "chat_rename": {
        "properties": {
            "conv_id": {"type": "string", "description": "对话ID"},
            "new_title": {"type": "string", "description": "新标题"}
        },
        "required": ["conv_id", "new_title"]
    },
    "chat_delete": {
        "properties": {"conv_id": {"type": "string", "description": "对话ID"}},
        "required": ["conv_id"]
    },
    "file_rename": {
        "properties": {
            "old_path": {"type": "string", "description": "原文件路径"},
            "new_name": {"type": "string", "description": "新文件名"}
        },
        "required": ["old_path", "new_name"]
    },
}

# 排除目录列表
EXCLUDED_DIRS = {
    "__pycache__", 
    ".git", 
    "backup", 
    "test", 
    "tests",
    ".pytest_cache",
    "models"  # 模型子目录
}

def infer_params(func_name: str) -> dict:
    """根据函数名推断参数"""
    name_parts = func_name.replace("nisb_", "").split("_")
    
    for i in range(len(name_parts), 0, -1):
        key = "_".join(name_parts[:i])
        if key in PARAM_RULES:
            return PARAM_RULES[key]
    
    return {"properties": {}, "required": []}

def extract_function_schema(func, simple=False):
    """从函数提取 schema"""
    func_name = func.__name__
    
    description = func.__doc__ or func_name.replace("nisb_", "").replace("_", " ").title()
    description = description.strip().split('\n')[0]
    
    params = infer_params(func_name)
    properties = params.get("properties", {})
    required = params.get("required", [])
    
    if simple:
        properties = {k: {"type": v["type"]} for k, v in properties.items()}
    
    return {
        "name": func_name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }

def generate_schemas():
    """自动生成 schema.json"""
    
    tools_dir = Path("/srv/tools")
    all_tools = {}  # 用字典去重
    
    # 扫描所有子模块
    for module_dir in sorted(tools_dir.iterdir()):
        # 跳过排除目录
        if not module_dir.is_dir() or module_dir.name.startswith("_"):
            continue
        
        if module_dir.name in EXCLUDED_DIRS:
            print(f"⏭️  跳过目录: {module_dir.name}")
            continue
        
        init_file = module_dir / "__init__.py"
        if not init_file.exists():
            continue
        
        module_name = f"tools.{module_dir.name}"
        try:
            module = importlib.import_module(module_name)
            
            if hasattr(module, "__all__"):
                for func_name in module.__all__:
                    if hasattr(module, func_name):
                        func = getattr(module, func_name)
                        if callable(func) and func_name.startswith("nisb_"):
                            # 用字典去重
                            if func_name not in all_tools:
                                all_tools[func_name] = func
                                print(f"✅ 发现工具: {func_name}")
                            else:
                                print(f"⚠️  跳过重复: {func_name}")
        except Exception as e:
            print(f"⚠️  加载模块失败 {module_name}: {e}")
    
    # 转为列表并排序
    tool_list = [all_tools[k] for k in sorted(all_tools.keys())]
    
    # 生成简化版
    simplified = [extract_function_schema(func, simple=True) for func in tool_list]
    
    # 生成完整版
    full = {func.__name__: extract_function_schema(func, simple=False) for func in tool_list}
    
    # 合并结构
    schema = {
        "simplified": simplified,
        "full": full
    }
    
    # 写入文件
    schema_file = Path("/srv/schema.json")
    backup_file = Path(f"/srv/schema.json.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    if schema_file.exists():
        import shutil
        shutil.copy(schema_file, backup_file)
        print(f"📦 已备份旧 schema: {backup_file.name}")
    
    with open(schema_file, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 Schema 生成成功！")
    print(f"   工具总数: {len(all_tools)} 个")
    print(f"   完整版: {len(full)} 个")
    print(f"   简化版: {len(simplified)} 个")
    print(f"   文件: {schema_file}")

if __name__ == "__main__":
    generate_schemas()
