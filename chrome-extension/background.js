/**
 * Gemini Cookie 同步器 - 后台服务 Worker (轮询版)
 * 支持账号别名、代理配置、浏览器请求头采集
 */

// 常量配置
const COOKIE_URL = "https://gemini.google.com";
const COOKIE_NAMES = ["__Secure-1PSID", "__Secure-1PSIDTS"];
const DEFAULT_SERVER_URL = "http://localhost:8001/api/cookies";
const DEFAULT_INTERVAL = 5;
const ALARM_NAME = "geminiCookieSync";

/**
 * 获取指定的 Cookie
 */
async function getCookie(name) {
    try {
        const cookie = await chrome.cookies.get({
            url: COOKIE_URL,
            name: name
        });
        return cookie ? cookie.value : null;
    } catch (error) {
        console.error(`[GeminiSync] 获取 Cookie ${name} 失败:`, error);
        return null;
    }
}

/**
 * 获取所有需要的 Cookie
 */
async function getAllCookies() {
    const cookies = {};
    for (const name of COOKIE_NAMES) {
        const value = await getCookie(name);
        if (value) {
            cookies[name] = value;
        }
    }
    return cookies;
}

/**
 * 获取浏览器请求头信息
 * 用于模拟真实浏览器请求，规避封禁
 */
function getBrowserHeaders() {
    // 基本的浏览器指纹信息
    const headers = {
        "User-Agent": navigator.userAgent,
        "Accept-Language": navigator.language || "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Ch-Ua": getSecChUa(),
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": `"${getPlatform()}"`,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    };

    return headers;
}

/**
 * 获取 Sec-Ch-Ua 头
 */
function getSecChUa() {
    // 从 User-Agent 解析 Chrome 版本
    const match = navigator.userAgent.match(/Chrome\/(\d+)/);
    const version = match ? match[1] : "120";

    return `"Chromium";v="${version}", "Google Chrome";v="${version}", "Not=A?Brand";v="99"`;
}

/**
 * 获取平台信息
 */
function getPlatform() {
    const platform = navigator.platform || "";
    if (platform.includes("Win")) return "Windows";
    if (platform.includes("Mac")) return "macOS";
    if (platform.includes("Linux")) return "Linux";
    return "Windows";
}

/**
 * 获取存储的设置
 */
async function getSettings() {
    const result = await chrome.storage.local.get({
        serverUrl: DEFAULT_SERVER_URL,
        refreshInterval: DEFAULT_INTERVAL,
        autoSync: true,
        lastCookies: null,
        lastSyncTime: null,
        lastSyncStatus: "unknown",
        currentAlias: "",
        currentProxy: ""
    });
    return result;
}

/**
 * 保存日志
 */
async function addLog(message, level = "info") {
    const { logs = [] } = await chrome.storage.local.get("logs");
    const timestamp = new Date().toLocaleTimeString("zh-CN", { hour12: false });

    logs.unshift({
        time: timestamp,
        message: message,
        level: level
    });

    if (logs.length > 50) {
        logs.pop();
    }

    await chrome.storage.local.set({ logs });
    console.log(`[GeminiSync] [${level.toUpperCase()}] ${message}`);
}

/**
 * 检查 Cookie 是否发生变化
 */
function cookiesChanged(currentCookies, lastCookies) {
    if (!lastCookies) return true;

    for (const name of COOKIE_NAMES) {
        if (currentCookies[name] !== lastCookies[name]) {
            return true;
        }
    }
    return false;
}

/**
 * 上传 Cookie 到服务器
 */
async function uploadCookies(cookies, serverUrl, alias = "", proxy = "", includeHeaders = true) {
    try {
        const payload = {
            ...cookies,
            alias: alias || undefined,
            proxy: proxy, // 允许发送空字符串以清空代理
            headers: includeHeaders ? getBrowserHeaders() : undefined,
            timestamp: new Date().toISOString()
        };

        const response = await fetch(serverUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const data = await response.json();
            const accountName = data.account?.alias || alias || "默认账号";
            const headersStatus = data.account?.has_headers ? "含请求头" : "";
            await addLog(`[${accountName}] Cookie 上传成功 ${headersStatus}`, "success");
            return true;
        } else {
            await addLog(`上传失败: HTTP ${response.status}`, "error");
            return false;
        }
    } catch (error) {
        await addLog(`上传失败: ${error.message}`, "error");
        return false;
    }
}

/**
 * 执行同步操作
 */
async function performSync(force = false, alias = "", proxy = "") {
    const settings = await getSettings();
    const finalAlias = alias || settings.currentAlias;
    const finalProxy = proxy || settings.currentProxy;

    await addLog("开始检查 Cookie...", "info");

    const currentCookies = await getAllCookies();

    if (!currentCookies["__Secure-1PSID"]) {
        await addLog("未找到 __Secure-1PSID，请先登录 Gemini", "warning");
        await chrome.storage.local.set({
            lastSyncStatus: "error",
            lastSyncTime: Date.now()
        });
        return false;
    }

    const hasChanged = cookiesChanged(currentCookies, settings.lastCookies);

    if (!hasChanged && !force) {
        await addLog("Cookie 未变化，跳过上传", "info");
        await chrome.storage.local.set({
            lastSyncStatus: "success",
            lastSyncTime: Date.now()
        });
        return true;
    }

    if (hasChanged) {
        await addLog("检测到 Cookie 变化", "info");
    }

    // 上传时包含浏览器请求头
    const success = await uploadCookies(
        currentCookies,
        settings.serverUrl,
        finalAlias,
        finalProxy,
        true  // 包含请求头
    );

    await chrome.storage.local.set({
        lastCookies: currentCookies,
        lastSyncStatus: success ? "success" : "error",
        lastSyncTime: Date.now()
    });

    return success;
}

/**
 * 设置定时器
 */
async function setupAlarm(intervalMinutes) {
    await chrome.alarms.clear(ALARM_NAME);
    await chrome.alarms.create(ALARM_NAME, {
        periodInMinutes: intervalMinutes
    });
    await addLog(`定时同步已设置: 每 ${intervalMinutes} 分钟`, "info");
}

/**
 * 测试服务器连接
 */
async function testConnection(serverUrl) {
    try {
        const baseUrl = serverUrl.replace("/api/cookies", "");
        const response = await fetch(baseUrl);
        return response.ok;
    } catch (error) {
        return false;
    }
}

// ================================
// 事件监听器
// ================================

chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name === ALARM_NAME) {
        const settings = await getSettings();
        if (settings.autoSync) {
            await performSync(false);
        }
    }
});

chrome.runtime.onInstalled.addListener(async (details) => {
    if (details.reason === "install") {
        await addLog("扩展已安装", "success");
        await setupAlarm(DEFAULT_INTERVAL);
    } else if (details.reason === "update") {
        await addLog(`扩展已更新到 v${chrome.runtime.getManifest().version}`, "info");
    }
});

chrome.runtime.onStartup.addListener(async () => {
    const settings = await getSettings();
    if (settings.autoSync) {
        await setupAlarm(settings.refreshInterval);
        await performSync(false);
    }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    (async () => {
        switch (message.action) {
            case "syncNow":
                const syncSuccess = await performSync(true);
                sendResponse({ success: syncSuccess });
                break;

            case "syncWithAccount":
                const alias = message.alias || "";
                const proxy = message.proxy || "";

                await chrome.storage.local.set({
                    currentAlias: alias,
                    currentProxy: proxy
                });

                const success = await performSync(true, alias, proxy);
                sendResponse({ success });
                break;

            case "testConnection":
                const serverUrl = message.serverUrl || DEFAULT_SERVER_URL;
                const isConnected = await testConnection(serverUrl);
                sendResponse({ success: isConnected });
                break;

            case "updateSettings":
                if (message.settings) {
                    await chrome.storage.local.set(message.settings);
                    if (message.settings.refreshInterval) {
                        await setupAlarm(message.settings.refreshInterval);
                    }
                    if (!message.settings.autoSync) {
                        await chrome.alarms.clear(ALARM_NAME);
                        await addLog("自动同步已禁用", "warning");
                    }
                }
                sendResponse({ success: true });
                break;

            case "getCookies":
                const cookies = await getAllCookies();
                sendResponse({ cookies });
                break;

            case "getHeaders":
                // 返回当前浏览器请求头
                const headers = getBrowserHeaders();
                sendResponse({ headers });
                break;

            case "clearLogs":
                await chrome.storage.local.set({ logs: [] });
                sendResponse({ success: true });
                break;

            default:
                sendResponse({ error: "Unknown action" });
        }
    })();

    return true;
});

// Cookie 变化监听
chrome.cookies.onChanged.addListener(async (changeInfo) => {
    const { cookie, removed } = changeInfo;

    if (cookie.domain.includes("google.com") && COOKIE_NAMES.includes(cookie.name)) {
        if (!removed) {
            await addLog(`检测到 ${cookie.name} 变化，触发同步`, "info");
            setTimeout(async () => {
                const settings = await getSettings();
                if (settings.autoSync) {
                    await performSync(false);
                }
            }, 1000);
        }
    }
});

console.log("[GeminiSync] 后台服务已启动 (轮询版，含请求头采集)");
