#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus Ingest 处理器基类
"""

from abc import ABC, abstractmethod


class BaseProcessor(ABC):
    """所有入库处理器的基类"""
    
    @abstractmethod
    def execute(self, args: dict) -> dict:
        """
        执行处理
        
        Args:
            args: 处理参数字典
            
        Returns:
            {
                "status": "success" | "error",
                "message": "处理结果描述",
                ...其他字段
            }
        """
        raise NotImplementedError


def auto_detect_processor(args: dict) -> BaseProcessor:
    """
    根据args自动检测并返回合适的处理器
    
    路由逻辑：
    1. 如果有guide/template标记 → GuideProcessor
    2. 如果有validate/check标记 → ValidationProcessor
    3. 如果有staging/from_staging标记 → StagingIngestProcessor
    4. 如果有list_staging标记 → StagingIngestProcessor（列表模式）
    5. 默认 → DirectIngestProcessor（直接入库）
    """
    
    # 判断1：用户要看指导
    if args.get("guide") or args.get("template"):
        from .guide import GuideProcessor
        return GuideProcessor()
    
    # 判断2：用户要验证数据
    if args.get("validate") or args.get("check"):
        from .validation import ValidationProcessor
        return ValidationProcessor()
    
    # 判断3：用户要查看或处理staging文件
    if args.get("staging") or args.get("from_staging") or args.get("list_staging"):
        from .staging import StagingIngestProcessor
        return StagingIngestProcessor()
    
    # 默认：直接入库
    from .direct import DirectIngestProcessor
    return DirectIngestProcessor()

