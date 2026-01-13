"""
Gemini API 使用示例 - 基础篇 (Supabase 版)
无需 pip install gemini_webapi

配置：
请在环境变量中设置 SUPABASE_URL 和 SUPABASE_KEY
或者直接在代码中填入
"""

import sys
import asyncio
import os  # Add missing import
from pathlib import Path

# 添加 src 目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from gemini_webapi import GeminiClient
from gemini_webapi.constants import Model
from gemini_webapi.account_manager import GeminiAccountManager  # 新增管理器

# Supabase 配置 (请填入您的配置)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lvpbegckuzmppqcvbtkj.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_secret_y9fn8HzVdDEmUqzttysMHQ_dEzWvD5R")

def get_account():
    """使用管理器获取账号"""
    manager = GeminiAccountManager(SUPABASE_URL, SUPABASE_KEY)
    return manager.get_next_account()

async def example_basic_chat():
    print("=" * 50)
    print("示例 1: 基础对话 (Supabase)")
    print("=" * 50)
    
    try:
        # 1. 获取账号
        account = get_account()
        print(f"使用账号: {account['alias']} (Call Count: {account['call_count']})")
        print(f"使用代理: {account.get('proxy')}")  # 打印代理
        # 2. 初始化客户端
        client = GeminiClient(
            secure_1psid=account["psid"],
            secure_1psidts=account["psidts"],
            proxy=account.get("proxy"),
            headers=account.get("headers")
        )
        await client.init()
        
        # 3. 对话
        response = await client.generate_content("你好，请介绍一下gpt")
        print(f"\nGemini: {response.text}")
        
        await client.close()
        
    except Exception as e:
        print(f"❌ 运行失败: {e}")
        print("请检查 Supabase 配置是否正确，以及数据库中是否有可用账号")

async def main():
    print(f"\n📂 项目根目录: {PROJECT_ROOT}\n")
    await example_basic_chat()

if __name__ == "__main__":
    asyncio.run(main())
