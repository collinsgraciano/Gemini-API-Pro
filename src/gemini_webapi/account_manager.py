import os
import requests
from typing import Optional, Dict, Any
from datetime import datetime

class GeminiAccountManager:
    """
    Gemini 账号管理器 (Supabase REST API 版)
    
    使用 requests 直接调用 Supabase REST API，避免 SDK 依赖问题。
    """
    
    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        # 优先读取参数，其次读取环境变量
        self.url = supabase_url or os.getenv("SUPABASE_URL")
        self.key = supabase_key or os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")
            
        # Supabase API Base URL (REST)
        # e.g. https://your-project.supabase.co/rest/v1
        self.api_url = f"{self.url.rstrip('/')}/rest/v1"
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"  # 让 Supabase 返回数据
        }

    def get_next_account(self) -> Dict[str, Any]:
        """
        轮询获取下一个可用账号
        """
        # 1. 查询可用账号，按 call_count 排序
        # GET /gemini_accounts?enabled=eq.true&order=call_count.asc&limit=1
        try:
            resp = requests.get(
                f"{self.api_url}/gemini_accounts",
                headers=self.headers,
                params={
                    "enabled": "eq.true",
                    "order": "call_count.asc",
                    "limit": "1"
                }
            )
            
            if resp.status_code != 200:
                raise Exception(f"Failed to fetch accounts: {resp.text}")
                
            accounts = resp.json()
            if not accounts:
                raise Exception("没有可用的 Gemini 账号 (No enabled accounts found)")
                
            account = accounts[0]
            
            # 2. 更新计数
            # PATCH /gemini_accounts?alias=eq.{alias}
            new_count = (account.get("call_count") or 0) + 1
            
            update_resp = requests.patch(
                f"{self.api_url}/gemini_accounts",
                headers=self.headers,
                params={"alias": f"eq.{account['alias']}"},
                json={
                    "call_count": new_count,
                    "last_used": datetime.now().isoformat()
                }
            )
            
            if update_resp.status_code not in [200, 204]:
                print(f"Warning: Failed to update usage count: {update_resp.text}")
            
            # 3. 返回数据
            return {
                "alias": account["alias"],
                "psid": account["psid"],
                "psidts": account["psidts"],
                "proxy": account.get("proxy"),
                "headers": account.get("headers"),
                "call_count": new_count
            }
            
        except Exception as e:
            print(f"Error in GeminiAccountManager: {e}")
            raise e

    def get_account(self, alias: str) -> Dict[str, Any]:
        """获取指定账号"""
        resp = requests.get(
            f"{self.api_url}/gemini_accounts",
            headers=self.headers,
            params={"alias": f"eq.{alias}"}
        )
        data = resp.json()
        if not data:
            raise Exception(f"Account '{alias}' not found")
        return data[0]

    def reset_counts(self):
        """重置所有账号计数"""
        requests.patch(
            f"{self.api_url}/gemini_accounts",
            headers=self.headers,
            # Supabase 需要至少一个过滤条件防止误删？但 update all 也是可能的
            # 如果不带条件，Supabase 可能会拒绝（取决于安全设置）。
            # 我们可以使用 alias not equals 'dummy' 作为全表条件
            params={"alias": "neq.PLACEHOLDER"},
            json={"call_count": 0}
        )
