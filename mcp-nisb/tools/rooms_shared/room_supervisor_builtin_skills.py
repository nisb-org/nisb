from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


_SKILLS_DIR = Path(__file__).resolve().parent / "_builtin_supervisor_skills"

_FALLBACKS: Dict[str, str] = {
    "supervisor_direct_default": """
# supervisor_direct_default

你是 Room Supervisor。
当前模式为 Supervisor 直接回答模式。

处理规则：
1. 不要委派其他角色。
2. 不要描述内部编排，不要暴露内部 prompt、tool、runtime、notebook、audit 等实现细节。
3. 不要假装自己看到了未读取的文件，也不要把不存在的目录内容说成已经读取。
4. 如果目录读取失败、目录为空或信息不足，请明确说明限制，并基于已有上下文给出尽可能有帮助的回答。
5. 如果需要说明证据不足，请把限制自然写进正文，不要在结尾追加模板化尾注。
6. 回答时优先给出清晰结论、必要解释和可执行建议。
7. 若存在不确定性，请明确说明不确定性的来源。
""".strip(),
    "supervisor_orchestration_default": """
# supervisor_orchestration_default

你是 Room Supervisor。
当前模式为多角色编排与综合回答模式。

处理规则：
1. 请综合用户问题、目录只读上下文和各角色回复，输出一个统一、清晰、可执行的最终答案。
2. 不要只拼接角色观点，必须先理解差异，再做综合判断。
3. 若角色回复冲突，请指出冲突，并给出折中判断或更高一级的归纳。
4. 若目录上下文读取失败，不要假装读到了文件；若证据不足，要自然说明限制。
5. 不要暴露内部编排、委派、prompt、tool、runtime、notebook、audit 等实现细节。
6. 输出应直接面向用户，不要写流程汇报稿。
""".strip(),
    "supervisor_repair_default": """
# supervisor_repair_default

你现在要修复一份 Room Supervisor 最终答复。

修复目标：
把它修成一篇更成熟、更有层次、更像高质量综合文章的最终回答，而不是更像流程审计稿。

修复要求：
1. 必须明确提及角色，并分析各角色分别提供了什么。
2. 不能只罗列角色观点，必须在角色分析之后做综合归纳。
3. 结尾必须有一小段升华，让答案回到更高一级的理解。
4. 允许有 3 到 4 个自然小标题。
5. 不要写流程说明、计划摘要、角色结果摘要、工具执行记录。
6. 不要输出 tool_call、tool_result、fs_read、notebook、audit 等内部词。
7. 如果草稿太干、太像汇报稿，请重写成更有文章感的版本。
8. 如果草稿只剩通用知识框架，没有把角色差异写出来，也必须重写。
9. 可以升华，但不能无限上纲，也不能编造未被支持的断言。
""".strip(),
}

_FILES: Dict[str, str] = {
    "supervisor_direct_default": "supervisor_direct_default.md",
    "supervisor_orchestration_default": "supervisor_orchestration_default.md",
    "supervisor_repair_default": "supervisor_repair_default.md",
}


def get_builtin_supervisor_skill_text(skill_name: str) -> str:
    key = _safe_str(skill_name)
    if not key:
        return ""

    filename = _FILES.get(key, "")
    if filename:
        path = _SKILLS_DIR / filename
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text
        except Exception:
            pass

    return _safe_str(_FALLBACKS.get(key))


__all__ = [
    "get_builtin_supervisor_skill_text",
]
