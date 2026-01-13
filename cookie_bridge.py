"""
Gemini Cookie 上传器 (Supabase REST API 版)
替代原有的 cookie_server.py + cookie_bridge.py 架构

用途：
直接接收浏览器扩展的 POST 请求，并将数据写入 Supabase 数据库。
浏览器扩展指向本服务地址：http://127.0.0.1:8002/api/cookies

前置条件：
pip install fastapi uvicorn requests
"""

import os
import requests
from datetime import datetime
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("请先安装依赖: pip install fastapi uvicorn requests")
    exit(1)

# ================= 配置区域 =================
# 本地监听配置
LOCAL_HOST = "0.0.0.0"
LOCAL_PORT = 8002

# Supabase 配置 (优先读取环境变量)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-anon-key")
# ===========================================

app = FastAPI(title="Gemini Cookie Uploader (Supabase REST)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 构造 Base URL 和 Headers
API_URL = f"{SUPABASE_URL.rstrip('/')}/rest/v1" if SUPABASE_URL else ""
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def is_configured():
    return SUPABASE_URL and SUPABASE_KEY and "your-project" not in SUPABASE_URL

@app.get("/")
async def root():
    return {
        "service": "Gemini Cookie Uploader",
        "backend": "Supabase (REST API)",
        "status": "active" if is_configured() else "misconfigured",
        "usage": "Set Chrome Extension URL to http://127.0.0.1:8002/api/cookies"
    }

@app.post("/api/cookies")
async def receive_cookies(payload: dict):
    if not is_configured():
        raise HTTPException(status_code=500, detail="服务器端 Supabase 未配置")

    # 提取字段
    psid = payload.get("__Secure-1PSID") or payload.get("secure_1psid")
    psidts = payload.get("__Secure-1PSIDTS") or payload.get("secure_1psidts")
    alias = payload.get("alias")
    proxy = payload.get("proxy")
    headers = payload.get("headers")
    timestamp = datetime.now().isoformat()

    if not all([psid, psidts, alias]):
        raise HTTPException(status_code=400, detail="缺少必要参数: alias, psid, psidts")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 收到更新: {alias}")

    # Upsert Logic using REST API
    # POST /gemini_accounts (with on_conflict header)
    # Supabase (PostgREST) supports Upsert via POST with Prefer: resolution=merge-duplicates header
    
    upsert_headers = HEADERS.copy()
    upsert_headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    
    data = {
        "alias": alias,
        "psid": psid,
        "psidts": psidts,
        "last_updated": timestamp
    }
    
    # 因为 REST upsert 是整行合并，有些字段如果不想被覆盖需要注意。
    # 比如 enabled, call_count。
    # PostgREST 的 merge-duplicates 会忽略不在 payload 中的列 (PATCH 行为) 还是覆盖 (PUT 行为)?
    # PostgREST Upsert (POST) 默认会插入，如果冲突则更新。
    # 为安全起见，我们最好先查询是否存在，就像原来代码做的那样。
    
    try:
        # 1. 检查是否存在
        query_resp = requests.get(
            f"{API_URL}/gemini_accounts",
            headers=HEADERS,
            params={"alias": f"eq.{alias}"}
        )
        existing = query_resp.json() if query_resp.status_code == 200 else []
        
        if existing:
            # 更新
            update_payload = data  # 基础数据
            if proxy is not None: update_payload["proxy"] = proxy if proxy else None
            if headers: update_payload["headers"] = headers
            
            # PATCH
            requests.patch(
                f"{API_URL}/gemini_accounts",
                headers=HEADERS,
                params={"alias": f"eq.{alias}"},
                json=update_payload
            )
            action = "updated"
        else:
            # 新建
            data["proxy"] = proxy
            data["headers"] = headers
            data["enabled"] = True
            data["call_count"] = 0
            
            # POST
            requests.post(
                f"{API_URL}/gemini_accounts",
                headers=HEADERS,
                json=data
            )
            action = "created"

        return {
            "status": "success",
            "action": action,
            "account": {
                "alias": alias,
                "has_headers": bool(headers)
            }
        }

    except Exception as e:
        print(f"❌ REST API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts")
async def get_accounts():
    """
    获取所有账号列表
    """
    if not is_configured():
        raise HTTPException(status_code=500, detail="Supabase 未配置")

    try:
        resp = requests.get(
            f"{API_URL}/gemini_accounts",
            headers=HEADERS,
            # 排序: order=last_updated.desc.nullslast
            params={"order": "last_updated.desc.nullslast"}
        )
        
        if resp.status_code != 200:
            raise Exception(f"Failed to list accounts: {resp.text}")
            
        accounts = resp.json()
        
        return {
            "status": "ok",
            "count": len(accounts),
            "accounts": accounts
        }
    except Exception as e:
        print(f"❌ List Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║     Gemini Cookie Uploader (Supabase REST Edition)            ║
╠══════════════════════════════════════════════════════════════╣
║  本地监听: http://{LOCAL_HOST}:{LOCAL_PORT}                          
║  数据库  : REST API Mode                                     
╚══════════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host=LOCAL_HOST, port=LOCAL_PORT)
