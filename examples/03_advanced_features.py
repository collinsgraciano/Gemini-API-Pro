"""
Gemini API 使用示例 - 高级功能篇
演示使用请求头、Gems 和扩展

前置条件：
1. Cookie 服务器运行中
2. 账号已同步（含浏览器请求头）
"""

import sys
import asyncio
from pathlib import Path

# 添加 src 目录到 Python 路径，直接使用本地源码
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import requests
from gemini_webapi import GeminiClient
from gemini_webapi.constants import Model


def get_account_with_headers():
    """获取带请求头的账号"""
    resp = requests.get("http://localhost:8001/api/accounts/next")
    account = resp.json()["account"]
    
    if not account.get("headers"):
        print("警告：该账号没有浏览器请求头")
    
    return account


async def example_use_thinking_model():
    """
    示例 1: 使用思考模型
    获取模型的思考过程
    """
    print("=" * 50)
    print("示例 1: 使用思考模型（查看思维链）")
    print("=" * 50)
    
    account = get_account_with_headers()
    
    client = GeminiClient(
        secure_1psid=account["psid"],
        secure_1psidts=account["psidts"],
        proxy=account.get("proxy")
    )
    await client.init()
    
    # 使用 Gemini 2.5 Pro（支持思考）
    response = await client.generate_content(
        "如果一个数的平方根是 144，这个数是多少？请一步步思考。",
        model=Model.G_2_5_PRO
    )
    
    # 查看思考过程
    if response.thoughts:
        print(f"\n💭 思考过程:\n{response.thoughts}")
    
    print(f"\n✅ 最终答案:\n{response.text}")
    
    await client.close()


async def example_use_gems():
    """
    示例 2: 使用 Gemini Gems（自定义系统提示）
    """
    print("\n" + "=" * 50)
    print("示例 2: 使用 Gems")
    print("=" * 50)
    
    account = get_account_with_headers()
    
    client = GeminiClient(
        secure_1psid=account["psid"],
        secure_1psidts=account["psidts"],
        proxy=account.get("proxy")
    )
    await client.init()
    
    # 获取可用的 Gems
    await client.fetch_gems()
    gems = client.gems
    
    print(f"可用 Gems 数量: {len(gems)}")
    
    if gems:
        # 使用第一个 Gem
        gem = gems[0]
        print(f"使用 Gem: {gem.name}")
        
        response = await client.generate_content(
            "你好，请介绍一下你自己",
            gem=gem
        )
        print(f"\n回复: {response.text}")
    else:
        print("没有可用的 Gems")
    
    await client.close()


async def example_use_extensions():
    """
    示例 3: 使用 Gemini 扩展（YouTube、Gmail 等）
    """
    print("\n" + "=" * 50)
    print("示例 3: 使用扩展")
    print("=" * 50)
    
    account = get_account_with_headers()
    
    client = GeminiClient(
        secure_1psid=account["psid"],
        secure_1psidts=account["psidts"],
        proxy=account.get("proxy")
    )
    await client.init()
    
    # 使用 YouTube 扩展
    response = await client.generate_content(
        "@Youtube 搜索最新的 Python 教程视频"
    )
    print(f"\n搜索结果:\n{response.text[:500]}...")
    
    await client.close()


async def example_save_and_load_chat():
    """
    示例 4: 保存和恢复对话
    """
    print("\n" + "=" * 50)
    print("示例 4: 保存和恢复对话")
    print("=" * 50)
    
    account = get_account_with_headers()
    
    # 第一个会话
    client = GeminiClient(
        secure_1psid=account["psid"],
        secure_1psidts=account["psidts"],
        proxy=account.get("proxy")
    )
    await client.init()
    
    chat = client.start_chat()
    
    # 进行对话
    await chat.send_message("我的名字是小明")
    await chat.send_message("我喜欢编程")
    
    # 保存会话元数据
    saved_metadata = chat.metadata
    print(f"已保存会话: {saved_metadata}")
    
    await client.close()
    
    # 第二个会话（恢复）
    client2 = GeminiClient(
        secure_1psid=account["psid"],
        secure_1psidts=account["psidts"],
        proxy=account.get("proxy")
    )
    await client2.init()
    
    # 恢复对话
    restored_chat = client2.start_chat(metadata=saved_metadata)
    response = await restored_chat.send_message("我叫什么名字？我喜欢什么？")
    
    print(f"\n恢复后回复: {response.text}")
    
    await client2.close()


async def example_custom_headers():
    """
    示例 5: 使用采集的浏览器请求头
    """
    print("\n" + "=" * 50)
    print("示例 5: 使用浏览器请求头")
    print("=" * 50)
    
    account = get_account_with_headers()
    
    headers = account.get("headers", {})
    if headers:
        print("采集到的请求头:")
        for key, value in headers.items():
            print(f"  {key}: {value[:50]}...")
    
    # 使用自定义请求头创建客户端
    # 注意：gemini_webapi 内部会使用默认头，这里只是演示数据可用
    print("\n这些请求头可用于其他需要模拟浏览器的场景")


async def main():
    try:
        await example_use_thinking_model()
        # await example_use_gems()  # 需要有可用的 Gems
        # await example_use_extensions()  # 需要开启扩展
        await example_save_and_load_chat()
        await example_custom_headers()
    except Exception as e:
        print(f"\n错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
