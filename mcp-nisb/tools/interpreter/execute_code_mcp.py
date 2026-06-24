#!/usr/bin/env python3
"""
NISB MCP工具：nisb_execute_code
Docker 沙箱版（保持原有路径与图片处理逻辑）
- 工作目录：/data/users/{uid}/agent_files/tmp/default
- 图表目录：/data/users/{uid}/agent_files/charts
- 图片命名：chart_时间戳_哈希.png（与原版保持一致）
"""

import json
import traceback
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from .container_manager import (
    get_or_create_container,
    execute_in_container,
    get_container_stats,
)
from .code_fixer import get_fix_suggestions


def _collect_recent_files(dirs: List[Path], since_ts: float) -> List[str]:
    out: List[str] = []
    for d in dirs:
        if not d.exists():
            continue
        for f in d.glob("*"):
            try:
                if f.is_file() and (f.stat().st_mtime >= since_ts):
                    out.append(str(f))
            except Exception:
                pass
    return out


def nisb_execute_code(args: dict) -> dict:
    """MCP工具入口：执行安全Python代码（Docker 沙箱）"""
    code = (args.get("code") or "").strip()
    language = args.get("language", "python")
    timeout = int(args.get("timeout", 30))
    user_id = args.get("user_id", "user_001")
    email = args.get("email")
    name = args.get("name")
    use_llm_fixer = bool(args.get("use_llm_fixer", False))

    # ⚠️ 测试阶段：强制开启网络，验证容器是否能够访问外网
    # 测试通过后，请改回：network_enabled = bool(args.get("network", False))
    #network_enabled = True
    network_enabled = bool(args.get("network", False))

    max_output_kb = int(args.get("max_output_kb", 256))

    if not code:
        msg = "❌ 错误：代码不能为空"
        return {
            "success": False,
            "output": "",
            "error": "Error: 代码不能为空",
            "message": msg,
            "text": msg,
        }

    if language != "python":
        msg = f"❌ 错误：仅支持Python（当前: {language}）"
        return {
            "success": False,
            "output": "",
            "error": f"Error: 仅支持Python，当前语言: {language}",
            "message": msg,
            "text": msg,
        }

    start_time = datetime.now()
    start_ts = start_time.timestamp()

    # 使用与原架构一致的 base_path
    from core.user_context import get_user_ctx

    base_path = Path(get_user_ctx().base)

    # ⭐ 与原来的 SecureNISBKernel 行为对齐
    work_dir = base_path / "agent_files" / "tmp" / "default"
    charts_dir = base_path / "agent_files" / "charts"
    work_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    # ⭐ 时间戳格式与原版保持一致：YYYYMMDD_HHMMSS
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        # 获取或创建执行容器
        container_name = get_or_create_container(user_id, base_path, network_enabled)

        # 在容器中执行代码
        result = execute_in_container(container_name, code, work_dir, timeout)

        # 输出截断
        def trim(s: str) -> str:
            lim = max(1, max_output_kb) * 1024
            b = (s or "").encode("utf-8", errors="ignore")
            return b[:lim].decode("utf-8", errors="ignore")

        if "output" in result:
            result["output"] = trim(result.get("output", ""))
        if "error" in result and result["error"]:
            result["error"] = trim(result.get("error", ""))

        # ⭐⭐⭐ 处理生成的图片文件：扫描 tmp/default 下本次执行后新生成的图片
        message_suffix = ""
        image_extensions = ["*.png", "*.jpg", "*.jpeg", "*.svg"]

        print(f"[DEBUG] 开始扫描图片，工作目录: {work_dir}，时间阈值: {start_ts}")

        for ext in image_extensions:
            for img_file in work_dir.glob(ext):
                try:
                    file_mtime = img_file.stat().st_mtime
                    print(
                        f"[DEBUG] 检查文件: {img_file.name}, "
                        f"mtime={file_mtime}, start_ts={start_ts}"
                    )

                    if file_mtime >= start_ts:
                        # ⭐ 命名格式与原版保持一致：chart_时间戳_哈希.扩展名
                        file_hash = hashlib.md5(img_file.read_bytes()).hexdigest()[:8]
                        new_filename = f"chart_{timestamp}_{file_hash}{img_file.suffix}"
                        dest = charts_dir / new_filename

                        # 复制文件（不是移动，保留原始文件供调试）
                        shutil.copy(str(img_file), str(dest))

                        # ⭐ 在消息中添加 Markdown 图片引用
                        message_suffix += (
                            "\n\n📊 图表已生成并保存\n\n"
                            f"![图表](agent_files/charts/{new_filename})"
                        )

                        print(
                            f"[INFO] 图片已复制: {img_file.name} -> {new_filename}"
                        )
                    else:
                        print(f"[DEBUG] 跳过旧文件: {img_file.name}")

                except Exception as e:
                    print(f"[WARN] 图片处理失败: {img_file}, 错误: {e}")
                    import traceback as tb

                    print(tb.format_exc())

        # 收集工件（可选调试用）
        artifacts = _collect_recent_files([work_dir, charts_dir], start_ts)

        execution_time = (datetime.now() - start_time).total_seconds()
        result["execution_time"] = round(execution_time, 3)

        # 组装 message（尽量保持原有格式）
        if result.get("success"):
            message = (
                "✅ 代码执行成功（Docker 沙箱）\n\n输出：\n"
                f"{result.get('output', '')}{message_suffix}\n\n"
                f"⏱️  执行时间: {result['execution_time']:.2f}秒"
            )
            if network_enabled:
                message += "\n🌐 网络访问：已启用"
            else:
                message += "\n🔒 网络访问：已禁用"
        else:
            message = f"❌ 执行失败\n\n错误：\n{result.get('error', '')}"
            try:
                message += get_fix_suggestions(
                    result.get("error", ""), code, use_llm=use_llm_fixer
                )
            except Exception as fix_error:
                print(f"[WARN] 修复建议生成失败: {fix_error}")

        _log_execution(
            user_id=user_id,
            code=code,
            result=result,
            execution_time=execution_time,
        )

        return {
            "success": bool(result.get("success")),
            "output": result.get("output", ""),
            "error": result.get("error"),
            "execution_time": execution_time,
            "artifacts": artifacts,
            "message": message,
            "text": message,
        }

    except Exception as e:
        error_msg = (
            "❌ 代码解释器内部错误\n\n"
            f"{str(e)}\n\n{traceback.format_exc()}"
        )
        _log_execution(
            user_id=user_id,
            code=code,
            result={"success": False, "error": str(e)},
            execution_time=0,
        )
        return {
            "success": False,
            "output": "",
            "error": error_msg,
            "message": error_msg,
            "text": error_msg,
        }


def nisb_interpreter_stats(args: dict) -> dict:
    """调试工具：查看容器状态"""
    stats = get_container_stats()
    return {
        "status": "success",
        **stats,
        "message": f"📊 当前活跃容器: {stats['active_containers']} 个",
    }


def _log_execution(user_id: str, code: str, result: dict, execution_time: float) -> None:
    """记录执行日志"""
    try:
        from core.user_context import get_user_ctx

        base_path = Path(get_user_ctx().base)
        log_dir = base_path / "storage" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"interpreter_{datetime.now().strftime('%Y-%m-%d')}.jsonl"

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "code_preview": code[:200],
            "code_length": len(code),
            "success": bool(result.get("success")),
            "execution_time": execution_time,
            "output_length": len(result.get("output", "")),
            "error_type": type(result.get("error", "")).__name__
            if not result.get("success")
            else None,
            "error_preview": (
                result.get("error", "")[:500]
                if not result.get("success")
                else None
            ),
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[WARN] 日志记录失败: {e}")


__all__ = ["nisb_execute_code", "nisb_interpreter_stats"]


# ✅ 自测入口：直接在后端容器里跑本文件，验证是否真的能联网
if __name__ == "__main__":
    from pprint import pprint

    test_code = """
import requests

print("开始请求 httpbin.org/ip ...")
resp = requests.get("https://httpbin.org/ip", timeout=5)
print("STATUS:", resp.status_code)
print("BODY:", resp.text[:200])
"""

    result = nisb_execute_code(
        {
            "code": test_code,
            "language": "python",
            "timeout": 20,
            "user_id": "test_user",
            "network": True,  # 当前被强制 True，这里只是语义对齐
        }
    )
    pprint(result)

