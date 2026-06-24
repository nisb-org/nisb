#!/usr/bin/env python3
"""
NISB Doc Parser - 统一入口
Phase 6.1.2 模块化版本
"""

from typing import Dict
from tools.doc.doc_parser_pdf import parse_pdf
from tools.doc.doc_parser_docx import parse_docx
from tools.doc.doc_parser_md import parse_md
from tools.doc.doc_parser_txt import parse_txt


def parse_document(file_path: str, filetype: str) -> Dict:
    """统一的文档解析接口"""
    
    filetype = filetype.lower().strip()
    
    try:
        if filetype == "pdf":
            return parse_pdf(file_path)
        elif filetype == "docx":
            return parse_docx(file_path)
        elif filetype == "md":
            return parse_md(file_path)
        elif filetype == "txt":
            return parse_txt(file_path)
        else:
            raise ValueError(f"不支持的文件类型：{filetype}")
    
    except Exception as e:
        return {
            "text": "",
            "tables": [],
            "metadata": {},
            "error": str(e),
            "quality": {"error": True}
        }


def get_supported_formats() -> Dict:
    """获取支持的格式和相应的库"""
    
    from tools.doc.doc_parser_pdf import PDFPLUMBER_AVAILABLE, PYPDF_AVAILABLE
    from tools.doc.doc_parser_docx import DOCX_AVAILABLE
    
    return {
        "pdf": {
            "supported": PYPDF_AVAILABLE or PDFPLUMBER_AVAILABLE,
            "preferred": "pdfplumber" if PDFPLUMBER_AVAILABLE else "pypdf",
            "features": {
                "text": True,
                "tables": PDFPLUMBER_AVAILABLE,
                "metadata": True,
                "scanned_detection": PDFPLUMBER_AVAILABLE
            }
        },
        "docx": {
            "supported": DOCX_AVAILABLE,
            "method": "python-docx",
            "features": {
                "text": True,
                "tables": DOCX_AVAILABLE,
                "metadata": DOCX_AVAILABLE,
                "headers_footers": DOCX_AVAILABLE
            }
        },
        "md": {
            "supported": True,
            "method": "enhanced-markdown",
            "features": {
                "text": True,
                "tables": True,
                "metadata": True,
                "frontmatter": True,
                "toc": True,
                "code_blocks": True,
                "latex_formulas": True,
                "links": True
            }
        },
        "txt": {
            "supported": True,
            "method": "built-in",
            "features": {
                "text": True,
                "tables": False,
                "metadata": False
            }
        }
    }


def validate_extracted_content(result: Dict) -> Dict:
    """验证提取的内容质量"""
    
    MIN_CONTENT_LENGTH = 50
    
    text = result.get("text", "")
    quality = result.get("quality", {})
    
    issues = []
    
    if len(text) < MIN_CONTENT_LENGTH:
        issues.append(f"内容过短（{len(text)}字符）")
    
    if quality.get("error"):
        issues.append("提取失败")
    
    confidence = quality.get("confidence", 0)
    if confidence < 0.6:
        issues.append(f"信心度低（{confidence:.0%}）")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "statistics": {
            "text_length": len(text),
            "table_count": len(result.get("tables", [])),
            "confidence": confidence,
            "method": quality.get("method", "unknown")
        }
    }

