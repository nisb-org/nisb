#!/usr/bin/env python3
"""
NISB Code Fixer - 智能代码修复引擎
Phase 3.8.1 优化版：
- 规则匹配（免费）✅
- LLM增强（可选）✅
- Matplotlib专项错误诊断 ⭐ Phase 3.7.1
- networkx专项错误诊断 ⭐ Phase 3.8.1新增
- 更友好的错误提示 ⭐

向后兼容：100%兼容Phase 3.7
"""

import re
import os
from typing import Dict, List
from pathlib import Path


class CodeFixerEngine:
    """基于规则的代码错误诊断引擎 - Phase 3.8.1"""
    
    def __init__(self):
        self.error_patterns = {
            'SyntaxError': self._fix_syntax_error,
            'NameError': self._fix_name_error,
            'TypeError': self._fix_type_error,
            'ImportError': self._fix_import_error,
            'ModuleNotFoundError': self._fix_import_error,
            'IndentationError': self._fix_indentation_error,
            'KeyError': self._fix_key_error,
            'IndexError': self._fix_index_error,
            'ZeroDivisionError': self._fix_zero_division,
            'AttributeError': self._fix_attribute_error,
            'PermissionError': self._fix_permission_error,
            'MatplotlibError': self._fix_matplotlib_error,
        }
    
    def suggest_fix(self, error_msg: str, code: str) -> Dict:
        """生成修复建议"""
        error_type = self._identify_error_type(error_msg)
        
        if error_type in self.error_patterns:
            return self.error_patterns[error_type](error_msg, code)
        else:
            return {
                'error_type': 'Unknown',
                'suggestions': ['未识别的错误类型，请检查完整错误信息'],
                'example_fix': None
            }
    
    def _identify_error_type(self, error_msg: str) -> str:
        """识别错误类型 - Phase 3.8.1优化"""
        # ⭐ 优先匹配matplotlib相关错误
        matplotlib_keywords = [
            "'Figure' object is not iterable",
            "'Figure' object",
            "_unpack_sequence_",
            "plt.subplots",
            "matplotlib",
            "No module named 'numpy'"
        ]
        if any(kw in error_msg for kw in matplotlib_keywords):
            return 'MatplotlibError'
        
        # 常规错误类型匹配
        for error_type in self.error_patterns.keys():
            if error_type in error_msg:
                return error_type
        
        return 'Unknown'
    
    def _fix_matplotlib_error(self, error_msg: str, code: str) -> dict:
        """诊断matplotlib相关错误 - Phase 3.7.1"""
        suggestions = []
        example = None
        
        if "'Figure' object is not iterable" in error_msg or "_unpack_sequence_" in error_msg:
            suggestions = [
                "Matplotlib图表解包错误",
                "plt.subplots() 返回 (Figure, axes)，但解包失败",
                "解决方案：改用 fig.add_subplot() 方式",
            ]
            example = """# ⭐ 方式1：不解包（推荐）
fig = plt.figure(figsize=(10, 8))
ax1 = fig.add_subplot(311)
ax2 = fig.add_subplot(312)
ax3 = fig.add_subplot(313)

ax1.plot([1, 2, 3], [1, 4, 2])
ax2.bar(['A', 'B', 'C'], [10, 20, 15])
ax3.scatter([1, 2, 3], [2, 3, 1])

plt.tight_layout()
plt.show()"""
        
        elif "No module named 'numpy'" in error_msg:
            suggestions = [
                "numpy模块已在Phase 3.8安装",
                "如果仍报错，请检查Docker镜像是否已重建",
            ]
            example = """# ✅ Phase 3.8已支持numpy
import numpy as np
data = np.array([1, 2, 3, 4, 5])
mean = np.mean(data)
print(f'平均值: {mean}')"""
        
        else:
            suggestions = [
                "Matplotlib绘图错误",
                "检查：1) 语法是否正确 2) 数据格式是否匹配 3) 是否调用plt.show()",
            ]
            example = """import matplotlib.pyplot as plt

x = [1, 2, 3, 4, 5]
y = [2, 4, 3, 5, 4]

plt.plot(x, y, 'o-')
plt.title('标题')
plt.xlabel('X轴')
plt.ylabel('Y轴')
plt.grid(True)
plt.show()"""
        
        return {
            'error_type': 'MatplotlibError',
            'suggestions': suggestions,
            'example_fix': example
        }
    
    def _fix_syntax_error(self, error_msg: str, code: str) -> dict:
        suggestions = []
        example = None
        
        if code.count('(') != code.count(')'):
            suggestions.append("括号不匹配：检查是否缺少右括号 )")
            example = "print('Hello')  # 正确\nprint('Hello'   # 错误"
        elif code.count('[') != code.count(']'):
            suggestions.append("方括号不匹配：检查是否缺少 ]")
            example = "data = [1, 2, 3]  # 正确"
        elif code.count("'") % 2 != 0 or code.count('"') % 2 != 0:
            suggestions.append("引号不匹配：字符串未正确闭合")
            example = 'text = "Hello"  # 正确'
        elif any(kw in code for kw in ['if ', 'for ', 'def ', 'class ']):
            if ':' not in code:
                suggestions.append("缺少冒号：if/for/def/class 后需要 :")
                example = "if x > 0:  # 正确\n    print(x)"
        else:
            suggestions.append("检查代码结构：括号、引号、冒号是否完整")
        
        return {'error_type': 'SyntaxError', 'suggestions': suggestions, 'example_fix': example}
    
    def _fix_name_error(self, error_msg: str, code: str) -> dict:
        match = re.search(r"name '(\w+)' is not defined", error_msg)
        var_name = match.group(1) if match else "变量"
        
        suggestions = [
            f"变量 '{var_name}' 未定义，可能原因：",
            "1. 拼写错误（检查大小写）",
            "2. 变量在使用前未赋值",
            "3. 作用域问题"
        ]
        
        example = f"{var_name} = 10  # 先定义\nprint({var_name})  # 后使用"
        
        return {'error_type': 'NameError', 'suggestions': suggestions, 'example_fix': example}
    
    def _fix_type_error(self, error_msg: str, code: str) -> dict:
        suggestions = []
        example = None
        
        if "can only concatenate str" in error_msg:
            suggestions.append("字符串拼接错误：不能直接拼接字符串和数字")
            example = "result = 'Value: ' + str(123)  # 或用 f'Value: {123}'"
        elif "unsupported operand type" in error_msg:
            suggestions.append("运算符类型不匹配：检查操作数类型")
            example = "x = 10 + 5  # 正确\n# x = 10 + '5'  # 错误"
        else:
            suggestions.append("类型不匹配：使用 type(变量) 查看实际类型")
        
        return {'error_type': 'TypeError', 'suggestions': suggestions, 'example_fix': example}
    
    def _fix_import_error(self, error_msg: str, code: str) -> dict:
        match = re.search(r"No module named '(\w+)'", error_msg)
        module_name = match.group(1) if match else "模块"
        
        # ⭐ Phase 3.8.1新增：networkx专项提示
        if module_name == 'networkx' or module_name == 'nx':
            suggestions = [
                "networkx模块用于网络图谱分析",
                "Phase 3.8.1已支持，如果报错请检查：",
                "1. Docker镜像是否已重建",
                "2. 使用正确的导入方式：import networkx as nx",
            ]
            return {
                'error_type': 'ImportError',
                'suggestions': suggestions,
                'example_fix': """# ✅ Phase 3.8.1已支持networkx
import networkx as nx
import matplotlib.pyplot as plt

G = nx.Graph()
G.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D')])
pos = nx.spring_layout(G)
nx.draw(G, pos, with_labels=True, node_size=2000, 
        node_color='lightblue', font_size=12)
plt.title('概念关系网络')
plt.show()"""
            }
        
        suggestions = [
            f"模块 '{module_name}' 导入失败，可能原因：",
            "1. 模块不在白名单中",
            "2. 拼写错误",
            "Phase 3.8.1支持：math, csv, statistics, numpy, pandas, networkx, matplotlib"
        ]
        
        return {'error_type': 'ImportError', 'suggestions': suggestions, 'example_fix': None}
    
    def _fix_indentation_error(self, error_msg: str, code: str) -> dict:
        return {
            'error_type': 'IndentationError',
            'suggestions': [
                "缩进错误：Python使用缩进表示代码块",
                "规范：使用4个空格（不要混用Tab）"
            ],
            'example_fix': "if x > 0:\n    print('正数')  # 缩进4个空格"
        }
    
    def _fix_key_error(self, error_msg: str, code: str) -> dict:
        match = re.search(r"KeyError: '(\w+)'", error_msg)
        key_name = match.group(1) if match else "键"
        
        return {
            'error_type': 'KeyError',
            'suggestions': [
                f"字典中不存在键 '{key_name}'",
                "使用 .get() 方法避免错误"
            ],
            'example_fix': f"value = data.get('{key_name}', '默认值')"
        }
    
    def _fix_index_error(self, error_msg: str, code: str) -> dict:
        return {
            'error_type': 'IndexError',
            'suggestions': [
                "列表索引超出范围",
                "Python索引从0开始，长度为n的列表索引范围是0到n-1"
            ],
            'example_fix': "data = [1, 2, 3]\nprint(data[0])  # 正确\n# print(data[3])  # 错误"
        }
    
    def _fix_zero_division(self, error_msg: str, code: str) -> dict:
        return {
            'error_type': 'ZeroDivisionError',
            'suggestions': ["除数为零：添加检查确保分母不为0"],
            'example_fix': "if denominator != 0:\n    result = numerator / denominator"
        }
    
    def _fix_attribute_error(self, error_msg: str, code: str) -> dict:
        return {
            'error_type': 'AttributeError',
            'suggestions': [
                "对象没有该属性或方法",
                "使用 type(obj) 和 dir(obj) 查看可用属性"
            ],
            'example_fix': None
        }
    
    def _fix_permission_error(self, error_msg: str, code: str) -> dict:
        return {
            'error_type': 'PermissionError',
            'suggestions': [
                "文件路径超出允许范围",
                "仅允许访问用户目录：agent_files/",
                "使用相对路径（如 'data.txt'）"
            ],
            'example_fix': "with open('test.txt', 'w') as f:  # 正确\n    f.write('Hello')"
        }


class LLMCodeFixer:
    """基于LLM的智能修复（可选）- Phase 3.7保持不变"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.enabled = self.api_key is not None
    
    def suggest_fix_llm(self, error_msg: str, code: str) -> dict:
        """调用LLM生成修复建议"""
        if not self.enabled:
            return {
                'error_type': 'LLM Disabled',
                'suggestions': ['OPENAI_API_KEY未配置'],
                'llm_used': False
            }
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            prompt = f"""你是Python错误诊断专家。分析以下错误并提供修复建议。

用户代码：
{code[:500]}

错误：
{error_msg[:300]}

简洁回答（3-5句话）：
1. 错误原因
2. 修复方法
3. 修正后的关键代码"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300
            )
            
            suggestion = response.choices[0].message.content
            
            return {
                'error_type': 'LLM Analysis',
                'suggestions': [suggestion],
                'llm_used': True,
                'tokens_used': response.usage.total_tokens
            }
        
        except Exception as e:
            return {
                'error_type': 'LLM Failed',
                'suggestions': [f'LLM调用失败: {str(e)}'],
                'llm_used': False
            }


# ===== 全局实例 =====
rule_engine = CodeFixerEngine()
llm_fixer = LLMCodeFixer()


def get_fix_suggestions(error_msg: str, code: str, use_llm: bool = False) -> str:
    """
    获取格式化的修复建议
    
    Args:
        error_msg: 错误信息
        code: 用户代码
        use_llm: 是否启用LLM（默认False）
    
    Returns:
        格式化的建议文本
    """
    result = rule_engine.suggest_fix(error_msg, code)
    
    if result['error_type'] == 'Unknown' and llm_fixer.enabled and use_llm:
        llm_result = llm_fixer.suggest_fix_llm(error_msg, code)
        if llm_result.get('llm_used'):
            return f"\n\n🤖 AI智能修复建议：\n{llm_result['suggestions'][0]}"
    
    output = f"\n\n💡 自动修复建议（{result['error_type']}）：\n"
    output += "\n".join(f"  • {s}" for s in result['suggestions'])
    
    if result.get('example_fix'):
        output += f"\n\n📝 示例代码：\n``````"
    
    return output


__all__ = ['get_fix_suggestions', 'CodeFixerEngine', 'LLMCodeFixer']

