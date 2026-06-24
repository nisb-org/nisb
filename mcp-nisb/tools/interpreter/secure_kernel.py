#!/usr/bin/env python3
"""
Secure NISB Kernel - Phase 3.8.2 Corpus分析优化版
关键更新：
1. ⭐⭐⭐ 扩展只读权限：支持读取corpus和storage数据
2. ✅ 保持写入权限限制在agent_files/
3. ✅ 自动备份机制继承自filesystem层
4. ✅ 保持Phase 3.8.1所有功能
"""

import io
import sys
import signal
import psutil
import base64
import builtins
from pathlib import Path
from contextlib import contextmanager
from typing import Dict, Any

from RestrictedPython import compile_restricted
from RestrictedPython.PrintCollector import PrintCollector
from RestrictedPython.Guards import (
    safe_builtins,
    guarded_iter_unpack_sequence,
    safer_getattr,
    full_write_guard
)

import matplotlib
matplotlib.use('Agg')

# ⭐⭐⭐ Phase 3.8.1修复：中文字体配置（使用实际安装的字体）
try:
    matplotlib.rcParams['font.sans-serif'] = [
        'Noto Sans CJK SC',
        'Noto Sans CJK TC',
        'Noto Sans CJK JP',
        'WenQuanYi Zen Hei',
        'DejaVu Sans'
    ]
    matplotlib.rcParams['axes.unicode_minus'] = False
    
    from matplotlib.font_manager import findfont, FontProperties
    font_path = findfont(FontProperties(family='Noto Sans CJK SC'))
    print(f"[INFO] Matplotlib中文字体已配置: {font_path}")
except Exception as e:
    print(f"[WARN] Matplotlib中文字体配置失败: {e}")
    try:
        matplotlib.rcParams['font.family'] = 'sans-serif'
        print("[INFO] 使用系统默认字体")
    except:
        pass

import matplotlib.pyplot as plt


class SecureNISBKernel:
    """NISB安全Python执行内核 - Phase 3.8.2 Corpus分析优化版"""
    
    # ⭐⭐⭐ Phase 3.8更新：阻止模块列表（保持安全）
    BLOCKED_MODULES = {
        'os', 'sys', 'subprocess', 'socket', 'urllib', 'urllib3', 'requests',
        'eval', 'exec', 'compile', 'importlib', 'ctypes', 'multiprocessing',
        'shutil', 'pathlib',
    }
    
    # ⭐⭐⭐ Phase 3.8.1新增：允许模块白名单
    ALLOWED_MODULES = [
        'math', 'csv', 'statistics', 'decimal', 'fractions',
        'numpy', 'numpy.linalg', 'numpy.random', 'pandas', 'pandas.core',
        'networkx',
        'random', 'datetime', 'time',
        'json', 'collections', 're', 'itertools', 'functools', 'string',
        'matplotlib', 'matplotlib.pyplot', 'matplotlib.patches',
        'matplotlib.lines', 'matplotlib.colors',
    ]
    
    def __init__(self, user_id: str, email: str = None, name: str = None, 
                 base_path: str = None, timeout: int = 30):
        """初始化安全内核（遵循NISB多用户规范）"""
        self.user_id = user_id
        self.email = email
        self.name = name
        self.timeout = timeout
        
        from tools.filesystem.config import get_agent_files_path
        self.user_root = Path(get_agent_files_path(user_id, email, name))
        self.user_root.mkdir(parents=True, exist_ok=True)
        
        self.charts_dir = self.user_root / "charts"
        self.charts_dir.mkdir(exist_ok=True)
        
        # ⭐⭐⭐ Phase 3.8.2新增：用户storage路径
        self.user_storage = Path(f"/data/users/{user_id}/documents/storage")
        
        self.safe_env = self._build_safe_environment()
    
    def _build_safe_environment(self) -> Dict[str, Any]:
        """构建安全的全局执行环境 - Phase 3.8.2优化"""
        env = {}
        
        # ===== RestrictedPython必需的guards =====
        env['_print_'] = PrintCollector
        env['_getattr_'] = safer_getattr
        env['_write_'] = full_write_guard
        env['_getitem_'] = lambda obj, index: obj[index]
        env['_getiter_'] = lambda obj: iter(obj)
        
        # ⭐⭐⭐ Phase 3.8.1优化：安全的迭代器解包（修复enumerate）
        def safe_iter_unpack_sequence(obj, *args):
            if isinstance(obj, (list, tuple)):
                return obj
            if isinstance(obj, dict):
                return list(obj.keys())
            if hasattr(obj, '__iter__'):
                try:
                    return list(obj)
                except Exception:
                    return []
            try:
                return list(iter(obj))
            except TypeError:
                return [obj]

        env['_iter_unpack_sequence_'] = safe_iter_unpack_sequence
      
        # ⭐⭐⭐ Phase 3.7.2修复：正确处理RestrictedPython的spec参数
        def enhanced_unpack_sequence(obj, spec, _getiter_):
            if isinstance(spec, dict):
                expected_len = spec.get('min_len', 2)
            elif isinstance(spec, int):
                expected_len = spec
            else:
                return guarded_iter_unpack_sequence(obj, spec, _getiter_)
            
            if isinstance(obj, (tuple, list)):
                if len(obj) != expected_len:
                    raise ValueError(
                        f"解包长度不匹配: 期望{expected_len}个元素，实际{len(obj)}个\n"
                        f"💡 提示：检查 plt.subplots() 的返回值"
                    )
                return obj
            
            try:
                result = list(_getiter_(obj))
                if len(result) != expected_len:
                    raise ValueError(
                        f"解包长度不匹配: 期望{expected_len}个元素，实际{len(result)}个"
                    )
                return result
            except TypeError as e:
                raise TypeError(
                    f"无法解包对象 {type(obj).__name__}\n\n"
                    f"💡 建议使用：\n"
                    f"   fig = plt.figure()\n"
                    f"   ax1 = fig.add_subplot(311)"
                ) from e
        
        env['_unpack_sequence_'] = enhanced_unpack_sequence
        env['__name__'] = 'restricted_module'
        env['__metaclass__'] = type
        
        # ===== 内置函数 =====
        builtins_dict = {
            'None': None, 'False': False, 'True': True,
            'abs': abs, 'divmod': divmod, 'max': max, 'min': min, 'pow': pow, 'round': round, 'sum': sum,
            'bin': bin, 'bool': bool, 'chr': chr, 'complex': complex, 'dict': dict, 'float': float,
            'hex': hex, 'int': int, 'list': list, 'oct': oct, 'ord': ord, 'set': set, 'str': str, 'tuple': tuple,
            'all': all, 'any': any, 'enumerate': enumerate, 'filter': filter, 'iter': iter, 'len': len,
            'map': map, 'next': next, 'range': range, 'reversed': reversed, 'slice': slice, 'sorted': sorted, 'zip': zip,
            'dir': dir, 'format': format, 'getattr': getattr, 'hasattr': hasattr, 'hash': hash,
            'isinstance': isinstance, 'repr': repr, 'setattr': setattr, 'type': type, 'print': print,
            # ⭐⭐⭐ Phase 3.8.2修复：添加异常类
            'Exception': Exception,
            'ValueError': ValueError,
            'TypeError': TypeError,
            'KeyError': KeyError,
            'IndexError': IndexError,
            'AttributeError': AttributeError,
            'ImportError': ImportError,
            'NameError': NameError,
            'SyntaxError': SyntaxError,
            'PermissionError': PermissionError,  # ⭐ 关键修复
            'FileNotFoundError': FileNotFoundError,
            'IOError': IOError,
        }
        env['__builtins__'] = builtins_dict
        
        # ⭐⭐⭐ Phase 3.8.1优化：增强的__import__（支持更多模块）
        original_import = builtins.__import__
        
        def safe_import(name, *args, **kwargs):
            if name in self.BLOCKED_MODULES:
                raise ImportError(
                    f"❌ 模块 '{name}' 被禁用（安全限制）\n"
                    f"💡 该模块可能访问系统资源或执行危险操作"
                )
            
            if name.startswith('matplotlib'):
                return original_import(name, *args, **kwargs)
            
            if name.startswith('numpy'):
                allowed_numpy = ['numpy', 'numpy.linalg', 'numpy.random', 'numpy.core']
                if any(name.startswith(m) for m in allowed_numpy):
                    try:
                        return original_import(name, *args, **kwargs)
                    except ImportError:
                        raise ImportError(
                            f"❌ numpy未安装\n"
                            f"💡 大部分场景可用Python列表替代"
                        )
                else:
                    raise ImportError(f"❌ numpy子模块 '{name}' 不在白名单中")
            
            if name.startswith('pandas'):
                try:
                    return original_import(name, *args, **kwargs)
                except ImportError:
                    raise ImportError(
                        f"❌ pandas未安装\n"
                        f"💡 临时方案：用Python字典处理数据"
                    )
            
            if name.startswith('networkx') or name == 'nx':
                try:
                    return original_import(name, *args, **kwargs)
                except ImportError:
                    raise ImportError(
                        f"❌ networkx未安装\n"
                        f"💡 临时方案：用matplotlib手动绘制网络图"
                    )
            
            if name in self.ALLOWED_MODULES:
                try:
                    return original_import(name, *args, **kwargs)
                except ImportError as e:
                    if name in ['csv', 'statistics']:
                        raise ImportError(
                            f"❌ 模块 '{name}' 未安装\n"
                            f"💡 请检查Docker镜像是否已重建"
                        ) from e
                    raise
            
            raise ImportError(
                f"❌ 模块 '{name}' 不在白名单中\n"
                f"💡 支持的模块：math, csv, statistics, numpy, pandas, networkx, matplotlib等"
            )
        
        env['__builtins__']['__import__'] = safe_import
        env['__import__'] = safe_import
        
        # ⭐⭐⭐⭐⭐ Phase 3.8.2核心修改：扩展文件访问权限
        def safe_open(path: str, mode: str = 'r', **kwargs):
            """
            安全的文件访问（Phase 3.8.2扩展版）
            
            读权限：
            - agent_files/         ✅ 完全访问（读写）
            - /data/corpus/        ✅ 只读访问（corpus数据）
            - storage/entities/    ✅ 只读访问（用户数据）
            - storage/annotations/ ✅ 只读访问（批注数据）
            
            写权限：
            - 仅agent_files/       ✅ 可写（有自动备份保护）
            - 其他路径              ❌ 禁止写入（数据保护）
            """
            # 转换为绝对路径
            if not Path(path).is_absolute():
                abs_path = (self.user_root / path).resolve()
            else:
                abs_path = Path(path).resolve()
            
            # ⭐⭐⭐ 定义允许的读取路径
            allowed_read_paths = [
                self.user_root,                      # agent_files/（可读写）
                Path("/data/corpus"),                 # corpus数据（只读）
                self.user_storage / "entities",      # 用户实体数据（只读）
                self.user_storage / "annotations",   # 批注数据（只读）
                self.user_storage / "relations",     # 关系数据（只读）
                self.user_storage / "cases",         # 案例数据（只读）
            ]
            
            # ⭐⭐⭐ 定义允许的写入路径（仅agent_files）
            allowed_write_paths = [
                self.user_root  # 仅agent_files可写
            ]
            
            # 检查读权限
            if 'r' in mode:
                read_allowed = False
                for allowed_path in allowed_read_paths:
                    try:
                        abs_path.relative_to(allowed_path)
                        read_allowed = True
                        break
                    except ValueError:
                        continue
                
                if not read_allowed:
                    raise PermissionError(
                        f"❌ 拒绝读取: {path}\n"
                        f"💡 允许读取的路径：\n"
                        f"   - agent_files/（您的工作目录）\n"
                        f"   - /data/corpus/（UP主视频库）\n"
                        f"   - storage/entities/（您的概念数据）\n"
                        f"   - storage/annotations/（您的批注）\n"
                        f"   当前路径: {abs_path}"
                    )
            
            # 检查写权限
            if any(m in mode for m in ['w', 'a', 'x', '+']):
                write_allowed = False
                for allowed_path in allowed_write_paths:
                    try:
                        abs_path.relative_to(allowed_path)
                        write_allowed = True
                        break
                    except ValueError:
                        continue
                
                if not write_allowed:
                    raise PermissionError(
                        f"❌ 拒绝写入: {path}\n"
                        f"💡 仅允许写入: agent_files/\n"
                        f"   corpus和storage数据受只读保护\n"
                        f"   如需修改数据，请使用专门的NISB工具：\n"
                        f"   - nisb_corpus_xxx（修改corpus）\n"
                        f"   - nisb_annotate（修改批注）\n"
                        f"   当前路径: {abs_path}"
                    )
                
                # 创建父目录（仅在agent_files内）
                abs_path.parent.mkdir(parents=True, exist_ok=True)
            
            return open(abs_path, mode, **kwargs)
        
        env['__builtins__']['open'] = safe_open
        
        # ⭐⭐⭐ Phase 3.8优化：预导入常用模块
        env['plt'] = plt
        env['matplotlib'] = matplotlib
        
        import math, random, datetime, json, collections, re, time
        env['math'] = math
        env['random'] = random
        env['datetime'] = datetime
        env['json'] = json
        env['collections'] = collections
        env['re'] = re
        env['time'] = time
        
        try:
            import csv, statistics
            env['csv'] = csv
            env['statistics'] = statistics
        except ImportError as e:
            print(f"[WARN] csv/statistics模块导入失败: {e}")
        
        try:
            import numpy as np
            env['np'] = np
            env['numpy'] = np
            print("[INFO] numpy已加载")
        except ImportError:
            print("[INFO] numpy未安装")
        
        try:
            import pandas as pd
            env['pd'] = pd
            env['pandas'] = pd
            print("[INFO] pandas已加载")
        except ImportError:
            print("[INFO] pandas未安装")
        
        try:
            import networkx as nx
            env['nx'] = nx
            env['networkx'] = nx
            print("[INFO] networkx已加载")
        except ImportError:
            print("[INFO] networkx未安装")
        
        # NISB辅助函数
        env['nisb_user_dir'] = str(self.user_root)
        env['nisb_read'] = lambda p: (self.user_root / p).read_text(encoding='utf-8')
        env['nisb_write'] = lambda p, c: (self.user_root / p).write_text(c, encoding='utf-8')
        
        return env
    
    @contextmanager
    def _timeout_context(self):
        """超时管理"""
        def timeout_handler(signum, frame):
            raise TimeoutError(f"⏱️  代码执行超时（{self.timeout}秒限制）")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.timeout)
        try:
            yield
        finally:
            signal.alarm(0)
    
    def _monitor_resources(self) -> Dict[str, float]:
        """资源监控"""
        process = psutil.Process()
        cpu_percent = process.cpu_percent(interval=0.1)
        mem_mb = process.memory_info().rss / 1024 / 1024
        
        if mem_mb > 512:
            raise MemoryError(f"💾 内存使用超限: {mem_mb:.1f}MB > 512MB")
        
        if cpu_percent > 95:
            raise RuntimeError(f"💻 CPU使用过高: {cpu_percent:.1f}% > 95%")
        
        return {
            'cpu_percent': round(cpu_percent, 2),
            'memory_mb': round(mem_mb, 2)
        }
    
    def execute_code(self, code: str) -> Dict[str, Any]:
        """执行代码"""
        plt.close('all')
        
        try:
            byte_code = compile_restricted(code, filename='<user_code>', mode='exec')
            if byte_code is None:
                raise SyntaxError("代码编译失败（可能包含不安全语法）")
            
            with self._timeout_context():
                exec(byte_code, self.safe_env)
                resource_usage = self._monitor_resources()
            
            output = ''
            if '_print' in self.safe_env:
                print_collector = self.safe_env['_print']
                if callable(print_collector):
                    output = print_collector()
            
            image_b64 = None
            if plt.get_fignums():
                fig = plt.gcf()
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
                buf.seek(0)
                image_b64 = base64.b64encode(buf.read()).decode('utf-8')
                plt.close(fig)
            
            return {
                'success': True,
                'output': output or '(无输出)',
                'error': None,
                'image': image_b64,
                'resource_usage': resource_usage
            }
        
        except SyntaxError as e:
            return {
                'success': False,
                'output': '',
                'error': f"语法错误: {str(e)}",
                'image': None,
                'resource_usage': {}
            }
        
        except TimeoutError as e:
            return {
                'success': False,
                'output': '',
                'error': str(e),
                'image': None,
                'resource_usage': {}
            }
        
        except (MemoryError, RuntimeError, PermissionError, ImportError) as e:
            return {
                'success': False,
                'output': '',
                'error': f"{type(e).__name__}: {str(e)}",
                'image': None,
                'resource_usage': {}
            }
        
        except Exception as e:
            import traceback
            return {
                'success': False,
                'output': '',
                'error': f"执行错误: {str(e)}\n\n{traceback.format_exc()}",
                'image': None,
                'resource_usage': {}
            }
        
        finally:
            plt.close('all')

