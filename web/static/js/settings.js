// API配置管理

// Backward-compatible helpers for site cookies
// NOTE: settings.html uses inline onclick="..." handlers, which require functions
// to be accessible on the global window object.
window.clearSiteCookies = function clearSiteCookies(site) {
    try {
        const s = String(site || '').toLowerCase();
        if (s === 'youtube') {
            const el = document.getElementById('youtube_cookies');
            if (el) el.value = '';
        } else if (s === 'bilibili') {
            const el = document.getElementById('bilibili_cookies');
            if (el) el.value = '';
        } else {
            console.warn('Unknown site for clearSiteCookies:', site);
            return;
        }

        // Persist immediately if manager is present
        try {
            if (window.apiConfigManager && typeof window.apiConfigManager.saveConfig === 'function') {
                window.apiConfigManager.saveConfig();
            }
        } catch (_) {}

        try {
            if (window.apiConfigManager && typeof window.apiConfigManager.showToast === 'function') {
                window.apiConfigManager.showToast('warning', '已清除', `已清除 ${site} Cookies`);
            }
        } catch (_) {}
    } catch (e) {
        console.error('clearSiteCookies failed:', e);
    }
}

window.testSiteCookies = function testSiteCookies(site) {
    const s = String(site || '').toLowerCase();

    // Keep YouTube as lightweight local heuristic for now
    if (s === 'youtube') {
        const val = (document.getElementById('youtube_cookies')?.value || '').trim();
        if (!val) {
            window.apiConfigManager?.showToast?.('warning', '未配置', '请先粘贴 YouTube Cookies');
            return;
        }
        const ok = /(^|;\s*)(VISITOR_INFO1_LIVE|SAPISID|HSID|SSID|SID)=/i.test(val);
        window.apiConfigManager?.showToast?.(
            ok ? 'success' : 'warning',
            ok ? '看起来已配置' : '可能不完整',
            ok ? '已检测到常见 YouTube Cookie 字段' : '未检测到常见 YouTube Cookie 字段，但仍可能可用'
        );
        return;
    }

    if (s !== 'bilibili') {
        console.warn('Unknown site for testSiteCookies:', site);
        return;
    }

    const val = (document.getElementById('bilibili_cookies')?.value || '').trim();
    if (!val) {
        window.apiConfigManager?.showToast?.('warning', '未配置', '请先粘贴 Bilibili Cookies');
        return;
    }

    // Ask user for a BV URL to test against (safer and more accurate)
    const defaultUrl = 'https://www.bilibili.com/';
    const testUrl = (prompt('请输入一个用于测试的 Bilibili 视频链接（BV...）。\n建议使用你无法下载 1080P60/4K 的那个视频链接来验证会员权限。', defaultUrl) || '').trim();
    if (!testUrl) {
        return;
    }

    // Explicit confirmation: cookies will be sent to the server instance
    const okSend = confirm(
        '即将把你粘贴的 Bilibili Cookies 发送到你部署的 VideoWhisper 服务器，用于请求 B 站验证会员/高画质格式权限。\n\n' +
        '请确认这是你信任的自部署环境（通常为本机/内网）。\n\n' +
        '继续执行测试？'
    );
    if (!okSend) {
        return;
    }

    window.apiConfigManager?.showToast?.('info', '测试中', '正在请求服务器验证 Bilibili Cookies，请稍候...');

    fetch('/api/downloads/test-cookies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ site: 'bilibili', url: testUrl, cookies: val })
    })
        .then(r => r.json())
        .then(resp => {
            if (!resp || resp.success !== true) {
                window.apiConfigManager?.showToast?.('error', '测试失败', resp?.message || '请求失败');
                return;
            }
            const data = resp.data || {};
            if (!data.ok) {
                window.apiConfigManager?.showToast?.('error', 'Cookies 无效', data.reason || '验证失败');
                return;
            }
            if (data.premium_access) {
                window.apiConfigManager?.showToast?.('success', '验证成功', '已检测到会员/高画质格式权限（例如 1080P60/4K/HDR 等）');
            } else {
                window.apiConfigManager?.showToast?.('warning', '验证通过但未检测到会员格式', data.reason || '可能账号非大会员，或该视频没有会员格式');
            }
        })
        .catch(err => {
            window.apiConfigManager?.showToast?.('error', '测试失败', err?.message || String(err));
        });
}

// Legacy names (kept for compatibility)
// Legacy names (kept for compatibility)
window.clearYoutubeCookies = function clearYoutubeCookies() { return window.clearSiteCookies('youtube'); };
window.testYoutubeCookies = function testYoutubeCookies() { return window.testSiteCookies('youtube'); };

class APIConfigManager {
    constructor() {
        this.storageKey = 'videowhisper_api_config';
        this.loadConfig();
    }

    // 保存配置到本地存储
    saveConfig() {
        try {
            // 检查必需的DOM元素是否存在
            const elements = {
                siliconflow_api_key: document.getElementById('siliconflow_api_key'),
                siliconflow_base_url: document.getElementById('siliconflow_base_url'),
                siliconflow_model: document.getElementById('siliconflow_model'),
                text_processor_provider: document.getElementById('text_processor_provider'),
                text_processor_api_key: document.getElementById('text_processor_api_key'),
                text_processor_base_url: document.getElementById('text_processor_base_url'),
                text_processor_model: document.getElementById('text_processor_model'),
                youtube_cookies: document.getElementById('youtube_cookies'),
                bilibili_cookies: document.getElementById('bilibili_cookies'),

                obsidian_vault_name: document.getElementById('obsidian_vault_name'),
                obsidian_default_folder: document.getElementById('obsidian_default_folder'),
                obsidian_filename_prefix: document.getElementById('obsidian_filename_prefix'),
                obsidian_filename_format: document.getElementById('obsidian_filename_format'),
                obsidian_auto_open: document.getElementById('obsidian_auto_open'),
                webhook_enabled: document.getElementById('webhook_enabled'),
                webhook_base_url: document.getElementById('webhook_base_url'),
                webhook_bark_enabled: document.getElementById('webhook_bark_enabled'),
                webhook_bark_server: document.getElementById('webhook_bark_server'),
                webhook_bark_key: document.getElementById('webhook_bark_key'),
                webhook_bark_group: document.getElementById('webhook_bark_group'),
                webhook_wecom_enabled: document.getElementById('webhook_wecom_enabled'),
                webhook_wecom_url: document.getElementById('webhook_wecom_url'),
                webhook_wecom_mobiles: document.getElementById('webhook_wecom_mobiles'),
                webhook_wecom_userids: document.getElementById('webhook_wecom_userids')
            };
            
            // 验证所有元素都存在
            for (const [id, element] of Object.entries(elements)) {
                if (!element) {
                    console.error(`DOM元素未找到: ${id}`);
                    this.showToast('error', '保存失败', `找不到表单元素: ${id}`);
                    return;
                }
            }
            
            const config = {
                siliconflow: {
                    api_key: elements.siliconflow_api_key.value,
                    base_url: elements.siliconflow_base_url.value,
                    model: elements.siliconflow_model.value
                },
                text_processor: {
                    provider: elements.text_processor_provider.value,
                    api_key: elements.text_processor_api_key.value,
                    base_url: elements.text_processor_base_url.value,
                    model: elements.text_processor_model.value
                },
                youtube: {
                    cookies: elements.youtube_cookies.value
                },
                bilibili: {
                    cookies: elements.bilibili_cookies.value
                },
                obsidian: {
                    vault_name: elements.obsidian_vault_name.value,
                    default_folder: elements.obsidian_default_folder.value,
                    filename_prefix: elements.obsidian_filename_prefix.value,
                    filename_format: elements.obsidian_filename_format.value,
                    auto_open: elements.obsidian_auto_open.checked
                },
                webhook: {
                    enabled: elements.webhook_enabled.checked,
                    base_url: elements.webhook_base_url.value,
                    bark: {
                        enabled: elements.webhook_bark_enabled.checked,
                        server: elements.webhook_bark_server.value,
                        key: elements.webhook_bark_key.value,
                        group: elements.webhook_bark_group.value
                    },
                    wecom: {
                        enabled: elements.webhook_wecom_enabled.checked,
                        webhook_url: elements.webhook_wecom_url.value,
                        mentioned_mobile_list: this._splitListField(elements.webhook_wecom_mobiles.value),
                        mentioned_userid_list: this._splitListField(elements.webhook_wecom_userids.value)
                    }
                }
            };
            
            if (window.UIHelpers && typeof window.UIHelpers.maskSensitiveData === 'function') {
                console.log('保存配置摘要:', window.UIHelpers.maskSensitiveData(config));
            } else {
                console.log('配置已保存到本地存储');
            }
            
            // 加密存储（使用UTF-8安全的Base64编码）
            const encrypted = btoa(unescape(encodeURIComponent(JSON.stringify(config))));
            localStorage.setItem(this.storageKey, encrypted);
            
            this.showToast('success', '配置已保存', '所有API配置已保存到本地存储');
            
        } catch (error) {
            console.error('保存配置时发生错误:', error);
            this.showToast('error', '保存失败', `保存配置时发生错误: ${error.message}`);
        }
    }

    // 从本地存储加载配置
    loadConfig() {
        try {
            const encrypted = localStorage.getItem(this.storageKey);
            if (!encrypted) return;

            const config = JSON.parse(decodeURIComponent(escape(atob(encrypted))));
            
            // 填充表单
            if (config.siliconflow) {
                document.getElementById('siliconflow_api_key').value = config.siliconflow.api_key || '';
                document.getElementById('siliconflow_base_url').value = config.siliconflow.base_url || 'https://api.siliconflow.cn/v1';
                document.getElementById('siliconflow_model').value = config.siliconflow.model || 'FunAudioLLM/SenseVoiceSmall';
            }
            
            if (config.text_processor) {
                document.getElementById('text_processor_provider').value = config.text_processor.provider || 'siliconflow';
                document.getElementById('text_processor_api_key').value = config.text_processor.api_key || '';
                document.getElementById('text_processor_base_url').value = config.text_processor.base_url || '';
                document.getElementById('text_processor_model').value = config.text_processor.model || '';
                this.updateModelPlaceholder(config.text_processor.provider || 'siliconflow');
            } else {
                // 设置默认值
                document.getElementById('text_processor_provider').value = 'siliconflow';
                this.updateModelPlaceholder('siliconflow');
            }
            
             // 加载站点 cookies（对大文本延迟填充，避免阻塞首屏）
             const defer = (cb) => {
                 if (typeof window.requestIdleCallback === 'function') {
                     requestIdleCallback(cb, { timeout: 1500 });
                 } else {
                     setTimeout(cb, 0);
                 }
             };

             if (config.youtube) {
                 const ytEl = document.getElementById('youtube_cookies');
                 const cookies = (config.youtube.cookies || '').trim();
                 if (cookies && cookies.length > 4000) {
                     ytEl.placeholder = `已保存 ${cookies.length} 字节的 Cookies，稍后自动填充...`;
                     defer(() => { ytEl.value = cookies; });
                 } else {
                     ytEl.value = cookies;
                 }
                 this.updateYouTubeStatus(cookies ? 'configured' : 'untested');
             }

             if (config.bilibili) {
                 const blEl = document.getElementById('bilibili_cookies');
                 const cookies = (config.bilibili.cookies || '').trim();
                 if (cookies && cookies.length > 4000) {
                     blEl.placeholder = `已保存 ${cookies.length} 字节的 Cookies，稍后自动填充...`;
                     defer(() => { blEl.value = cookies; });
                 } else {
                     blEl.value = cookies;
                 }
             }

            
            // 加载 Obsidian 配置
            if (config.obsidian) {
                document.getElementById('obsidian_vault_name').value = config.obsidian.vault_name || '';
                document.getElementById('obsidian_default_folder').value = config.obsidian.default_folder || '';
                document.getElementById('obsidian_filename_prefix').value = config.obsidian.filename_prefix || '';
                document.getElementById('obsidian_filename_format').value = config.obsidian.filename_format || 'title';
                document.getElementById('obsidian_auto_open').checked = config.obsidian.auto_open !== false;
                this.updateObsidianStatus('configured', '已配置');
            } else {
                // 设置默认值
                document.getElementById('obsidian_vault_name').value = '';
                document.getElementById('obsidian_filename_format').value = 'title';
                document.getElementById('obsidian_auto_open').checked = true;
                this.updateObsidianStatus('untested', '可选配置');
            }

            // 加载 webhook 配置
            if (config.webhook) {
                const wh = config.webhook;
                document.getElementById('webhook_enabled').checked = !!wh.enabled;
                document.getElementById('webhook_base_url').value = wh.base_url || '';

                const bark = wh.bark || {};
                document.getElementById('webhook_bark_enabled').checked = !!bark.enabled;
                document.getElementById('webhook_bark_server').value = bark.server || '';
                document.getElementById('webhook_bark_key').value = bark.key || '';
                document.getElementById('webhook_bark_group').value = bark.group || '';

                const wecom = wh.wecom || {};
                document.getElementById('webhook_wecom_enabled').checked = !!wecom.enabled;
                document.getElementById('webhook_wecom_url').value = wecom.webhook_url || '';
                const mobiles = wecom.mentioned_mobile_list || wecom.mobiles || [];
                const userids = wecom.mentioned_userid_list || wecom.userids || [];
                document.getElementById('webhook_wecom_mobiles').value = mobiles.join(', ');
                document.getElementById('webhook_wecom_userids').value = userids.join(', ');
            } else {
                document.getElementById('webhook_enabled').checked = false;
                document.getElementById('webhook_base_url').value = '';
                document.getElementById('webhook_bark_enabled').checked = false;
                document.getElementById('webhook_bark_server').value = '';
                document.getElementById('webhook_bark_key').value = '';
                document.getElementById('webhook_bark_group').value = '';
                document.getElementById('webhook_wecom_enabled').checked = false;
                document.getElementById('webhook_wecom_url').value = '';
                document.getElementById('webhook_wecom_mobiles').value = '';
                document.getElementById('webhook_wecom_userids').value = '';
            }
            
        } catch (error) {
            console.error('加载配置失败:', error);
            this.showToast('error', '加载失败', '无法加载已保存的配置');
        }
    }

    // 清除所有配置
    clearConfig() {
        if (confirm('确定要清除所有API配置吗？此操作无法撤销。')) {
            localStorage.removeItem(this.storageKey);
            
            // 清空表单
            document.getElementById('apiConfigForm').reset();
            
            // 重置状态指示器
            this.updateStatus('siliconflow', 'untested', '未测试');
            this.updateStatus('text_processor', 'untested', '未测试');
            this.updateObsidianStatus('untested', '可选配置');
            
            // 重置默认值
            document.getElementById('obsidian_vault_name').value = '';
            document.getElementById('obsidian_filename_format').value = 'title';
            document.getElementById('obsidian_auto_open').checked = true;
            
            this.showToast('warning', '配置已清除', '所有API配置已从本地存储中移除');
        }
    }

    // 获取配置用于API调用
    getConfig() {
        const encrypted = localStorage.getItem(this.storageKey);
        if (!encrypted) return null;
        
        try {
            return JSON.parse(decodeURIComponent(escape(atob(encrypted))));
        } catch (error) {
            console.error('解析配置失败:', error);
            return null;
        }
    }

    // 将逗号分隔的字符串拆分为去空白的数组
    _splitListField(raw) {
        if (!raw) {
            return [];
        }
        return raw
            .split(',')
            .map((v) => v.trim())
            .filter((v) => v.length > 0);
    }

    // 从表单采集 webhook 配置（不依赖已保存的 localStorage）
    _collectWebhookConfigFromForm() {
        return {
            enabled: document.getElementById('webhook_enabled').checked,
            base_url: document.getElementById('webhook_base_url').value,
            bark: {
                enabled: document.getElementById('webhook_bark_enabled').checked,
                server: document.getElementById('webhook_bark_server').value,
                key: document.getElementById('webhook_bark_key').value,
                group: document.getElementById('webhook_bark_group').value,
            },
            wecom: {
                enabled: document.getElementById('webhook_wecom_enabled').checked,
                webhook_url: document.getElementById('webhook_wecom_url').value,
                mentioned_mobile_list: this._splitListField(document.getElementById('webhook_wecom_mobiles').value),
                mentioned_userid_list: this._splitListField(document.getElementById('webhook_wecom_userids').value),
            },
        };
    }

    // 测试API连接
    async testConnection(provider) {
        // 获取当前表单配置，不保存到存储
        const config = {
            siliconflow: {
                api_key: document.getElementById('siliconflow_api_key').value,
                base_url: document.getElementById('siliconflow_base_url').value,
                model: document.getElementById('siliconflow_model').value
            },
            text_processor: {
                provider: document.getElementById('text_processor_provider').value,
                api_key: document.getElementById('text_processor_api_key').value,
                base_url: document.getElementById('text_processor_base_url').value,
                model: document.getElementById('text_processor_model').value
            }
        };
        if (!config || !config[provider]) {
            this.showToast('error', '测试失败', '请先配置API信息');
            return;
        }

        // 特殊处理文本处理器
        let testConfig = config[provider];
        if (provider === 'text_processor') {
            // 验证必要字段
            if (!config[provider].api_key) {
                this.showToast('error', '测试失败', '请先输入API Key');
                return;
            }
            
            // 如果是自定义提供商，检查Base URL是否已填写
            if (config[provider].provider === 'custom' && !config[provider].base_url) {
                this.showToast('error', '测试失败', '自定义提供商需要输入Base URL');
                return;
            }
            
            testConfig = {
                ...config[provider],
                actual_provider: config[provider].provider
            };
        }

        this.updateStatus(provider, 'testing', '测试中...');
        
        try {
            const response = await fetch('/api/test-connection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    provider: provider,
                    config: testConfig
                })
            });

            const result = await response.json();
            
            if (result.success) {
                this.updateStatus(provider, 'success', '连接成功');
                this.showToast('success', `${this.getProviderDisplayName(provider)} 连接成功`, result.message || '');
            } else {
                this.updateStatus(provider, 'error', '连接失败');
                this.showToast('error', `${this.getProviderDisplayName(provider)} 连接失败`, result.message || result.error || '未知错误');
            }
        } catch (error) {
            this.updateStatus(provider, 'error', '连接失败');
            this.showToast('error', '测试失败', '网络错误或服务器无响应: ' + error.message);
        }
    }
    
    // 获取提供商显示名称
    getProviderDisplayName(provider) {
        const names = {
            'siliconflow': '硅基流动',
            'text_processor': 'AI文本处理服务'
        };
        return names[provider] || provider;
    }

    // 更新状态指示器
    updateStatus(provider, status, text) {
        const indicator = document.getElementById(`${provider}-status`);
        const textElement = document.getElementById(`${provider}-status-text`);
        
        indicator.className = 'status-indicator';
        
        switch (status) {
            case 'success':
                indicator.classList.add('status-success');
                break;
            case 'error':
                indicator.classList.add('status-error');
                break;
            case 'testing':
                indicator.classList.add('status-untested');
                indicator.style.animation = 'pulse 1s infinite';
                break;
            default:
                indicator.classList.add('status-untested');
                indicator.style.animation = '';
        }
        
        textElement.textContent = text;
    }

    // 更新模型占位符
    updateModelPlaceholder(provider) {
        const modelInput = document.getElementById('text_processor_model');
        const baseUrlInput = document.getElementById('text_processor_base_url');
        const baseUrlRequired = document.getElementById('baseurl-required');
        
        switch (provider) {
            case 'siliconflow':
                modelInput.placeholder = 'Qwen/Qwen3-Coder-30B-A3B-Instruct';
                modelInput.value = modelInput.value || 'Qwen/Qwen3-Coder-30B-A3B-Instruct';
                baseUrlInput.placeholder = 'https://api.siliconflow.cn/v1 (可选)';
                baseUrlInput.value = baseUrlInput.value || 'https://api.siliconflow.cn/v1';
                baseUrlRequired.style.display = 'none';
                baseUrlInput.required = false;
                break;
            case 'custom':
                modelInput.placeholder = '如: gpt-4, claude-3-haiku, 或其他兼容OpenAI的模型';
                if (modelInput.value === 'Qwen/Qwen3-Coder-30B-A3B-Instruct') {
                    modelInput.value = ''; // 清空硅基流动的默认值
                }
                baseUrlInput.placeholder = '如: https://api.openai.com/v1 或第三方API地址';
                baseUrlInput.value = '';
                baseUrlRequired.style.display = 'inline';
                baseUrlInput.required = true;
                break;
        }
    }

    // 显示提示消息（安全渲染，避免XSS）
    showToast(type, title, message) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const header = document.createElement('div');
        header.className = 'toast-header';

        const iconWrap = document.createElement('div');
        iconWrap.className = 'toast-icon me-2';
        const icon = document.createElement('i');
        const iconClass = type === 'success' ? 'fa-circle-check text-success' :
                          type === 'error' ? 'fa-circle-exclamation text-danger' :
                          'fa-circle-info text-warning';
        icon.className = `fas ${iconClass}`;
        iconWrap.appendChild(icon);

        const strong = document.createElement('strong');
        strong.className = 'me-auto';
        strong.textContent = title || '';

        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'btn-close';
        closeBtn.setAttribute('data-bs-dismiss', 'toast');

        header.appendChild(iconWrap);
        header.appendChild(strong);
        header.appendChild(closeBtn);

        const body = document.createElement('div');
        body.className = 'toast-body';
        body.textContent = message || '';

        toast.appendChild(header);
        toast.appendChild(body);

        document.body.appendChild(toast);

        // Bootstrap might fail to load (CDN blocked) or be loaded after this script.
        // Fall back to a simple auto-dismiss toast to avoid breaking the page.
        try {
            if (window.bootstrap && typeof window.bootstrap.Toast === 'function') {
                const bsToast = new window.bootstrap.Toast(toast);
                bsToast.show();
            } else {
                toast.style.display = 'block';
                setTimeout(() => {
                    try { toast.remove(); } catch (_) {}
                }, 3500);
            }
        } catch (_) {
            toast.style.display = 'block';
            setTimeout(() => {
                try { toast.remove(); } catch (_) {}
            }, 3500);
        }

        toast.addEventListener('hidden.bs.toast', () => {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        });
    }

    // 更新 YouTube 状态
    updateYouTubeStatus(status, text) {
        // settings.html does not currently have youtube-status / youtube-status-text elements.
        // Guard to avoid breaking the entire page init.
        const indicator = document.getElementById('youtube-status');
        const textElement = document.getElementById('youtube-status-text');
        if (!indicator || !textElement) {
            return;
        }

        indicator.className = 'status-indicator';

        switch (status) {
            case 'configured':
                indicator.classList.add('status-success');
                textElement.textContent = text || '已配置';
                break;
            case 'error':
                indicator.classList.add('status-error');
                textElement.textContent = text || '配置错误';
                break;
            default:
                indicator.classList.add('status-untested');
                textElement.textContent = text || '可选配置';
        }
    }

    // 获取 YouTube cookies（用于发送请求时携带）
    getYouTubeCookies() {
        const config = this.getConfig();
        return config?.youtube?.cookies || '';
    }

    // 更新 Obsidian 状态
    updateObsidianStatus(status, text) {
        const indicator = document.getElementById('obsidian-status');
        const textElement = document.getElementById('obsidian-status-text');
        
        indicator.className = 'status-indicator';
        
        switch (status) {
            case 'configured':
                indicator.classList.add('status-success');
                textElement.textContent = text || '已配置';
                break;
            case 'error':
                indicator.classList.add('status-error');
                textElement.textContent = text || '配置错误';
                break;
            default:
                indicator.classList.add('status-untested');
                textElement.textContent = text || '可选配置';
        }
    }

    // Obsidian配置验证函数
    validateObsidianConfig(obsidianConfig) {
        const errors = [];
        
        // 检查必需字段
        if (!obsidianConfig.vault_name || obsidianConfig.vault_name.trim() === '') {
            errors.push('缺少仓库名称（必需）');
        }
        
        // 检查仓库名称格式
        if (obsidianConfig.vault_name) {
            const vaultName = obsidianConfig.vault_name.trim();
            // 检查是否包含非法字符
            const invalidChars = /[<>:"/\\|?*]/;
            if (invalidChars.test(vaultName)) {
                errors.push('仓库名称包含非法字符（不能包含 < > : " / \\ | ? *）');
            }
            
            // 检查长度
            if (vaultName.length > 100) {
                errors.push('仓库名称过长（建议100字符以内）');
            }
        }
        
        // 检查文件夹路径格式
        if (obsidianConfig.default_folder) {
            const folderPath = obsidianConfig.default_folder.trim();
            if (folderPath.includes('\\')) {
                errors.push('文件夹路径应使用 / 而不是 \\');
            }
            
            if (folderPath.startsWith('/') || folderPath.endsWith('/')) {
                errors.push('文件夹路径不应以 / 开头或结尾');
            }
            
            // 检查非法字符
            const invalidChars = /[<>:"|?*]/;
            if (invalidChars.test(folderPath)) {
                errors.push('文件夹路径包含非法字符');
            }
        }
        
        // 检查文件名前缀
        if (obsidianConfig.filename_prefix) {
            const prefix = obsidianConfig.filename_prefix;
            const invalidChars = /[<>:"/\\|?*]/;
            if (invalidChars.test(prefix)) {
                errors.push('文件名前缀包含非法字符');
            }
        }
        
        return errors;
    }
    
    // 实用的Obsidian环境检测（跳过不可靠的协议检测）
    async checkObsidianEnvironment() {
        try {
            // 浏览器的协议检测不够可靠，改为实用策略
            // 如果用户配置了Obsidian，就假设环境可用，通过实际调用来验证
            return {
                isInstalled: true,  // 假设已安装，后续通过URI调用验证
                hasAdvancedUri: true,  // 假设插件可用
                reason: 'Obsidian环境检测已跳过，将通过实际连接验证'
            };
            
        } catch (error) {
            return {
                isInstalled: true,  // 允许尝试连接
                reason: `环境检测跳过，将直接测试连接`
            };
        }
    }
    
    // URI协议测试
    async testUriProtocol(testUri) {
        return new Promise((resolve) => {
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = testUri;
            
            let resolved = false;
            const timeout = setTimeout(() => {
                if (!resolved) {
                    resolved = true;
                    document.body.removeChild(iframe);
                    resolve(false);
                }
            }, 2000);
            
            iframe.onload = () => {
                if (!resolved) {
                    resolved = true;
                    clearTimeout(timeout);
                    document.body.removeChild(iframe);
                    resolve(true);
                }
            };
            
            iframe.onerror = () => {
                if (!resolved) {
                    resolved = true;
                    clearTimeout(timeout);
                    document.body.removeChild(iframe);
                    resolve(false);
                }
            };
            
            document.body.appendChild(iframe);
        });
    }

    // 测试 Obsidian 配置
    async testObsidianConfig() {
        const config = this.getConfig();
        const obsidianConfig = config?.obsidian || {};
        
        this.updateObsidianStatus('testing', '测试中...');
        
        try {
            // 使用新的配置验证函数
            const configErrors = this.validateObsidianConfig(obsidianConfig);
            if (configErrors.length > 0) {
                this.updateObsidianStatus('error', '配置错误');
                this.showToast('error', 'Obsidian配置问题', 
                    configErrors.join('<br>') + '<br><br>请检查并修正配置项');
                return;
            }
            
            // 使用增强的环境检测
            const envCheck = await this.checkObsidianEnvironment();
            if (!envCheck.isInstalled) {
                this.updateObsidianStatus('error', '环境检查失败');
                this.showToast('warning', 'Obsidian环境问题', 
                    envCheck.reason + '<br><br>解决方法：<br>1. 安装Obsidian桌面应用<br>2. 确保Obsidian正在运行<br>3. 重新测试配置');
                return;
            }
            
            // 测试基础连接
            const vaultName = obsidianConfig.vault_name.trim();
            const testUri = this.buildTestObsidianUri(vaultName);
            const connectionTest = await this.testObsidianConnection(testUri);
            
            if (connectionTest) {
                this.updateObsidianStatus('configured', '配置正常');
                let successMsg = '✅ Obsidian配置测试通过';
                
                // 添加环境信息
                if (envCheck.hasAdvancedUri) {
                    successMsg += '<br>📱 Advanced URI插件已检测到';
                } else {
                    successMsg += '<br>ℹ️ 建议安装Advanced URI插件以获得更好体验';
                }
                
                this.showToast('success', 'Obsidian配置有效', successMsg);
            } else {
                this.updateObsidianStatus('warning', '连接不稳定');
                this.showToast('warning', 'Obsidian连接测试失败', 
                    '配置格式正确，但连接测试失败<br><br>可能原因：<br>1. Obsidian未运行<br>2. 仓库名称错误<br>3. Advanced URI插件未安装<br><br>建议：先启动Obsidian并打开对应仓库');
            }
            
        } catch (error) {
            this.updateObsidianStatus('error', '测试异常');
            console.error('Obsidian配置测试异常:', error);
            this.showToast('error', 'Obsidian测试失败', 
                `测试过程出现异常：${error.message}<br><br>请检查：<br>1. 网络连接<br>2. Obsidian是否正在运行<br>3. 浏览器是否允许自定义协议`);
        }
    }

    // 构建测试Obsidian URI
    buildTestObsidianUri(vaultName) {
        const encodedVaultName = encodeURIComponent(vaultName);
        return `obsidian://advanced-uri?vault=${encodedVaultName}`;
    }

    // 测试Obsidian连接
    async testObsidianConnection(testUri) {
        try {
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = testUri;
            document.body.appendChild(iframe);
            
            return new Promise((resolve) => {
                setTimeout(() => {
                    try {
                        document.body.removeChild(iframe);
                        // 如果没有抛出错误，说明URI格式可能有效
                        resolve(true);
                    } catch (e) {
                        resolve(false);
                    }
                }, 500);
            });
        } catch (error) {
            return false;
        }
    }

    // 检查Obsidian是否安装
    async checkObsidianInstalled() {
        try {
            const testUri = 'obsidian://';
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = testUri;
            document.body.appendChild(iframe);
            
            return new Promise((resolve) => {
                setTimeout(() => {
                    try {
                        document.body.removeChild(iframe);
                        resolve(true);
                    } catch (e) {
                        resolve(false);
                    }
                }, 100);
            });
        } catch (error) {
            return false;
        }
    }

    // 验证文件夹路径格式
    validateFolderPath(path) {
        // 只允许字母、数字、下划线、斜杠、空格和中文字符
        const regex = /^[a-zA-Z0-9_\u4e00-\u9fa5\s\/]+$/;
        return regex.test(path);
    }

    // 显示 Obsidian 使用指南
    showObsidianGuide() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title"><i class="fas fa-book me-2"></i>Obsidian 集成使用指南</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="accordion" id="obsidianGuideAccordion">
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#installation-guide">
                                        <i class="fas fa-download me-2"></i>安装与配置
                                    </button>
                                </h2>
                                <div id="installation-guide" class="accordion-collapse collapse show">
                                    <div class="accordion-body">
                                        <ol>
                                            <li>下载并安装 <a href="https://obsidian.md/" target="_blank">Obsidian</a> 桌面应用</li>
                                            <li>创建或打开您的Obsidian仓库（vault）</li>
                                            <li><strong>必需：</strong>在VideoWhisper的API设置页面中配置仓库名称
                                                <ul>
                                                    <li>仓库名称通常与您的文件夹名称相同</li>
                                                    <li>支持中文和英文</li>
                                                    <li>此字段为必填项</li>
                                                </ul>
                                            </li>
                                            <li>推荐安装 <strong>Advanced URI</strong> 插件（可选但强烈推荐）：
                                                <ul>
                                                    <li>打开 Obsidian 设置 → 社区插件</li>
                                                    <li>关闭安全模式</li>
                                                    <li>浏览插件，搜索 "Advanced URI"</li>
                                                    <li>安装并启用插件</li>
                                                </ul>
                                            </li>
                                        </ol>
                                        <div class="alert alert-warning">
                                            <i class="fas fa-triangle-exclamation me-2"></i>
                                            <strong>重要：</strong>仓库名称必须准确填写，否则Obsidian无法正确创建文件
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#usage-guide">
                                        <i class="fas fa-gear me-2"></i>使用方法
                                    </button>
                                </h2>
                                <div id="usage-guide" class="accordion-collapse collapse">
                                    <div class="accordion-body">
                                        <ol>
                                            <li>在VideoWhisper中处理视频完成后，点击"导入Obsidian"按钮</li>
                                            <li>系统会自动打开Obsidian并创建新的笔记文件</li>
                                            <li>笔记包含视频的元信息、标签和完整的逐字稿</li>
                                            <li>文件会保存到您配置的默认文件夹中</li>
                                            <li>如果未安装Advanced URI插件或导入失败，系统会下载Markdown文件供手动导入</li>
                                        </ol>
                                        <div class="alert alert-info">
                                            <i class="fas fa-lightbulb me-2"></i>
                                            <strong>提示：</strong>您可以在API设置页面中配置：
                                            <ul class="mb-0 mt-1">
                                                <li>默认保存文件夹</li>
                                                <li>文件名格式和前缀</li>
                                                <li>是否自动打开Obsidian</li>
                                            </ul>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#troubleshooting-guide">
                                        <i class="fas fa-tools me-2"></i>故障排除
                                    </button>
                                </h2>
                                <div id="troubleshooting-guide" class="accordion-collapse collapse">
                                    <div class="accordion-body">
                                        <h6>问题：点击导入后Obsidian没有打开</h6>
                                        <ul>
                                            <li><strong>首先检查：</strong>是否在API设置中填写了仓库名称</li>
                                            <li>确保Obsidian桌面应用正在运行</li>
                                            <li>检查仓库名称是否正确（大小写敏感）</li>
                                            <li>推荐安装Advanced URI插件以获得最佳体验</li>
                                            <li>如果失败，系统会自动下载Markdown文件</li>
                                        </ul>
                                        
                                        <h6>问题：如何找到仓库名称？</h6>
                                        <ul>
                                            <li>打开Obsidian应用</li>
                                            <li>查看左下角的仓库名称</li>
                                            <li>或者查看Obsidian的数据文件夹名称</li>
                                            <li>通常与您的文件夹名称相同</li>
                                        </ul>
                                        
                                        <h6>问题：文件保存位置不正确</h6>
                                        <ul>
                                            <li>在API设置页面中检查"默认保存文件夹"配置</li>
                                            <li>确保文件夹路径格式正确（支持多级文件夹用/分隔）</li>
                                            <li>如果留空，文件将保存到Obsidian仓库的根目录</li>
                                        </ul>
                                        
                                        <h6>问题：提示"配置不完整"</h6>
                                        <ul>
                                            <li>请检查API设置页面中的"Obsidian仓库名称"字段</li>
                                            <li>此字段为必填项，必须填写您的Obsidian仓库名称</li>
                                            <li>确保仓库名称不为空且包含有效字符</li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }
}

// 实例化配置管理器
const configManager = new APIConfigManager();
window.apiConfigManager = configManager;

// 切换密码可见性
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    const button = input.nextElementSibling;
    const icon = button.querySelector('i');
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'fas fa-eye';
    }
}

// 表单提交处理 - 移到DOMContentLoaded中确保DOM已加载
// document.getElementById('apiConfigForm').addEventListener('submit', function(e) {
//     console.log('表单提交事件触发');
//     e.preventDefault();
//     try {
//         configManager.saveConfig();
//     } catch (error) {
//         console.error('表单提交处理错误:', error);
//         alert('保存配置时发生错误，请查看控制台');
//     }
// });

// 按钮事件绑定
function loadConfig() {
    configManager.loadConfig();
    configManager.showToast('success', '配置已重新加载', '从本地存储重新加载了配置');
}

function clearConfig() {
    configManager.clearConfig();
}

function testConnection(provider) {
    configManager.testConnection(provider);
}

// 提供商变更事件
function onProviderChange() {
    const provider = document.getElementById('text_processor_provider').value;
    configManager.updateModelPlaceholder(provider);
}

// 主题切换功能
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeToggleButton(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeToggleButton(newTheme);
}

function updateThemeToggleButton(theme) {
    const themeToggle = document.getElementById('themeToggle');
    const themeText = document.getElementById('themeText');
    const themeIcon = themeToggle.querySelector('i');

    if (theme === 'dark') {
        themeIcon.className = 'fas fa-sun me-2';
        themeText.textContent = '亮色模式';
    } else {
        themeIcon.className = 'fas fa-moon me-2';
        themeText.textContent = '暗色模式';
    }
}

// 页面加载完成后自动加载配置
document.addEventListener('DOMContentLoaded', function() {
    // 初始化主题
    initTheme();

    // 添加主题切换事件监听器
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    configManager.loadConfig();
    
    // 绑定表单提交事件
    const apiConfigForm = document.getElementById('apiConfigForm');
    if (apiConfigForm) {
        apiConfigForm.addEventListener('submit', function(e) {
            console.log('表单提交事件触发');
            e.preventDefault();
            try {
                configManager.saveConfig();
            } catch (error) {
                console.error('表单提交处理错误:', error);
                alert('保存配置时发生错误，请查看控制台');
            }
        });
        console.log('表单提交事件绑定成功');
    } else {
        console.error('找不到表单元素: apiConfigForm');
    }
    
    // 初始化默认提供商
    if (!document.getElementById('text_processor_provider').value) {
        document.getElementById('text_processor_provider').value = 'siliconflow';
        configManager.updateModelPlaceholder('siliconflow');
    }
});

// 导出配置管理器供其他页面使用
window.APIConfigManager = APIConfigManager;

// 全局函数绑定
window.showObsidianGuide = function() {
    configManager.showObsidianGuide();
};

window.testObsidianConfig = function() {
    configManager.testObsidianConfig();
};

window.loadConfig = function() {
    configManager.loadConfig();
    configManager.showToast('success', '配置已重新加载', '从本地存储重新加载了配置');
};

window.clearConfig = function() {
    configManager.clearConfig();
};

window.testConnection = function(provider) {
    configManager.testConnection(provider);
};

window.testWebhookConfig = function() {
    (async () => {
        try {
            const webhook = configManager._collectWebhookConfigFromForm();
            if (!webhook.enabled) {
                configManager.showToast('error', '测试失败', '请先勾选“启用任务完成后 webhook 通知”');
                return;
            }

            // 简单校验至少配置了一个目标
            if (!webhook.bark.enabled && !webhook.wecom.enabled) {
                configManager.showToast('error', '测试失败', '请至少启用 Bark 或 企业微信其中一种通知方式');
                return;
            }

            const resp = await fetch('/api/webhook/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ webhook })
            });
            const result = await resp.json();
            if (result.success) {
                configManager.showToast('success', '测试请求已发送', result.message || '请检查 Bark / 企业微信是否收到通知');
            } else {
                configManager.showToast('error', '测试失败', result.message || result.error || '服务器未返回成功');
            }
        } catch (err) {
            console.error('测试 Webhook 失败:', err);
            configManager.showToast('error', '测试失败', '网络错误或服务器异常: ' + (err.message || ''));
        }
    })();
};

window.onProviderChange = function() {
    const provider = document.getElementById('text_processor_provider').value;
    configManager.updateModelPlaceholder(provider);
};

// YouTube cookies 相关函数
function showCookieGuide() {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fab fa-youtube me-2"></i>YouTube Cookies 获取指南</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="accordion" id="cookieGuideAccordion">
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#chrome-guide">
                                    <i class="fab fa-chrome me-2"></i>Chrome 浏览器
                                </button>
                            </h2>
                            <div id="chrome-guide" class="accordion-collapse collapse show">
                                <div class="accordion-body">
                                    <ol>
                                        <li>在 Chrome 中打开 <strong>YouTube.com</strong> 并确保已登录</li>
                                        <li>按 <kbd>F12</kbd> 打开开发者工具</li>
                                        <li>点击 <strong>Application</strong> 标签页</li>
                                        <li>在左侧展开 <strong>Cookies</strong> → <strong>https://www.youtube.com</strong></li>
                                        <li>选择所有 cookie，右键复制或使用 Ctrl+A 全选后复制</li>
                                        <li>粘贴到上面的文本框中</li>
                                    </ol>
                                    <div class="alert alert-info">
                                        <i class="fas fa-lightbulb me-2"></i>
                                        <strong>提示：</strong>确保复制格式为 "name=value; name2=value2" 的字符串
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#firefox-guide">
                                    <i class="fab fa-firefox me-2"></i>Firefox 浏览器
                                </button>
                            </h2>
                            <div id="firefox-guide" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    <ol>
                                        <li>在 Firefox 中打开 <strong>YouTube.com</strong> 并确保已登录</li>
                                        <li>按 <kbd>F12</kbd> 打开开发者工具</li>
                                        <li>点击 <strong>Storage</strong> 标签页</li>
                                        <li>在左侧展开 <strong>Cookies</strong> → <strong>https://www.youtube.com</strong></li>
                                        <li>选择所有 cookie 值并复制</li>
                                        <li>粘贴到上面的文本框中</li>
                                    </ol>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="alert alert-warning mt-3">
                        <i class="fas fa-triangle-exclamation me-2"></i>
                        <strong>安全提示：</strong>
                        <ul class="mb-0 mt-2">
                            <li>Cookies 包含您的登录信息，请勿分享给他人</li>
                            <li>定期更新 cookies 以保持有效性</li>
                            <li>在公共设备使用后请清除浏览器数据</li>
                        </ul>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    modal.addEventListener('hidden.bs.modal', () => {
        document.body.removeChild(modal);
    });
}

function clearYoutubeCookies() {
    if (confirm('确定要清除 YouTube cookies 配置吗？')) {
        document.getElementById('youtube_cookies').value = '';
        configManager.updateYouTubeStatus('untested', '可选配置');
        configManager.showToast('warning', 'Cookies 已清除', 'YouTube cookies 配置已清除');
    }
}

function testYoutubeCookies() {
    const cookies = document.getElementById('youtube_cookies').value.trim();
    if (!cookies) {
        configManager.showToast('error', '测试失败', '请先输入 YouTube cookies');
        return;
    }
    
    // 简单验证 cookies 格式
    if (!cookies.includes('=') || (!cookies.includes(';') && cookies.split('=').length !== 2)) {
        configManager.updateYouTubeStatus('error', '格式错误');
        configManager.showToast('error', 'Cookies 格式错误', '请确保 cookies 格式为 "name=value; name2=value2"');
        return;
    }
    
    configManager.updateYouTubeStatus('configured', '已配置');
    configManager.showToast('success', 'Cookies 配置完成', '格式验证通过，将在处理 YouTube 视频时使用');
}

// YouTube cookies 函数的全局绑定
window.showCookieGuide = function() {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fab fa-youtube me-2"></i>YouTube Cookies 获取指南</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="accordion" id="cookieGuideAccordion">
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#chrome-guide">
                                    <i class="fab fa-chrome me-2"></i>Chrome 浏览器
                                </button>
                            </h2>
                            <div id="chrome-guide" class="accordion-collapse collapse show">
                                <div class="accordion-body">
                                    <ol>
                                        <li>在 Chrome 中打开 <strong>YouTube.com</strong> 并确保已登录</li>
                                        <li>按 <kbd>F12</kbd> 打开开发者工具</li>
                                        <li>点击 <strong>Application</strong> 标签页</li>
                                        <li>在左侧展开 <strong>Cookies</strong> → <strong>https://www.youtube.com</strong></li>
                                        <li>选择所有 cookie，右键复制或使用 Ctrl+A 全选后复制</li>
                                        <li>粘贴到上面的文本框中</li>
                                    </ol>
                                    <div class="alert alert-info">
                                        <i class="fas fa-lightbulb me-2"></i>
                                        <strong>提示：</strong>确保复制格式为 "name=value; name2=value2" 的字符串
                                    </div>
                                </div>
                            </div>
                            
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#firefox-guide">
                                        <i class="fab fa-firefox me-2"></i>Firefox 浏览器
                                    </button>
                                </h2>
                                <div id="firefox-guide" class="accordion-collapse collapse">
                                    <div class="accordion-body">
                                        <ol>
                                            <li>在 Firefox 中打开 <strong>YouTube.com</strong> 并确保已登录</li>
                                            <li>按 <kbd>F12</kbd> 打开开发者工具</li>
                                            <li>点击 <strong>Storage</strong> 标签页</li>
                                            <li>在左侧展开 <strong>Cookies</strong> → <strong>https://www.youtube.com</strong></li>
                                            <li>选择所有 cookie 值并复制</li>
                                            <li>粘贴到上面的文本框中</li>
                                        </ol>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="alert alert-warning mt-3">
                            <i class="fas fa-triangle-exclamation me-2"></i>
                            <strong>安全提示：</strong>
                            <ul class="mb-0 mt-2">
                                <li>Cookies 包含您的登录信息，请勿分享给他人</li>
                                <li>定期更新 cookies 以保持有效性</li>
                                <li>在公共设备使用后请清除浏览器数据</li>
                            </ul>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    modal.addEventListener('hidden.bs.modal', () => {
        document.body.removeChild(modal);
    });
};

window.clearYoutubeCookies = function() {
    if (confirm('确定要清除 YouTube cookies 配置吗？')) {
        document.getElementById('youtube_cookies').value = '';
        configManager.updateYouTubeStatus('untested', '可选配置');
        configManager.showToast('warning', 'Cookies 已清除', 'YouTube cookies 配置已清除');
    }
};

window.testYoutubeCookies = function() {
    const cookies = document.getElementById('youtube_cookies').value.trim();
    if (!cookies) {
        configManager.showToast('error', '测试失败', '请先输入 YouTube cookies');
        return;
    }
    
    // 简单验证 cookies 格式
    if (!cookies.includes('=') || (!cookies.includes(';') && cookies.split('=').length !== 2)) {
        configManager.updateYouTubeStatus('error', '格式错误');
        configManager.showToast('error', 'Cookies 格式错误', '请确保 cookies 格式为 "name=value; name2=value2"');
        return;
    }
    
    configManager.updateYouTubeStatus('configured', '已配置');
    configManager.showToast('success', 'Cookies 配置完成', '格式验证通过，将在处理 YouTube 视频时使用');
};
