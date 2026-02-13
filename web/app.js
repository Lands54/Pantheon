/**
 * Gods Temple - Interaction Logic
 */

const genesisContent = document.getElementById('genesisContent');
const coderContent = document.getElementById('coderContent');
const globalLogs = document.getElementById('globalLogs');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const currentThreadSpan = document.getElementById('currentThread');

let threadId = "temple_" + Math.random().toString(36).substr(2, 9);
currentThreadSpan.innerText = threadId;

const addLog = (msg, type = 'system') => {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerText = `[${new Date().toLocaleTimeString()}] ${msg}`;
    globalLogs.appendChild(entry);
    globalLogs.scrollTop = globalLogs.scrollHeight;
};

const updateChamber = (node, content) => {
    const target = node.toLowerCase() === 'genesis' ? genesisContent : coderContent;

    // 如果是新消息的第一块内容，清空 placeholder
    if (target.querySelector('.placeholder')) {
        target.innerHTML = '';
    }

    let bubble = target.querySelector('.active-bubble');
    if (!bubble) {
        bubble = document.createElement('div');
        bubble.className = 'message-bubble active-bubble';
        target.appendChild(bubble);
    }

    // 基础 Markdown 解析器
    const parseMarkdown = (text) => {
        return text
            .replace(/### (.*)/g, '<h3>$1</h3>')
            .replace(/\*\*(.*)\*\*/g, '<strong>$1</strong>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\[\[(.*?)\]\]/g, '<span class="tool-call">[[$1]]</span>')
            .replace(/\n/g, '<br>');
    };

    bubble.innerHTML = parseMarkdown(content);
    target.scrollTop = target.scrollHeight;
};

const finalizeChamber = (node) => {
    const target = node.toLowerCase() === 'genesis' ? genesisContent : coderContent;
    const bubble = target.querySelector('.active-bubble');
    if (bubble) {
        bubble.classList.remove('active-bubble');
    }
};

const sendOracle = async () => {
    const task = userInput.value.trim();
    if (!task) return;

    userInput.value = '';
    addLog(`神谕下达: ${task}`, 'system');

    // 清理旧状态
    document.querySelectorAll('.active-bubble').forEach(b => b.classList.remove('active-bubble'));

    try {
        const response = await fetch('/oracle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task, thread_id: threadId })
        });

        // 也可以考虑用原生 EventSource，但 POST 比较方便传 Task
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // 保持最后的碎片

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed || !trimmed.startsWith('data: ')) continue;

                try {
                    const jsonStr = trimmed.substring(6);
                    const data = JSON.parse(jsonStr);

                    if (data.error) {
                        addLog(`错误: ${data.error}`, 'system');
                    } else if (data.node) {
                        addLog(`收到来自 ${data.node} 的讯息`, 'agent');
                        updateChamber(data.node, data.content);
                    }
                } catch (e) {
                    console.debug("跳过不完整的 JSON 行:", trimmed);
                }
            }
        }
        addLog("交互序列完成。", "system");
        document.querySelectorAll('.active-bubble').forEach(b => b.classList.remove('active-bubble'));
    } catch (err) {
        addLog(`连接失败: ${err.message}`, 'system');
    }
};

sendBtn.addEventListener('click', sendOracle);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendOracle();
});

addLog("连接至众神殿服务器...", "system");

// --- 元素引用 ---
const configModal = document.getElementById('config-modal');
const settingsTrigger = document.getElementById('settings-trigger');
const saveConfigBtn = document.getElementById('saveConfigBtn');
const closeConfigBtn = document.getElementById('closeConfigBtn');

const apiKeyInput = document.getElementById('apiKeyInput');
const genesisModelInput = document.getElementById('genesisModelInput');
const coderModelInput = document.getElementById('coderModelInput');

// --- 配置同步 ---
const fetchConfig = async () => {
    try {
        const response = await fetch('/config');
        const config = await response.json();
        apiKeyInput.value = config.openrouter_api_key || '';
        genesisModelInput.value = config.agent_models.genesis || '';
        coderModelInput.value = config.agent_models.coder || '';
    } catch (err) {
        console.error("Failed to fetch config", err);
    }
};

const saveConfig = async () => {
    const newConfig = {
        openrouter_api_key: apiKeyInput.value.trim(),
        agent_models: {
            genesis: genesisModelInput.value.trim(),
            coder: coderModelInput.value.trim()
        }
    };

    try {
        const response = await fetch('/config/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newConfig)
        });
        if (response.ok) {
            addLog("系统配置已更新。", "system");
            configModal.style.display = 'none';
        }
    } catch (err) {
        addLog(`配置更新失败: ${err.message}`, "system");
    }
};

// --- 事件监听 ---
settingsTrigger.onclick = () => {
    configModal.style.display = 'flex';
    fetchConfig();
};

closeConfigBtn.onclick = () => {
    configModal.style.display = 'none';
};

saveConfigBtn.onclick = saveConfig;

window.onclick = (event) => {
    if (event.target == configModal) {
        configModal.style.display = 'none';
    }
};

// 页面初始化时也尝试拉取一次
fetchConfig();
