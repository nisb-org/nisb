#!/usr/bin/env python3
"""
Markdown文档解析模块 - Phase 6.1.2（增强版 - 修正TOML导入）

特性：
  ✅ YAML/TOML前置元数据解析（使用Python 3.11+ tomllib）
  ✅ 目录（TOC）自动识别
  ✅ 代码块标记和提取
  ✅ 表格自动识别
  ✅ 数学公式（LaTeX）标记
  ✅ 链接和引用收集

更新日期：2025-11-03
"""

import re
from typing import Dict, List, Optional

# ============================================================
# 配置常量
# ============================================================

MARKDOWN_PATTERNS = {
    "heading": r"^(#{1,6})\s+(.+)$",
    "code_block": r"``````",
    "link": r"\[([^\]]+)\]\(([^\)]+)\)",
    "image": r"!\[([^\]]*)\]\(([^\)]+)\)",
    "table": r"\|(.+)\|",
    "latex": r"\$\$?(.*?)\$\$?",
    "bold": r"\*\*(.+?)\*\*",
    "italic": r"\*(.+?)\*",
    "strikethrough": r"~~(.+?)~~",
    "horizontal_rule": r"^(---|\*\*\*|___)",
    "blockquote": r"^>\s+(.+)$",
    "unordered_list": r"^[\*\-\+]\s+(.+)$",
    "ordered_list": r"^\d+\.\s+(.+)$"
}


# ============================================================
# 前置元数据解析（修正版 - 优先使用tomllib）
# ============================================================

def _parse_frontmatter(text: str) -> tuple:
    """解析YAML/TOML前置元数据（修正：使用tomllib）"""
    
    metadata = {}
    content = text
    
    # ===== 优先解析YAML =====
    yaml_match = re.match(r"^---\n(.*?)\n---\n", text, re.MULTILINE | re.DOTALL)
    if yaml_match:
        try:
            import yaml
            metadata = yaml.safe_load(yaml_match.group(1))
            content = text[yaml_match.end():]
            return metadata, content
        except Exception as e:
            print(f"[WARN] YAML解析失败：{e}，尝试TOML...")
    
    # ===== 其次解析TOML（使用Python 3.11+ tomllib）=====
    toml_match = re.match(r"^\+\+\+\n(.*?)\n\+\+\+\n", text, re.MULTILINE | re.DOTALL)
    if toml_match:
        try:
            # ⭐ 修正：Python 3.11+ 内置tomllib
            import tomllib
            metadata = tomllib.loads(toml_match.group(1))
            content = text[toml_match.end():]
            return metadata, content
        except ImportError:
            # ⭐ 降级方案：Python < 3.11
            try:
                import toml
                metadata = toml.loads(toml_match.group(1))
                content = text[toml_match.end():]
                return metadata, content
            except Exception as e:
                print(f"[WARN] TOML解析失败：{e}，使用纯文本模式")
        except Exception as e:
            print(f"[WARN] TOML解析失败：{e}，使用纯文本模式")
    
    return metadata, content


# ============================================================
# 结构提取
# ============================================================

def _extract_headings(text: str) -> List[Dict]:
    """提取标题层级（用于生成TOC）"""
    
    headings = []
    for line in text.split('\n'):
        match = re.match(MARKDOWN_PATTERNS["heading"], line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            headings.append({
                "level": level,
                "title": title,
                "anchor": title.lower().replace(" ", "-")
            })
    
    return headings


def _extract_code_blocks(text: str) -> List[Dict]:
    """提取代码块"""
    
    blocks = []
    for match in re.finditer(MARKDOWN_PATTERNS["code_block"], text, re.DOTALL):
        language = match.group(1) or "plaintext"
        code = match.group(2).strip()
        blocks.append({
            "language": language,
            "code": code,
            "lines": len(code.split('\n'))
        })
    
    return blocks


def _extract_links(text: str) -> List[Dict]:
    """提取链接和引用"""
    
    links = []
    
    # 普通链接
    for match in re.finditer(MARKDOWN_PATTERNS["link"], text):
        text_content = match.group(1)
        url = match.group(2)
        links.append({
            "type": "link",
            "text": text_content,
            "url": url
        })
    
    # 图片
    for match in re.finditer(MARKDOWN_PATTERNS["image"], text):
        alt_text = match.group(1)
        url = match.group(2)
        links.append({
            "type": "image",
            "alt": alt_text,
            "url": url
        })
    
    return links


def _extract_tables(text: str) -> List[Dict]:
    """提取Markdown表格"""
    
    tables = []
    lines = text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 识别表格开始（包含 | 的行）
        if '|' in line and i + 1 < len(lines) and '---' in lines[i + 1]:
            table_data = {"rows": []}
            
            # 解析表头
            header = [cell.strip() for cell in line.split('|')[1:-1]]
            if header:
                table_data["rows"].append(header)
            
            # 跳过分隔符
            i += 2
            
            # 解析表体
            while i < len(lines) and '|' in lines[i]:
                row = [cell.strip() for cell in lines[i].split('|')[1:-1]]
                if row and any(row):
                    table_data["rows"].append(row)
                i += 1
            
            if len(table_data["rows"]) > 1:
                tables.append(table_data)
            
            continue
        
        i += 1
    
    return tables


def _extract_latex_formulas(text: str) -> List[Dict]:
    """提取LaTeX数学公式"""
    
    formulas = []
    
    # $$ 公式 $$
    for match in re.finditer(r"\$\$(.*?)\$\$", text, re.DOTALL):
        formulas.append({
            "type": "block",
            "formula": match.group(1).strip()
        })
    
    # $ 公式 $
    for match in re.finditer(r"(?<!\$)\$(?!\$)([^\$]+)\$(?!\$)", text):
        formula = match.group(1).strip()
        if len(formula) > 1:  # 避免单个字符
            formulas.append({
                "type": "inline",
                "formula": formula
            })
    
    return formulas


# ============================================================
# 统计信息
# ============================================================

def _calculate_statistics(text: str, headings: List[Dict], 
                         code_blocks: List[Dict], 
                         tables: List[Dict]) -> Dict:
    """计算文档统计信息"""
    
    lines = text.split('\n')
    words = len(text.split())
    
    return {
        "lines": len(lines),
        "words": words,
        "characters": len(text),
        "paragraphs": len([l for l in lines if l.strip() and not l.startswith('#')]),
        "headings": len(headings),
        "code_blocks": len(code_blocks),
        "tables": len(tables),
        "max_heading_level": max([h["level"] for h in headings]) if headings else 0
    }


# ============================================================
# 主解析函数
# ============================================================

def parse_md(file_path: str) -> Dict:
    """完整的Markdown文档解析"""
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # ===== 前置元数据 =====
        frontmatter, body_text = _parse_frontmatter(content)
        
        # ===== 结构提取 =====
        headings = _extract_headings(body_text)
        code_blocks = _extract_code_blocks(body_text)
        links = _extract_links(body_text)
        tables = _extract_tables(body_text)
        formulas = _extract_latex_formulas(body_text)
        
        # ===== 统计信息 =====
        stats = _calculate_statistics(body_text, headings, code_blocks, tables)
        
        # ===== 清理文本（去除多余空行） =====
        lines = body_text.split('\n')
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
        
        return {
            "text": '\n'.join(final_lines).strip(),
            "tables": tables,
            "metadata": {
                "frontmatter": frontmatter,
                "title": frontmatter.get("title", ""),
                "author": frontmatter.get("author", ""),
                "tags": frontmatter.get("tags", []),
                "encoding": "utf-8"
            },
            "structure": {
                "headings": headings,
                "code_blocks": code_blocks,
                "links": links,
                "formulas": formulas
            },
            "statistics": stats,
            "quality": {
                "confidence": 0.99,
                "method": "enhanced-markdown",
                "has_tables": len(tables) > 0,
                "has_code": len(code_blocks) > 0,
                "has_formulas": len(formulas) > 0
            }
        }
    
    except Exception as e:
        raise Exception(f"Markdown解析失败：{str(e)}")

