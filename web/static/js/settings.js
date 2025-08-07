// API配置管理
class APIConfigManager {
    constructor() {
        this.storageKey = 'videowhisper_api_config';
        this.loadConfig();
    }

    // 保存配置到本地存储
    saveConfig() {
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

        // 加密存储（简单的Base64编码，实际项目中应使用更强的加密）
        const encrypted = btoa(JSON.stringify(config));
        localStorage.setItem(this.storageKey, encrypted);
        
        this.showToast('success', '配置已保存', '所有API配置已保存到本地存储');
    }

    // 从本地存储加载配置
    loadConfig() {
        try {
            const encrypted = localStorage.getItem(this.storageKey);
            if (!encrypted) return;

            const config = JSON.parse(atob(encrypted));
            
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
            
            this.showToast('warning', '配置已清除', '所有API配置已从本地存储中移除');
        }
    }

    // 获取配置用于API调用
    getConfig() {
        const encrypted = localStorage.getItem(this.storageKey);
        if (!encrypted) return null;
        
        try {
            return JSON.parse(atob(encrypted));
        } catch (error) {
            console.error('解析配置失败:', error);
            return null;
        }
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

    // 显示提示消息
    showToast(type, title, message) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-header">
                <div class="toast-icon me-2">
                    <i class="fas ${type === 'success' ? 'fa-check-circle text-success' : 
                                   type === 'error' ? 'fa-exclamation-circle text-danger' : 
                                   'fa-info-circle text-warning'}"></i>
                </div>
                <strong class="me-auto">${title}</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">${message}</div>
        `;
        
        document.body.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        toast.addEventListener('hidden.bs.toast', () => {
            document.body.removeChild(toast);
        });
    }
}

// 实例化配置管理器
const configManager = new APIConfigManager();

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

// 表单提交处理
document.getElementById('apiConfigForm').addEventListener('submit', function(e) {
    e.preventDefault();
    configManager.saveConfig();
});

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

// 页面加载完成后自动加载配置
document.addEventListener('DOMContentLoaded', function() {
    configManager.loadConfig();
    // 初始化默认提供商
    if (!document.getElementById('text_processor_provider').value) {
        document.getElementById('text_processor_provider').value = 'siliconflow';
        configManager.updateModelPlaceholder('siliconflow');
    }
});

// 导出配置管理器供其他页面使用
window.APIConfigManager = APIConfigManager;