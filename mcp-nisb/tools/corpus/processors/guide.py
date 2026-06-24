#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指导处理器
处理：提供JSON模板和字段说明
"""

from .base import BaseProcessor


class GuideProcessor(BaseProcessor):
    """
    指导处理器
    
    功能：
    - 提供标准的JSON模板
    - 解释各字段的含义
    - 给出示例
    """
    
    def execute(self, args: dict) -> dict:
        """返回指导信息"""
        
        data_type = args.get("type", "l2")
        
        if data_type == "l4":
            return self._guide_l4()
        else:  # 默认L2
            return self._guide_l2()
    
    
    def _guide_l2(self) -> dict:
        """L2指导"""
        
        template = {
            "episode_number": 311,
            "L2_pattern": {
                "opening_hooks": [
                    {
                        "timestamp": "00:05",
                        "text": "开场钩子内容",
                        "effectiveness_score": 0.95
                    }
                ],
                "transition_phrases": [
                    {
                        "timestamp": "12:03",
                        "text": "转折短语内容",
                        "effectiveness_score": 0.85
                    }
                ],
                "rhetorical_devices": [
                    {
                        "timestamp": "00:52",
                        "type": "对比",
                        "example": "修辞手法内容",
                        "effectiveness_score": 0.92
                    }
                ],
                "explanation_patterns": [
                    {
                        "concept": "概念名称",
                        "simple_explanation": "通俗解释内容",
                        "timestamp": "16:27",
                        "effectiveness_score": 0.88
                    }
                ]
            }
        }
        
        explanation = {
            "episode_number": "视频集数（必填）",
            "L2_pattern": {
                "opening_hooks": "开场钩子列表",
                "transition_phrases": "转折短语列表",
                "rhetorical_devices": "修辞手法列表",
                "explanation_patterns": "解释模式列表"
            },
            "timestamp": "时间戳格式：MM:SS",
            "effectiveness_score": "有效性评分：0.0-1.0",
            "text/example": "具体内容",
            "concept/simple_explanation": "概念和解释"
        }
        
        return {
            "status": "guide_provided",
            "type": "l2",
            "template": template,
            "field_explanation": explanation,
            "message": "【L2模板指导】\n请按照上面的template字段填写数据"
        }
    
    
    def _guide_l4(self) -> dict:
        """L4指导"""
        
        template = {
            "episode_id": "ep311",
            "title": "视频标题",
            "duration_minutes": 27.03,
            "l4_patterns_extracted": [
                {
                    "l4_id": "L4-1",
                    "l4_name": "L4-1: 悬念对比开场法",
                    "rule": "开场通过对比悬念制造认知冲击",
                    "frequency_score": 0.94,
                    "confidence": 0.94,
                    "evidence_segments": [
                        {
                            "timestamp": "00:05-00:13",
                            "content": "证据内容"
                        }
                    ]
                }
            ]
        }
        
        explanation = {
            "episode_id": "视频ID（格式：epXXX）",
            "l4_id": "L4方法论ID（L4-1到L4-7）",
            "l4_name": "L4方法论名称",
            "rule": "核心规则描述",
            "frequency_score": "该L4在episode中的频率（0.0-1.0）",
            "confidence": "检测置信度（0.0-1.0）",
            "evidence_segments": "支撑证据片段"
        }
        
        return {
            "status": "guide_provided",
            "type": "l4",
            "template": template,
            "field_explanation": explanation,
            "message": "【L4模板指导】\n请按照上面的template字段填写数据"
        }

