"""
Gemini API 使用示例 - 图片处理与生成 (Supabase 版)
演示：
1. 图片生成与保存
2. 多模态对话（上传文件 + 图片修改）
"""

import sys
import asyncio
import os
from pathlib import Path

# 添加 src 目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gemini_webapi import GeminiClient
from gemini_webapi.account_manager import GeminiAccountManager

# Supabase 配置
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lvpbegckuzmppqcvbtkj.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_secret_y9fn8HzVdDEmUqzttysMHQ_dEzWvD5R")

def get_account():
    manager = GeminiAccountManager(SUPABASE_URL, SUPABASE_KEY)
    return manager.get_next_account()

async def example_image_generation(client):
    print("\n" + "=" * 50)
    print("示例 1: 图片生成与保存")
    print("=" * 50)
    
    prompt = "Generate some pictures of cats in cyberpunk style"
    print(f"提示词: {prompt}")
    
    response = await client.generate_content(prompt)
    print(f"回复: {response.text}")
    
    if response.images:
        save_dir = Path("temp")
        save_dir.mkdir(exist_ok=True)
        
        for i, image in enumerate(response.images):
            # 支持 save 方法，skip_invalid_filename 跳过非法文件名
            file_path = await image.save(
                path=str(save_dir), 
                filename=f"cat_{i}.png", 
                skip_invalid_filename=True,
                verbose=True
            )
            print(f"✅ 图片已保存: {file_path}")
            print(f"Image Object: {image}")
            print("-" * 30)
    else:
        print("⚠️ 未生成图片")

async def example_multimodal_chat(client):
    print("\n" + "=" * 50)
    print("示例 2: 多模态对话与图片修改")
    print("=" * 50)
    
    # 准备示例文件
    assets_dir = PROJECT_ROOT / "assets"
    pdf_path = assets_dir / "sample.pdf"
    img_path = assets_dir / "banner.png"
    
    if not pdf_path.exists() or not img_path.exists():
        print(f"⚠️ 缺少示例文件，请确保 assets 目录下有 sample.pdf 和 banner.png")
        # 创建假文件用于演示（如果不存在）
        # assets_dir.mkdir(exist_ok=True)
        # return
    
    # 开始聊天
    chat = client.start_chat()
    
    # 1. 上传文件并提问
    print("用户: 介绍这两个文件的内容，它们之间有什么联系吗？")
    if pdf_path.exists() and img_path.exists():
        # files 参数支持字符串路径或 Path 对象
        response1 = await chat.send_message(
            "Introduce the contents of these two files. Is there any connection between them?",
            files=[str(pdf_path), img_path],
        )
        print(f"\nGemini: {response1.text}")
    else:
        print("(跳过文件上传演示，文件缺失)")
        # 为了演示继续，发送纯文本
        await chat.send_message("Let's pretend I sent a banner image.")

    # 2. 修改图片
    print("\n用户: 使用图片生成工具修改这个 banner，换一个字体和设计。")
    response2 = await chat.send_message(
        "Use image generation tool to modify the banner with another font and design."
    )
    
    print(f"\nGemini: {response2.text}")
    if response2.images:
        print("\n生成的图片列表:")
        for img in response2.images:
            print(f"- {img.url[:60]}...")
            # 同样可以保存
            # await img.save("temp/", verbose=True)
    
    print("\n----------------------------------\n")

async def main():
    try:
        account = get_account()
        print(f"使用账号: {account['alias']} (Count: {account['call_count']})")
        
        client = GeminiClient(
            secure_1psid=account["psid"],
            secure_1psidts=account["psidts"],
            proxy=account.get("proxy"),
            headers=account.get("headers")
        )
        await client.init()
        
        await example_image_generation(client)
        #await example_multimodal_chat(client)
        
        await client.close()
        
    except Exception as e:
        print(f"❌ 运行失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
