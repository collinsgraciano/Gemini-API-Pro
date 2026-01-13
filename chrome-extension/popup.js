/**
 * Gemini Cookie 同步器 - 弹窗脚本 (多账号版)
 * 支持账号别名、代理配置和账号管理
 */

// DOM 元素引用
const elements = {
    // 标签页
    tabBtns: document.querySelectorAll(".tab-btn"),
    tabContents: document.querySelectorAll(".tab-content"),

    // 状态区域
    statusIndicator: document.getElementById("statusIndicator"),
    lastSyncTime: document.getElementById("lastSyncTime"),
    cookieStatus: document.getElementById("cookieStatus"),

    // Cookie 预览
    psidPreview: document.getElementById("psidPreview"),
    psidtsPreview: document.getElementById("psidtsPreview"),

    // 账号配置
    accountAlias: document.getElementById("accountAlias"),
    accountProxy: document.getElementById("accountProxy"),
    saveAccount: document.getElementById("saveAccount"),
    accountList: document.getElementById("accountList"),
    refreshAccounts: document.getElementById("refreshAccounts"),

    // 设置
    serverUrl: document.getElementById("serverUrl"),
    refreshInterval: document.getElementById("refreshInterval"),
    autoSync: document.getElementById("autoSync"),
    saveSettings: document.getElementById("saveSettings"),

    // 操作按钮
    syncNow: document.getElementById("syncNow"),
    testConnection: document.getElementById("testConnection"),

    // 日志
    logContainer: document.getElementById("logContainer"),
    clearLog: document.getElementById("clearLog")
};

/**
 * 格式化时间戳
 */
function formatTime(timestamp) {
    if (!timestamp) return "从未";
    const date = new Date(timestamp);
    return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}

/**
 * 截断显示 Cookie 值
 */
function truncateCookie(value, length = 30) {
    if (!value) return "--";
    if (value.length <= length) return value;
    return value.substring(0, length) + "...";
}

/**
 * 更新状态指示器
 */
function updateStatusIndicator(status, text) {
    elements.statusIndicator.className = `status-indicator status-${status}`;
    elements.statusIndicator.textContent = text;
}

/**
 * 显示通知
 */
function showNotification(message, type) {
    const indicator = elements.statusIndicator;
    const originalClass = indicator.className;
    const originalText = indicator.textContent;

    indicator.className = `status-indicator status-${type}`;
    indicator.textContent = message;

    setTimeout(() => {
        indicator.className = originalClass;
        indicator.textContent = originalText;
    }, 2000);
}

/**
 * 标签页切换
 */
function switchTab(tabName) {
    elements.tabBtns.forEach(btn => {
        btn.classList.toggle("active", btn.dataset.tab === tabName);
    });
    elements.tabContents.forEach(content => {
        content.classList.toggle("active", content.id === `tab-${tabName}`);
    });
}

/**
 * 加载并显示当前状态
 */
async function loadStatus() {
    const storage = await chrome.storage.local.get({
        lastSyncTime: null,
        lastSyncStatus: "unknown",
        serverUrl: "http://localhost:8001/api/cookies",
        refreshInterval: 5,
        autoSync: true,
        currentAlias: "",
        currentProxy: ""
    });

    // 更新状态指示器
    const statusMap = {
        success: { class: "success", text: "正常" },
        error: { class: "error", text: "错误" },
        unknown: { class: "unknown", text: "未知" }
    };
    const statusInfo = statusMap[storage.lastSyncStatus] || statusMap.unknown;
    updateStatusIndicator(statusInfo.class, statusInfo.text);

    // 更新上次同步时间
    elements.lastSyncTime.textContent = `上次同步: ${formatTime(storage.lastSyncTime)}`;

    // 更新设置表单
    elements.serverUrl.value = storage.serverUrl;
    elements.refreshInterval.value = storage.refreshInterval;
    elements.autoSync.checked = storage.autoSync;

    // 更新账号配置
    elements.accountAlias.value = storage.currentAlias || "";
    elements.accountProxy.value = storage.currentProxy || "";

    // 获取当前 Cookie
    chrome.runtime.sendMessage({ action: "getCookies" }, (response) => {
        if (response && response.cookies) {
            const { cookies } = response;
            const hasPsid = !!cookies["__Secure-1PSID"];
            const hasPsidts = !!cookies["__Secure-1PSIDTS"];

            elements.psidPreview.textContent = truncateCookie(cookies["__Secure-1PSID"]);
            elements.psidtsPreview.textContent = truncateCookie(cookies["__Secure-1PSIDTS"]);

            if (hasPsid && hasPsidts) {
                elements.cookieStatus.textContent = "Cookie 状态: ✅ 已获取";
            } else if (hasPsid) {
                elements.cookieStatus.textContent = "Cookie 状态: ⚠️ 缺少 PSIDTS";
            } else {
                elements.cookieStatus.textContent = "Cookie 状态: ❌ 未登录";
            }
        }
    });
}

/**
 * 加载日志
 */
async function loadLogs() {
    const { logs = [] } = await chrome.storage.local.get("logs");

    if (logs.length === 0) {
        elements.logContainer.innerHTML = '<p class="log-empty">暂无日志</p>';
        return;
    }

    elements.logContainer.innerHTML = logs.map(log => `
    <div class="log-entry">
      <span class="log-time">${log.time}</span>
      <span class="log-${log.level}">${log.message}</span>
    </div>
  `).join("");
}

/**
 * 加载账号列表
 */
async function loadAccountList() {
    const storage = await chrome.storage.local.get({ serverUrl: "http://localhost:8001/api/cookies" });
    const baseUrl = storage.serverUrl.replace("/api/cookies", "");

    try {
        const response = await fetch(`${baseUrl}/api/accounts`);
        if (!response.ok) throw new Error("获取账号列表失败");

        const data = await response.json();

        if (data.accounts && data.accounts.length > 0) {
            elements.accountList.innerHTML = data.accounts.map(account => `
        <div class="account-item">
          <div class="account-info">
            <span class="account-alias">${account.alias}</span>
            <span class="account-proxy">${account.proxy || "无代理"}</span>
          </div>
          <div class="account-meta">
            <span class="account-status ${account.enabled ? "enabled" : "disabled"}">
              ${account.enabled ? "已启用" : "已禁用"}
            </span>
            <span class="account-time">${formatTime(account.last_updated)}</span>
          </div>
        </div>
      `).join("");
        } else {
            elements.accountList.innerHTML = '<p class="list-empty">暂无账号，请先同步</p>';
        }
    } catch (error) {
        elements.accountList.innerHTML = `<p class="list-empty">获取失败: ${error.message}</p>`;
    }
}

/**
 * 保存设置
 */
async function saveSettings() {
    const settings = {
        serverUrl: elements.serverUrl.value.trim() || "http://localhost:8001/api/cookies",
        refreshInterval: parseInt(elements.refreshInterval.value) || 5,
        autoSync: elements.autoSync.checked
    };

    chrome.runtime.sendMessage({
        action: "updateSettings",
        settings: settings
    }, (response) => {
        if (response && response.success) {
            showNotification("设置已保存", "success");
        } else {
            showNotification("保存失败", "error");
        }
    });
}

/**
 * 保存账号并上传
 */
async function saveAccountAndUpload() {
    const alias = elements.accountAlias.value.trim();
    const proxy = elements.accountProxy.value.trim();

    // 保存到本地存储
    await chrome.storage.local.set({
        currentAlias: alias,
        currentProxy: proxy
    });

    // 触发带账号信息的同步
    elements.saveAccount.disabled = true;
    elements.saveAccount.innerHTML = '<span class="btn-icon spinning">💾</span> 保存中...';

    chrome.runtime.sendMessage({
        action: "syncWithAccount",
        alias: alias,
        proxy: proxy
    }, (response) => {
        elements.saveAccount.disabled = false;
        elements.saveAccount.innerHTML = '<span class="btn-icon">💾</span> 保存并上传';

        if (response && response.success) {
            showNotification("账号已保存", "success");
            loadAccountList();
            loadStatus();
        } else {
            showNotification("保存失败", "error");
        }
    });
}

/**
 * 立即同步
 */
async function syncNow() {
    elements.syncNow.disabled = true;
    elements.syncNow.innerHTML = '<span class="btn-icon spinning">🔄</span> 同步中...';

    chrome.runtime.sendMessage({ action: "syncNow" }, (response) => {
        elements.syncNow.disabled = false;
        elements.syncNow.innerHTML = '<span class="btn-icon">🔄</span> 立即同步';

        if (response && response.success) {
            loadStatus();
            loadLogs();
        }
    });
}

/**
 * 测试服务器连接
 */
async function testConnection() {
    elements.testConnection.disabled = true;
    elements.testConnection.innerHTML = '<span class="btn-icon spinning">🔌</span> 测试中...';

    const serverUrl = elements.serverUrl.value.trim();

    chrome.runtime.sendMessage({
        action: "testConnection",
        serverUrl: serverUrl
    }, (response) => {
        elements.testConnection.disabled = false;
        elements.testConnection.innerHTML = '<span class="btn-icon">🔌</span> 测试连接';

        if (response && response.success) {
            showNotification("连接成功", "success");
        } else {
            showNotification("连接失败", "error");
        }
    });
}

/**
 * 清空日志
 */
async function clearLogs() {
    chrome.runtime.sendMessage({ action: "clearLogs" }, () => {
        loadLogs();
    });
}

// ================================
// 事件绑定
// ================================

// 标签页切换
elements.tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        switchTab(btn.dataset.tab);
        // 切换到账号标签页时刷新列表
        if (btn.dataset.tab === "accounts") {
            loadAccountList();
        }
    });
});

// 按钮事件
elements.saveSettings.addEventListener("click", saveSettings);
elements.saveAccount.addEventListener("click", saveAccountAndUpload);
elements.syncNow.addEventListener("click", syncNow);
elements.testConnection.addEventListener("click", testConnection);
elements.clearLog.addEventListener("click", clearLogs);
elements.refreshAccounts.addEventListener("click", loadAccountList);

// 监听存储变化
chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local") {
        if (changes.logs) {
            loadLogs();
        }
        if (changes.lastSyncTime || changes.lastSyncStatus) {
            loadStatus();
        }
    }
});

// ================================
// 初始化
// ================================

document.addEventListener("DOMContentLoaded", () => {
    loadStatus();
    loadLogs();
});
