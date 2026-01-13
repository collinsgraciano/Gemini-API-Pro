# Gemini Cookie 自动同步 Chrome 扩展 (轮询版)

支持**多账号轮询调度**、**代理配置**和**浏览器请求头采集**。

## 核心功能

- ✅ **轮询调度** - 自动轮流使用各账号，均衡请求
- ✅ **请求头采集** - 采集真实浏览器指纹，规避封禁
- ✅ **多账号支持** - 账号别名 + 独立代理
- ✅ **调用计数** - 记录每个账号使用次数
- ✅ **自动同步** - 定时检测并上传 Cookie

## 快速开始

```bash
# 1. 启动服务器
pip install fastapi uvicorn
python cookie_server.py

# 2. 加载 Chrome 扩展
# chrome://extensions/ → 开发者模式 → 加载已解压的扩展

# 3. 登录 Gemini 账号，设置别名和代理，点击保存
```

## 轮询调用

```python
import requests

# 获取下一个可用账号（自动轮询）
resp = requests.get("http://localhost:8001/api/accounts/next")
data = resp.json()["account"]

# 使用返回的账号信息
from gemini_webapi import GeminiClient
client = GeminiClient(
    secure_1psid=data["psid"],
    secure_1psidts=data["psidts"],
    proxy=data["proxy"]
)

# 同时可用账号的浏览器请求头
custom_headers = data["headers"]  # User-Agent, Sec-Ch-Ua 等
```

## API 参考

| 端点 | 描述 |
|------|------|
| `GET /api/accounts/next` | **轮询获取下一个账号**（核心） |
| `GET /api/accounts` | 获取所有账号（按调用次数排序） |
| `GET /api/accounts/{alias}` | 获取指定账号详情 |
| `POST /api/accounts/{alias}/reset` | 重置单个账号计数 |
| `POST /api/accounts/reset-all` | 重置所有计数 |

## 浏览器请求头

每次同步时会采集以下头信息：
- `User-Agent` - 浏览器标识
- `Accept-Language` - 语言偏好
- `Sec-Ch-Ua` - Chrome 版本信息
- `Sec-Ch-Ua-Platform` - 操作系统
- 其他 Sec-Fetch-* 头

这些头可用于 Gemini API 请求，模拟真实浏览器访问。
