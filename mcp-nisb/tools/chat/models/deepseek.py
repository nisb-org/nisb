# 新建：mcp-nisb/tools/chat/models/deepseek.py

#!/usr/bin/env python3
"""
DeepSeek 模型封装
"""

import os
from openai import OpenAI

class DeepSeekModel:
    def __init__(self, model="deepseek-chat"):
        self.model = model
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
    
    def chat(self, messages, temperature=0.7, max_tokens=4000):
        """
        发送消息（兼容 OpenAI API）
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            raise Exception(f"DeepSeek API 调用失败: {str(e)}")

__all__ = ['DeepSeekModel']

