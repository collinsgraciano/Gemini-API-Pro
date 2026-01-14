"""
OpenAI 使用示例
演示如何使用官方 `openai` 库连接本地的 Gemini-OpenAI 代理服务。

配置：
1. 启动服务: python openai_server.py
2. 运行此脚本
"""

import os
import sys
import base64
from PIL import Image
from openai import OpenAI

# 配置 OpenAI 客户端指向本地服务
client = OpenAI(
    api_key="sk-dummy",
    base_url="http://localhost:8001/v1"
)

def test_chat():
    print("=" * 50)
    print("测试 1: 普通对话")
    print("=" * 50)
    
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": "地球上最高的山峰是哪座？"}
        ]
    )
    
    print(f"User: 地球上最高的山峰是哪座？")
    print(f"AI: {completion.choices[0].message.content}")


def test_stream_chat():
    print("\n" + "=" * 50)
    print("测试 2: 流式对话 (Streaming)")
    print("=" * 50)
    
    stream = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": "请写一首关于春天的五言绝句。"}
        ],
        stream=True
    )
    
    print("AI: ", end="", flush=True)
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print() # 换行

def test_image_generation():
    print("\n" + "=" * 50)
    print("测试 3: 文生图 (Text-to-Image)")
    print("=" * 50)
    
    prompt = "A cute robot painting a picture, cyberpunk style"
    print(f"Prompt: {prompt}")
    
    try:
        response = client.images.generate(
            model="g3-img-pro",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        
        image_url = response.data[0].url
        print(f"✅ 图片生成成功: {image_url}")
        
    except Exception as e:
        print(f"❌ 图片生成失败: {e}")

def test_image_edit():
    print("\n" + "=" * 50)
    print("测试 4: 图生图 (参考生成 / Image Variation)")
    print("=" * 50)
    
    image_path = "D:\gemini\Gemini-API-feat-image-mode-api\static\images\gen_3770e884-5aea-4186-90fa-fd5d9f2bc603.png"
    if not os.path.exists(image_path):
        # Create a simple dummy image if not exists
        img = Image.new('RGB', (100, 100), color = 'red')
        img.save(image_path)
        print(f"⚠️ Created dummy image: {image_path}")

    prompt = "Make it look like a van gogh painting"
    print(f"Prompt: {prompt} (Reference: {image_path})")
    
    try:
        response = client.images.edit(
            image=open(image_path, "rb"),
            prompt=prompt,
            model="g3-img-pro",
            n=1,
            size="1024x1024"
        )
        print(f"✅ 参考生成成功: {response.data[0].url}")
    except Exception as e:
        print(f"❌ 参考生成失败: {e}")


def test_multi_image_edit():
    """测试多张图片参考生成"""
    print("\n" + "=" * 50)
    print("测试 5: 多图参考生成 (Multi-Image Reference)")
    print("=" * 50)
    
    # 准备多张参考图片
    image_paths = []
    
    # 使用 static/images 目录下已有的图片，或创建测试图
    static_dir = "D:\\gemini\\Gemini-API-feat-image-mode-api\\static\\images"
    if os.path.exists(static_dir):
        # 获取前2张现有图片
        existing = [f for f in os.listdir(static_dir) if f.endswith('.png')][:2]
        for f in existing:
            image_paths.append(os.path.join(static_dir, f))
    
    # 如果没有足够的图片，创建测试图
    while len(image_paths) < 2:
        test_path = f"test_multi_{len(image_paths)}.png"
        colors = ['red', 'blue', 'green']
        img = Image.new('RGB', (100, 100), color=colors[len(image_paths) % 3])
        img.save(test_path)
        image_paths.append(test_path)
        print(f"⚠️ Created dummy image: {test_path}")
    
    prompt = "Combine these images into one artistic composition"
    print(f"Prompt: {prompt}")
    print(f"Reference images: {len(image_paths)} files")
    for p in image_paths:
        print(f"  - {os.path.basename(p)}")
    
    try:
        import requests
        
        # 使用 requests 直接调用多图端点（OpenAI SDK不直接支持）
        files = [('images', (os.path.basename(p), open(p, 'rb'), 'image/png')) for p in image_paths]
        data = {
            'prompt': prompt,
            'model': 'g3-img-pro',
            'n': 1,
            'size': '1024x1024'
        }
        
        response = requests.post(
            "http://localhost:8001/v1/images/edits/multi",
            files=files,
            data=data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 多图参考生成成功: {result['data'][0]['url']}")
        else:
            print(f"❌ 多图参考生成失败: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ 多图参考生成失败: {e}")


def main():
    try:
        #test_chat()
        # test_stream_chat() 
        #test_image_generation()
        #test_image_edit() # 图生图（参考生成）
        test_multi_image_edit() # 多图参考生成

        
    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        print("请确保 'openai_server.py' 正在运行 (端口 8001)")

if __name__ == "__main__":
    main()
