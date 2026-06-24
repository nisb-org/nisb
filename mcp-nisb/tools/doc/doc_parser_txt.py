#!/usr/bin/env python3
"""
TXT文档解析模块 - Phase 6.1.2
"""

from typing import Dict


def parse_txt(file_path: str) -> Dict:
    """优化的TXT文本提取"""
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        lines = content.split('\n')
        cleaned_lines = [line.rstrip() for line in lines]
        
        final_lines = []
        prev_empty = False
        for line in cleaned_lines:
            if not line.strip():
                if not prev_empty:
                    final_lines.append(line)
                prev_empty = True
            else:
                final_lines.append(line)
                prev_empty = False
        
        final_text = '\n'.join(final_lines).strip()
        
        non_empty_lines = len([l for l in final_lines if l.strip()])
        
        return {
            "text": final_text,
            "tables": [],
            "metadata": {
                "encoding": "utf-8",
                "total_lines": len(final_lines),
                "non_empty_lines": non_empty_lines
            },
            "quality": {
                "confidence": 0.99,
                "method": "optimized-txt"
            }
        }
    
    except Exception as e:
        raise Exception(f"TXT解析失败：{str(e)}")

