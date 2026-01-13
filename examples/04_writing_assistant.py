"""
Gemini API 使用示例 - 实战应用篇
一个完整的 AI 写作助手示例

功能：
- 多账号轮询
- 自动重试
- 流式输出模拟
- 内容润色、续写、总结
"""

import sys
import asyncio
from pathlib import Path
from typing import Optional

# 添加 src 目录到 Python 路径，直接使用本地源码
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import requests
from gemini_webapi import GeminiClient
from gemini_webapi.constants import Model


class AIWritingAssistant:
    """AI 写作助手"""
    
    def __init__(self, server_url: str = "http://localhost:8001"):
        self.server_url = server_url
        self.client: Optional[GeminiClient] = None
        self.chat = None
    
    async def connect(self):
        """连接到 Gemini（使用轮询账号）"""
        account = self._get_next_account()
        print(f"🔗 连接账号: {account['alias']}")
        
        self.client = GeminiClient(
            secure_1psid=account["psid"],
            secure_1psidts=account["psidts"],
            proxy=account.get("proxy")
        )
        await self.client.init(verbose=False)
        self.chat = self.client.start_chat()
    
    async def disconnect(self):
        """断开连接"""
        if self.client:
            await self.client.close()
            self.client = None
            self.chat = None
    
    def _get_next_account(self):
        """获取下一个账号"""
        resp = requests.get(f"{self.server_url}/api/accounts/next")
        if resp.status_code != 200:
            raise Exception(f"获取账号失败: {resp.text}")
        return resp.json()["account"]
    
    async def _generate(self, prompt: str, max_retries: int = 2) -> str:
        """带重试的生成"""
        for attempt in range(max_retries):
            try:
                if not self.client:
                    await self.connect()
                
                response = await self.chat.send_message(prompt)
                return response.text
            except Exception as e:
                print(f"⚠️ 生成失败 (尝试 {attempt + 1}): {e}")
                await self.disconnect()
                if attempt < max_retries - 1:
                    print("🔄 切换账号重试...")
                    await self.connect()
                else:
                    raise
        return ""
    
    async def polish(self, text: str) -> str:
        """
        润色文本
        """
        prompt = f"""请对以下文本进行润色，使其更加通顺、优美：

原文：
{text}

要求：
1. 保持原意不变
2. 改善句子结构
3. 使用更优美的词汇
4. 输出润色后的文本即可，不要其他说明"""

        return await self._generate(prompt)
    
    async def continue_writing(self, text: str, style: str = "默认") -> str:
        """
        续写文本
        """
        prompt = f"""请根据以下文本进行续写：

原文：
{text}

写作风格：{style}

要求：
1. 保持与原文风格一致
2. 内容连贯自然
3. 续写约 200-300 字
4. 直接输出续写内容"""

        return await self._generate(prompt)
    
    async def summarize(self, text: str, length: str = "短") -> str:
        """
        总结文本
        """
        length_map = {"短": "50字以内", "中": "100字左右", "长": "200字左右"}
        target_length = length_map.get(length, "100字左右")
        
        prompt = f"""请对以下文本进行总结：

原文：
{text}

要求：
1. 提取核心要点
2. 总结长度控制在{target_length}
3. 语言简洁明了
4. 直接输出总结内容"""

        return await self._generate(prompt)
    
    async def translate(self, text: str, target_lang: str = "英文") -> str:
        """
        翻译文本
        """
        prompt = f"""将以下文本翻译成{target_lang}：

{text}

只输出翻译结果，不要其他说明。"""

        return await self._generate(prompt)
    
    async def generate_outline(self, topic: str) -> str:
        """
        生成文章大纲
        """
        prompt = f"""请为以下主题生成一个详细的文章大纲：

主题：{topic}

要求：
1. 包含标题
2. 分 3-5 个主要章节
3. 每个章节有 2-3 个要点
4. 使用 Markdown 格式"""

        return await self._generate(prompt)


async def demo():
    """演示写作助手"""
    assistant = AIWritingAssistant()
    
    try:
        await assistant.connect()
        
        print("\n" + "=" * 50)
        print("🖊️ AI 写作助手演示")
        print("=" * 50)
        
        # 示例 1: 润色
        print("\n📝 [润色示例]")
        original = "今天天气很好，我去公园玩了，看到了很多花，很开心。"
        polished = await assistant.polish(original)
        print(f"原文: {original}")
        print(f"润色: {polished}")
        
        # 示例 2: 续写
        print("\n📝 [续写示例]")
        start = "在一个阳光明媚的早晨，小明推开窗户，深吸一口新鲜空气。"
        continued = await assistant.continue_writing(start, style="轻松愉快")
        print(f"原文: {start}")
        print(f"续写: {continued}")
        
        # 示例 3: 总结
        print("\n📝 [总结示例]")
        long_text = """
        人工智能（AI）是计算机科学的一个分支，旨在创建能够执行通常需要人类智能的任务的系统。
        这些任务包括学习、推理、问题解决、感知和语言理解。AI 系统可以分为两大类：
        狭义 AI（专注于特定任务）和通用 AI（具有类似人类的一般智能）。
        目前，大多数 AI 应用属于狭义 AI，如语音助手、推荐系统和自动驾驶汽车。
        """
        summary = await assistant.summarize(long_text, "短")
        print(f"总结: {summary}")
        
        # 示例 4: 生成大纲
        print("\n📝 [大纲生成示例]")
        outline = await assistant.generate_outline("如何学习 Python 编程")
        print(f"大纲:\n{outline}")
        
    finally:
        await assistant.disconnect()
        print("\n✅ 演示完成")


if __name__ == "__main__":
    asyncio.run(demo())
