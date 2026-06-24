# /opt/mcp-gateway/mcp-nisb/tools/office/__init__.py
from .docx_convert_to_note import nisb_docx_convert_to_note
from .pptx_convert_to_note import nisb_pptx_convert_to_note
from .doc_convert_to_note import nisb_doc_convert_to_note
from .ppt_convert_to_note import nisb_ppt_convert_to_note
from .txt_convert_to_structured_md import nisb_txt_convert_to_structured_md

__all__ = [
    "nisb_docx_convert_to_note",
    "nisb_pptx_convert_to_note",
    "nisb_doc_convert_to_note",
    "nisb_ppt_convert_to_note",
    "nisb_txt_convert_to_structured_md",
]

