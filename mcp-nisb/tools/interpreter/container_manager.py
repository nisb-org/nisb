#!/usr/bin/env python3
"""
Docker 容器生命周期管理器（NISB 代码执行沙箱）
- 每个用户一个长期执行容器（nisb-exec-{user_id}）
- 工作目录固定：/data/users/{uid}/agent_files/tmp/default
- /tmp 映射到同一目录，方便 Matplotlib 保存图片
- 自动对所有打开的 Matplotlib 图形执行 savefig，生成 /tmp/auto_plot_*.png
"""

import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict
import threading

# 全局容器注册表
_containers: Dict[str, dict] = {}
_lock = threading.Lock()

# 容器空闲超时（秒）
CONTAINER_IDLE_TIMEOUT = 600  # 10 分钟


def _cleanup_idle_containers() -> None:
    """后台清理空闲容器"""
    while True:
        time.sleep(60)
        with _lock:
            now = time.time()
            to_remove = []
            for user_id, info in list(_containers.items()):
                last_used = info.get("last_used", now)
                if now - last_used > CONTAINER_IDLE_TIMEOUT:
                    container_name = info["name"]
                    try:
                        subprocess.run(
                            ["docker", "rm", "-f", container_name],
                            capture_output=True,
                            timeout=5,
                        )
                        print(
                            f"[INFO container] 已清理空闲容器: {container_name} "
                            f"(用户: {user_id})"
                        )
                        to_remove.append(user_id)
                    except Exception as e:
                        print(f"[WARN container] 清理容器失败: {e}")

            for user_id in to_remove:
                _containers.pop(user_id, None)


# 启动后台清理线程（守护线程）
_cleanup_thread = threading.Thread(
    target=_cleanup_idle_containers, daemon=True
)
_cleanup_thread.start()


def _get_host_path(container_path: Path) -> Path:
    """
    将容器内路径转换为宿主机路径

    容器内：/data/users/xxx/agent_files/...
    宿主机：/opt/nisb-data/users/xxx/agent_files/...
    """
    container_path_str = str(container_path)
    if container_path_str.startswith("/data"):
        host_path_str = container_path_str.replace("/data", "/opt/nisb-data", 1)
        return Path(host_path_str)
    return container_path

def get_or_create_container(
    user_id: str, base_path: Path, network_enabled: bool
) -> str:
    """获取或创建用户的执行容器（自动检测网络模式变化）"""

    # 所有地方统一用这个名字
    container_name = f"nisb-exec-{user_id.replace('_', '-')}"
    
    # 期望的网络模式
    expected_network = "bridge" if network_enabled else "none"

    with _lock:
        # 1）如果内存里有记录，尝试复用
        if user_id in _containers:
            info = _containers[user_id]

            try:
                # 检查容器是否在运行
                result = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                
                if result.returncode == 0 and result.stdout.strip() == "true":
                    # ⭐ 检查网络模式是否匹配
                    network_result = subprocess.run(
                        ["docker", "inspect", "-f", "{{.HostConfig.NetworkMode}}", container_name],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    
                    current_network = network_result.stdout.strip()
                    
                    if current_network == expected_network:
                        # 网络模式匹配，复用容器
                        info["last_used"] = time.time()
                        print(f"[INFO container] 复用现有容器: {container_name} (network={current_network})")
                        return container_name
                    else:
                        # 网络模式不匹配，删除旧容器重建
                        print(
                            f"[INFO container] 网络模式变化（{current_network} -> {expected_network}），"
                            f"删除旧容器重建: {container_name}"
                        )
                        subprocess.run(
                            ["docker", "rm", "-f", container_name],
                            capture_output=True,
                            timeout=5,
                        )
                        _containers.pop(user_id, None)
                else:
                    print(
                        f"[WARN container] 容器不在运行状态，将重新创建: {container_name}"
                    )
            except Exception as e:
                print(f"[WARN container] 检查旧容器状态失败: {e}")

            # 如果容器不在运行或网络模式不匹配，删除并清理
            try:
                subprocess.run(
                    ["docker", "rm", "-f", container_name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                print(f"[INFO container] 已删除旧容器: {container_name}")
            except Exception as e:
                print(f"[WARN container] 删除旧容器失败: {e}")

            _containers.pop(user_id, None)

        # 2）进程重启后 _containers 清空，但旧容器仍然可能存在
        #    这里无条件尝试删除一次同名容器，避免 name conflict (code=125)
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            print(f"[INFO container] 启动前清理同名容器: {container_name}")
        except Exception as e:
            # 如果本来就不存在，会报错，忽略即可
            print(f"[DEBUG container] 启动前清理同名容器时忽略错误: {e}")

        # 3）创建新容器
        work_dir = base_path / "agent_files" / "tmp" / "default"
        work_dir.mkdir(parents=True, exist_ok=True)
        host_work_dir = _get_host_path(work_dir)

        print(f"[DEBUG container] 容器内路径: {work_dir}")
        print(f"[DEBUG container] 宿主机路径: {host_work_dir}")

        docker_cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--cpus",
            "0.5",
            "--memory",
            "256m",
            "--memory-swap",
            "256m",
            "--pids-limit",
            "50",
            f"--volume={host_work_dir}:/workspace:rw",
            f"--volume={host_work_dir}:/tmp:rw",
            "--workdir=/workspace",
        ]

        if network_enabled:
            docker_cmd.extend(["--network", "bridge"])
        else:
            docker_cmd.extend(["--network", "none"])

        docker_cmd.append("nisb-executor:latest")

        try:
            print(f"[DEBUG container] Docker 命令: {' '.join(docker_cmd)}")
            result = subprocess.run(
                docker_cmd, capture_output=True, text=True, timeout=20
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"容器启动失败 (code={result.returncode}): {result.stderr}"
                )

            _containers[user_id] = {
                "name": container_name,
                "created_at": time.time(),
                "last_used": time.time(),
                "network_enabled": network_enabled,
                "work_dir": str(work_dir),
                "host_work_dir": str(host_work_dir),
            }

            print(
                f"[INFO container] 已创建新容器: {container_name} "
                f"(网络: {'开启' if network_enabled else '关闭'}, network={expected_network})"
            )
            return container_name

        except Exception as e:
            print(f"[ERROR container] 容器创建失败: {e}")
            raise RuntimeError(f"容器创建失败: {str(e)}") from e

def execute_in_container(
    container_name: str, code: str, work_dir: Path, timeout: int
) -> dict:
    """
    在容器中执行代码（热执行 + 自动保存 Matplotlib 图像）

    行为约定：
    - 使用 Agg 后端（无 GUI）
    - 自动配置中文字体（Noto Sans CJK / WenQuanYi Zen Hei）
    - 用户代码执行完后，枚举所有打开的 Figure，保存到 /tmp/auto_plot_*.png
    """

    # 将脚本文件写到 mcp-nisb 容器的 /data/.../tmp/default
    script_name = f"exec_default_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.py"
    script_file = work_dir / script_name

    # ⭐ 用户代码前后加包装
    wrapper_prefix = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 配置中文字体（尽量兼容多种环境）
try:
    plt.rcParams['font.sans-serif'] = [
        'Noto Sans CJK SC',
        'WenQuanYi Zen Hei',
        'Microsoft YaHei',
        'SimHei',
        'Arial Unicode MS'
    ]
    plt.rcParams['axes.unicode_minus'] = False
except Exception:
    pass

# ========== 用户代码开始 ==========
"""

    wrapper_suffix = """
# ========== 用户代码结束 ==========

# ⭐ 自动保存所有打开的图形到 /tmp/auto_plot_*.png
try:
    import time
    figs = plt.get_fignums()
    if figs:
        for i, fignum in enumerate(figs):
            fig = plt.figure(fignum)
            fname = f"/tmp/auto_plot_{int(time.time()*1000)}_{i}.png"
            fig.savefig(fname, bbox_inches='tight')
            print(f"[AUTO-SAVE] 已自动保存图形 {fignum} -> {fname}")
except Exception as e:
    print(f"[WARN] 自动保存失败: {e}")
"""

    code_to_run = wrapper_prefix + (code or "") + "\n\n" + wrapper_suffix
    script_file.write_text(code_to_run, encoding="utf-8")

    print(f"[DEBUG container] 脚本已写入: {script_file}")

    docker_cmd = [
        "docker",
        "exec",
        container_name,
        "python3",
        "-u",
        f"/workspace/{script_name}",
    ]

    print(f"[DEBUG container] 执行命令: {' '.join(docker_cmd)}")

    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": f"执行超时（{timeout} 秒）"}
    except Exception as e:
        return {"success": False, "output": "", "error": f"执行失败: {str(e)}"}
    finally:
        try:
            script_file.unlink()
        except Exception:
            pass


def get_container_stats() -> dict:
    """获取容器统计信息（用于调试）"""
    with _lock:
        return {
            "active_containers": len(_containers),
            "containers": {
                user_id: {
                    "name": info["name"],
                    "idle_seconds": int(time.time() - info.get("last_used", 0)),
                    "network_enabled": info.get("network_enabled", False),
                    "work_dir": info.get("work_dir", "N/A"),
                    "host_work_dir": info.get("host_work_dir", "N/A"),
                }
                for user_id, info in _containers.items()
            },
        }
