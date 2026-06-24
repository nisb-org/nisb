#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证处理器
处理：验证JSON数据的有效性
"""

from .base import BaseProcessor


class ValidationProcessor(BaseProcessor):
    """
    验证处理器
    
    功能：
    - 检查JSON格式
    - 验证必填字段
    - 检查数据类型
    - 提供详细的错误报告
    """
    
    def execute(self, args: dict) -> dict:
        """执行验证"""
        
        errors = []
        warnings = []
        
        # ========== 验证L2数据 ==========
        if "L2_pattern" in args or any(k in args for k in ["opening_hooks", "transition_phrases"]):
            l2_validation = self._validate_l2(args)
            errors.extend(l2_validation["errors"])
            warnings.extend(l2_validation["warnings"])
        
        # ========== 验证L4数据 ==========
        if "l4_patterns_extracted" in args or "l4_patterns" in args:
            l4_validation = self._validate_l4(args)
            errors.extend(l4_validation["errors"])
            warnings.extend(l4_validation["warnings"])
        
        # ========== 返回结果 ==========
        return {
            "status": "validation_complete",
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "next_action": "ingest" if len(errors) == 0 else "fix_and_retry",
            "message": (
                f"✅ 验证完成\n"
                f"  错误：{len(errors)}个\n"
                f"  警告：{len(warnings)}个"
            )
        }
    
    
    def _validate_l2(self, args: dict) -> dict:
        """验证L2数据"""
        
        errors = []
        warnings = []
        
        l2_data = args.get("L2_pattern") or {}
        
        if not isinstance(l2_data, dict):
            errors.append("L2_pattern 必须是字典")
            return {"errors": errors, "warnings": warnings}
        
        # 检查四类模板
        for pattern_type in ["opening_hooks", "transition_phrases", "rhetorical_devices", "explanation_patterns"]:
            items = l2_data.get(pattern_type, [])
            
            if items and not isinstance(items, list):
                errors.append(f"{pattern_type} 必须是列表")
                continue
            
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"{pattern_type}[{i}] 必须是字典")
                    continue
                
                # 检查必要字段
                if "text" not in item and "content" not in item and "example" not in item:
                    errors.append(f"{pattern_type}[{i}] 缺少text/content/example字段")
        
        return {"errors": errors, "warnings": warnings}
    
    
    def _validate_l4(self, args: dict) -> dict:
        """验证L4数据"""
        
        errors = []
        warnings = []
        
        l4_data = args.get("l4_patterns_extracted") or args.get("l4_patterns", [])
        
        if not isinstance(l4_data, list):
            errors.append("l4_patterns_extracted 必须是列表")
            return {"errors": errors, "warnings": warnings}
        
        for i, pattern in enumerate(l4_data):
            if not isinstance(pattern, dict):
                errors.append(f"l4_patterns[{i}] 必须是字典")
                continue
            
            if "l4_name" not in pattern:
                errors.append(f"l4_patterns[{i}] 缺少 l4_name")
            
            if "rule" not in pattern:
                errors.append(f"l4_patterns[{i}] 缺少 rule")
            
            if "frequency_score" not in pattern:
                warnings.append(f"l4_patterns[{i}] 缺少 frequency_score（建议补齐）")
        
        return {"errors": errors, "warnings": warnings}

