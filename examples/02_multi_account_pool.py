"""
Gemini API 使用示例 - 多账号轮询篇
演示如何使用多账号轮询进行批量任务

适用场景：
- 批量翻译
- 批量内容生成
- 分散请求，规避限制
"""

import sys
import asyncio
from pathlib import Path

# 添加 src 目录到 Python 路径，直接使用本地源码
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import requests
from gemini_webapi import GeminiClient


class GeminiPool:
    """
    Gemini 客户端池 - 支持多账号轮询
    """
    
    def __init__(self, server_url: str = "http://localhost:8001"):
        self.server_url = server_url
    
    def get_next_account(self):
        """获取下一个可用账号（轮询）"""
        resp = requests.get(f"{self.server_url}/api/accounts/next")
        if resp.status_code != 200:
            raise Exception(f"获取账号失败: {resp.text}")
        return resp.json()["account"]
    
    def get_all_accounts(self):
        """获取所有账号"""
        resp = requests.get(f"{self.server_url}/api/accounts")
        return resp.json()["accounts"]
    
    async def create_client(self, account: dict = None) -> GeminiClient:
        """创建客户端，不传账号则自动轮询"""
        if account is None:
            account = self.get_next_account()
        
        client = GeminiClient(
            secure_1psid=account["psid"],
            secure_1psidts=account["psidts"],
            proxy=account.get("proxy")
        )
        await client.init(verbose=False)
        return client


async def example_batch_translate():
    """
    示例 1: 批量翻译（使用轮询）
    """
    print("=" * 50)
    print("示例 1: 批量翻译")
    print("=" * 50)
    
    texts = [
        "Hello, how are you?",
        "The quick brown fox jumps over the lazy dog.",
        "Artificial intelligence is changing the world.",
        "Python is a great programming language.",
        "Machine learning models require large datasets."
    ]
    
    pool = GeminiPool()
    
    for i, text in enumerate(texts):
        # 每次获取新账号（轮询）
        client = await pool.create_client()
        
        response = await client.generate_content(
            f"将以下英文翻译成中文，只输出翻译结果：\n{text}"
        )
        
        print(f"\n原文: {text}")
        print(f"译文: {response.text}")
        
        await client.close()
    
    print("\n翻译完成！")


async def example_parallel_requests():
    """
    示例 2: 并行请求（多账号同时使用）
    """
    print("\n" + "=" * 50)
    print("示例 2: 并行请求")
    print("=" * 50)
    
    pool = GeminiPool()
    
    # 获取所有账号
    accounts = pool.get_all_accounts()
    print(f"可用账号数: {len(accounts)}")
    
    if len(accounts) < 2:
        print("需要至少 2 个账号才能演示并行请求")
        return
    
    # 准备问题
    questions = [
        "写一首关于春天的诗",
        "写一首关于夏天的诗",
        "写一首关于秋天的诗",
        "写一首关于冬天的诗"
    ]
    
    async def ask_question(q: str):
        client = await pool.create_client()
        try:
            response = await client.generate_content(q)
            return q, response.text
        finally:
            await client.close()
    
    # 并行执行
    tasks = [ask_question(q) for q in questions]
    results = await asyncio.gather(*tasks)
    
    for question, answer in results:
        print(f"\n问题: {question}")
        print(f"回答: {answer[:100]}...")


async def example_with_retry():
    """
    示例 3: 带重试的请求（账号失效时切换）
    """
    print("\n" + "=" * 50)
    print("示例 3: 带重试的请求")
    print("=" * 50)
    
    pool = GeminiPool()
    max_retries = 3
    
    async def safe_generate(prompt: str):
        for attempt in range(max_retries):
            try:
                client = await pool.create_client()
                response = await client.generate_content(prompt)
                await client.close()
                return response.text
            except Exception as e:
                print(f"尝试 {attempt + 1} 失败: {e}")
                if attempt == max_retries - 1:
                    raise
                print("切换账号重试...")
        return None
    
    result = await safe_generate("用一句话介绍中国")
    print(f"\n结果: {result}")


async def main():
    try:
        await example_batch_translate()
        await example_parallel_requests()
        await example_with_retry()
    except Exception as e:
        print(f"\n错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
