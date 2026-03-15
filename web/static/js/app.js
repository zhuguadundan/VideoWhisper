// 全局变量
let currentTaskId = null;
let progressInterval = null;
let currentResultData = null;
let selectedFile = null;
let uploadTaskId = null;
let uploadConfig = null;
let activeDownloadSession = null;

function setDownloadSubmitButtonState(state = 'idle') {
    const submitBtn = document.getElementById('submitDownloadBtn');
    if (!submitBtn) return;

    if (state === 'starting') {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>下载中...';
        submitBtn.classList.add('loading-shimmer');
        return;
    }

    if (state === 'active') {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-hourglass-half me-2"></i>下载进行中';
        submitBtn.classList.add('loading-shimmer');
        return;
    }

    submitBtn.disabled = false;
    submitBtn.innerHTML = '<i class="fas fa-download me-2"></i>开始下载（MP4）';
    submitBtn.classList.remove('loading-shimmer');
}

function clearActiveDownloadSession(taskId = null) {
    if (!activeDownloadSession) {
        setDownloadSubmitButtonState('idle');
        return;
    }

    if (taskId && activeDownloadSession.taskId !== taskId) {
        return;
    }

    if (activeDownloadSession.poll) {
        clearInterval(activeDownloadSession.poll);
    }
    if (activeDownloadSession.fallback) {
        clearInterval(activeDownloadSession.fallback);
    }

    activeDownloadSession = null;
    setDownloadSubmitButtonState('idle');
}

function getSafeLogPayload(payload) {
    try {
        if (window.UIHelpers && typeof window.UIHelpers.maskSensitiveData === 'function') {
            return window.UIHelpers.maskSensitiveData(payload);
        }
    } catch (_) {
        // ignore masking fallback errors
    }
    return {};
}

function stopProgressMonitoring() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

// 主题切换功能
function initTheme() {
    // 从localStorage获取保存的主题
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // 更新主题切换按钮
    updateThemeToggleButton(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);

    // 更新按钮显示
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

// 辅助函数：获取API配置
function getApiConfig() {
    try {
        const storageKey = 'videowhisper_api_config';
        const encrypted = localStorage.getItem(storageKey);
        if (!encrypted) return null;
        
        return JSON.parse(decodeURIComponent(escape(atob(encrypted))));
    } catch (error) {
        console.error('读取配置失败:', error);
        return null;
    }
}

// 辅助函数：验证配置是否有效
function hasValidConfig(config) {
    if (!config) return false;
    
    // 至少需要硅基流动的语音识别配置，或者文本处理器配置
    const hasSiliconflow = config.siliconflow && config.siliconflow.api_key;
    const hasTextProcessor = config.text_processor && config.text_processor.api_key;
    
    return hasSiliconflow || hasTextProcessor;
}

// Toast通知函数
function showToast(type, title, message) {
    let toastElement = document.getElementById('liveToast');
    // 若容器不存在，动态创建一套标准结构，避免页面缺少模板时报错
    if (!toastElement) {
        const container = document.createElement('div');
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        const toast = document.createElement('div');
        toast.id = 'liveToast';
        toast.className = 'toast';
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        const header = document.createElement('div');
        header.className = 'toast-header';
        const iconDiv = document.createElement('div');
        iconDiv.className = 'toast-icon me-2';
        const titleEl = document.createElement('strong');
        titleEl.className = 'me-auto toast-title';
        titleEl.textContent = '通知';
        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'btn-close';
        closeBtn.setAttribute('data-bs-dismiss', 'toast');
        closeBtn.setAttribute('aria-label', 'Close');
        header.appendChild(iconDiv);
        header.appendChild(titleEl);
        header.appendChild(closeBtn);
        const bodyDiv = document.createElement('div');
        bodyDiv.className = 'toast-body';
        toast.appendChild(header);
        toast.appendChild(bodyDiv);
        container.appendChild(toast);
        document.body.appendChild(container);
        toastElement = toast;
    }

    // 确保子元素存在，不存在则补齐
    let toastIcon = toastElement.querySelector('.toast-icon');
    let toastTitle = toastElement.querySelector('.toast-title');
    let toastBody = toastElement.querySelector('.toast-body');

    if (!toastIcon || !toastTitle || !toastBody) {
        let header = toastElement.querySelector('.toast-header');
        if (!header) {
            header = document.createElement('div');
            header.className = 'toast-header';
            toastElement.insertBefore(header, toastElement.firstChild);
        }
        if (!toastIcon) {
            toastIcon = document.createElement('div');
            toastIcon.className = 'toast-icon me-2';
            header.insertBefore(toastIcon, header.firstChild);
        }
        if (!toastTitle) {
            toastTitle = document.createElement('strong');
            toastTitle.className = 'me-auto toast-title';
            header.appendChild(toastTitle);
        }
        if (!header.querySelector('.btn-close')) {
            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.className = 'btn-close';
            closeBtn.setAttribute('data-bs-dismiss', 'toast');
            closeBtn.setAttribute('aria-label', 'Close');
            header.appendChild(closeBtn);
        }
        if (!toastBody) {
            toastBody = document.createElement('div');
            toastBody.className = 'toast-body';
            toastElement.appendChild(toastBody);
        }
    }
    
    // 设置图标和样式
    let iconClass = '';
    let bgClass = '';
    
    switch(type) {
        case 'success':
            iconClass = 'fas fa-circle-check text-success';
            bgClass = 'bg-success';
            break;
        case 'error':
            iconClass = 'fas fa-circle-exclamation text-danger';
            bgClass = 'bg-danger';
            break;
        case 'warning':
            iconClass = 'fas fa-triangle-exclamation text-warning';
            bgClass = 'bg-warning';
            break;
        default:
            iconClass = 'fas fa-circle-info text-info';
            bgClass = 'bg-info';
    }
    
    // 更新内容
    toastIcon.className = `${iconClass} me-2`;
    toastTitle.textContent = title;
    toastBody.textContent = message;
    
    // 显示Toast
    try {
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
    } catch (error) {
        console.warn('Bootstrap Toast初始化失败，使用console.log代替:', error);
        console.log(`[${type.toUpperCase()}] ${title}: ${message}`);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化主题
    initTheme();

    // 添加主题切换事件监听器
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    // 仅绑定事件监听，避免阻塞首屏渲染
    initializeEventListeners();

    // 非关键任务延后到空闲时执行，优先让页面完成首屏绘制
    const defer = (cb) => {
        if (typeof window.requestIdleCallback === 'function') {
            requestIdleCallback(cb, { timeout: 1500 });
        } else {
            setTimeout(cb, 0);
        }
    };

    defer(() => {
        initializeFileUpload();
        loadAvailableProvidersServerFirst();
    });

    // 任务列表加载放到稍后，避免阻塞首次交互
    setTimeout(() => {
        loadHistoryTasks();
    }, 200);
});

// 加载可用的AI提供商
async function loadAvailableProviders() {
    try {
        // 从localStorage读取API配置
        const config = getApiConfig();
        const select = document.getElementById('llmProvider');
        select.innerHTML = '';
        
        if (config && hasValidConfig(config)) {
            // 添加可用的提供商选项
            const providerNames = {
                'siliconflow': '硅基流动',
                'openai': 'OpenAI GPT-4',
                'gemini': 'Google Gemini'
            };
            
            // 检查硅基流动配置
            if (config.siliconflow && config.siliconflow.api_key) {
                const option = document.createElement('option');
                option.value = 'siliconflow';
                option.textContent = providerNames.siliconflow + ' (语音识别)';
                option.selected = true;
                select.appendChild(option);
            }
            
            // 检查文本处理器配置
            if (config.text_processor && config.text_processor.api_key) {
                const provider = config.text_processor.provider || 'siliconflow';
                const option = document.createElement('option');
                option.value = provider;
                
                // 根据提供商类型显示不同的名称
                if (provider === 'siliconflow') {
                    option.textContent = providerNames.siliconflow;
                } else if (provider === 'custom') {
                    option.textContent = '自定义 (兼容OpenAI)';
                } else {
                    option.textContent = providerNames[provider] || provider;
                }
                
                if (!config.siliconflow || !config.siliconflow.api_key) {
                    option.selected = true;
                }
                select.appendChild(option);
            }
            
            // 如果有配置，隐藏警告
            hideConfigWarning();
            const uploadSel = document.getElementById('uploadLlmProvider');
            if (uploadSel) {
                uploadSel.innerHTML = select.innerHTML;
            }
        } else {
            // 没有可用的提供商，显示警告
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '请先配置API密钥';
            option.disabled = true;
            option.selected = true;
            select.appendChild(option);
            
            const uploadSel = document.getElementById('uploadLlmProvider');
            if (uploadSel) {
                uploadSel.innerHTML = select.innerHTML;
            }
            
            showConfigWarning();
        }
    } catch (error) {
        console.error('加载提供商失败:', error);
        showConfigWarning();
    }
}

// 显示配置警告
function showConfigWarning() {
    let warning = document.getElementById('configWarning');
    if (!warning) {
        warning = document.createElement('div');
        warning.id = 'configWarning';
        warning.className = 'alert alert-warning mt-3';
        warning.innerHTML = `
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>配置提醒：</strong>请先在 
            <a href="/settings" class="alert-link">设置页面</a> 
            配置AI服务API密钥，然后刷新页面。
        `;
        
        // 插入到表单后面
        const form = document.querySelector('form');
        form.parentNode.insertBefore(warning, form.nextSibling);
    }
    warning.style.display = 'block';
    
    // 禁用提交按钮
    const submitBtn = document.getElementById('submitUrlBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-cog me-2"></i>请先配置API';
    }
    const submitUploadBtn = document.getElementById('submitUploadBtn');
    if (submitUploadBtn) {
        submitUploadBtn.disabled = true;
        submitUploadBtn.innerHTML = '<i class="fas fa-cog me-2"></i>请先配置API';
    }
}

// 隐藏配置警告
function hideConfigWarning() {
    const warning = document.getElementById('configWarning');
    if (warning) {
        warning.style.display = 'none';
    }
    
    // 启用提交按钮
    const submitBtn = document.getElementById('submitUrlBtn');
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-bolt me-2"></i>开始智能处理（仅音频）';
    }
    const submitUploadBtn = document.getElementById('submitUploadBtn');
    if (submitUploadBtn) {
        submitUploadBtn.disabled = false;
        submitUploadBtn.innerHTML = '<i class="fas fa-bolt me-2"></i>开始智能处理';
    }
}

// 文件上传相关函数
async function initializeFileUpload() {
    // 第一步：立即使用默认配置，避免阻塞用户操作
    if (!uploadConfig) {
        uploadConfig = getDefaultUploadConfig();
        console.log('已应用默认上传配置（即时可用）:', uploadConfig);
    }

    // 第二步：后台刷新服务器配置（短超时，非阻塞）
    try {
        console.log('正在初始化文件上传配置（后台刷新）...');

        const controller = new AbortController();
        const timeoutMs = 2500; // 缩短超时，降低等待感知
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        fetch('/api/upload/config', {
            signal: controller.signal,
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        })
        .then(async (response) => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                console.warn(`上传配置API响应错误: ${response.status} ${response.statusText}`);
                return null;
            }
            try {
                const result = await response.json();
                return result;
            } catch (e) {
                console.warn('解析上传配置响应失败:', e);
                return null;
            }
        })
        .then((result) => {
            if (!result) return;
            if (result.success && result.data) {
                uploadConfig = result.data;
                console.log('上传配置加载成功（已刷新）:', uploadConfig);
            } else if (result && !result.success) {
                console.warn('加载上传配置失败（保持默认）:', result.error);
            }
        })
        .catch((error) => {
            if (error && error.name === 'AbortError') {
                console.warn('文件上传配置加载超时（保持默认）');
            } else {
                console.warn('初始化文件上传配置时发生错误（保持默认）:', error && error.message ? error.message : error);
            }
        });
    } catch (error) {
        console.warn('初始化文件上传配置流程异常（保持默认）:', error.message);
    }
}

// 获取默认上传配置
function getDefaultUploadConfig() {
    return {
        max_upload_size_bytes: 500 * 1024 * 1024, // 500MB
        allowed_video_formats: ['mp4', 'avi', 'mov', 'mkv', 'webm', 'flv'],
        allowed_audio_formats: ['mp3', 'wav', 'aac', 'm4a', 'ogg'],
        max_duration_seconds: 7200 // 2小时
    };
}

// 文件选择处理
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) {
        clearFileSelection();
        return;
    }
    
    // 验证文件类型
    const fileExt = file.name.split('.').pop().toLowerCase();
    const allowedVideoTypes = uploadConfig?.allowed_video_formats || [];
    const allowedAudioTypes = uploadConfig?.allowed_audio_formats || [];
    
    if (!allowedVideoTypes.includes(fileExt) && !allowedAudioTypes.includes(fileExt)) {
        showToast('error', '不支持的文件格式', `请选择支持的文件格式：视频 (${allowedVideoTypes.join(', ')}) 或音频 (${allowedAudioTypes.join(', ')})`);
        clearFileSelection();
        return;
    }
    
    // 验证文件大小
    const maxSizeBytes = uploadConfig?.max_upload_size_bytes || 500 * 1024 * 1024;
    if (file.size > maxSizeBytes) {
        const maxSizeMB = maxSizeBytes / (1024 * 1024);
        showToast('error', '文件过大', `文件大小不能超过 ${maxSizeMB}MB`);
        clearFileSelection();
        return;
    }
    
    selectedFile = file;
    
    // 显示文件信息 - 添加安全检查
    const selectedFileNameElement = document.getElementById('selectedFileName');
    const selectedFileSizeElement = document.getElementById('selectedFileSize');
    const selectedFileTypeElement = document.getElementById('selectedFileType');
    
    if (selectedFileNameElement) {
        selectedFileNameElement.textContent = file.name;
    }
    if (selectedFileSizeElement) {
        selectedFileSizeElement.textContent = formatFileSize(file.size);
    }
    
    const fileType = allowedVideoTypes.includes(fileExt) ? 'video' : 'audio';
    if (selectedFileTypeElement) {
        selectedFileTypeElement.textContent = file.name + ` (${fileType})`;
    }
    
    // 显示文件信息区域，隐藏上传内容 - 添加安全检查
    const fileInfoElement = document.getElementById('fileInfo');
    const uploadContentElement = document.getElementById('uploadContent');
    const clearFileBtnElement = document.getElementById('clearFileBtn');
    
    if (fileInfoElement) {
        fileInfoElement.style.display = 'block';
    }
    if (uploadContentElement) {
        uploadContentElement.style.display = 'none';
    }
    if (clearFileBtnElement) {
        clearFileBtnElement.style.display = 'inline-block';
    }
    
    // 启用提交按钮
    const submitBtn = document.getElementById('submitUploadBtn');
    if (submitBtn) {
        submitBtn.disabled = false;
    }
}

// 清除文件选择
function clearFileSelection() {
    selectedFile = null;
    
    // 清除文件输入
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        fileInput.value = '';
    }
    
    // 隐藏文件信息，显示上传内容 - 添加安全检查
    const fileInfoElement = document.getElementById('fileInfo');
    const uploadContentElement = document.getElementById('uploadContent');
    const clearFileBtnElement = document.getElementById('clearFileBtn');
    
    if (fileInfoElement) {
        fileInfoElement.style.display = 'none';
    }
    if (uploadContentElement) {
        uploadContentElement.style.display = 'block';
    }
    if (clearFileBtnElement) {
        clearFileBtnElement.style.display = 'none';
    }
    
    // 禁用提交按钮
    const submitBtn = document.getElementById('submitUploadBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
    }
}

// 触发文件选择对话框
function triggerFileSelect() {
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        fileInput.click();
    }
}

// 文件拖拽处理
function setupDragAndDrop() {
    const uploadArea = document.getElementById('uploadArea');
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            // 模拟文件选择事件
            const event = { target: { files: [files[0]] } };
            handleFileSelect(event);
        }
    });
}

// 文件上传处理
async function handleFileUpload() {
    if (!selectedFile) {
        showToast('error', '请选择文件', '请先选择要上传的文件');
        return;
    }
    
    const submitBtn = document.getElementById('submitUploadBtn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-cog fa-spin me-2"></i>上传中...';
    
    // 显示上传进度（判空）
    const _uploadContent = document.getElementById('uploadContent');
    const _uploadProcessing = document.getElementById('uploadProcessing');
    if (_uploadContent) _uploadContent.style.display = 'none';
    if (_uploadProcessing) _uploadProcessing.style.display = 'block';
    
    try {
        // 使用 XMLHttpRequest 来支持上传进度
        const xhr = new XMLHttpRequest();
        const formData = new FormData();
        formData.append('file', selectedFile);
        
        // 设置上传进度监听
        xhr.upload.addEventListener('progress', function(event) {
            if (event.lengthComputable) {
                const percentComplete = Math.round((event.loaded / event.total) * 100);
                updateUploadProgress(percentComplete);
            }
        });
        
        // 设置上传完成监听
        xhr.addEventListener('load', function() {
            console.log('🎉 上传完成监听被触发 - 这是最关键的步骤');
            console.log('原始响应文本:', xhr.responseText);
            
            try {
                console.log('🔄 开始解析响应...');
                const result = JSON.parse(xhr.responseText);
                console.log('✅ 响应解析成功:', result);
                
                if (result.success) {
                    uploadTaskId = result.data.task_id;
                    console.log('🎯 文件上传成功，任务ID:', uploadTaskId);
                    console.log('📍 设置前全局变量 currentTaskId:', currentTaskId);
                    
                    currentTaskId = uploadTaskId;
                    console.log('📍 设置后全局变量 currentTaskId:', currentTaskId);
                    
                    console.log('🎯 全局变量验证 - uploadTaskId:', typeof uploadTaskId, uploadTaskId);
                    console.log('🎯 全局变量验证 - currentTaskId:', typeof currentTaskId, currentTaskId);
                    
                    showToast('success', '文件上传成功', `任务ID: ${uploadTaskId}`);
                    
                    // 延迟一下再开始处理，让用户看到上传完成
                    console.log('⏳ 将在1秒后开始处理上传的文件...');
                    setTimeout(() => {
                        console.log('🚀 setTimeout回调被触发 - 这是第二关键的步骤');
                        if (!uploadTaskId) {
                            console.error('❌ uploadTaskId为空，无法调用handleUploadProcess');
                            showToast('error', '处理失败', '任务ID为空，请重新上传文件');
                            return;
                        }
                        const tid = uploadTaskId; // 使用局部快照
                        console.log('✅ 开始调用handleUploadProcess...', tid);
                        handleUploadProcess(tid);
                    }, 1000);
                } else {
                    console.error('文件上传失败:', result.error);
                    showToast('error', '文件上传失败', result.error);
                    resetUploadForm();
                }
            } catch (parseError) {
                console.error('解析响应失败:', parseError, '响应内容:', xhr.responseText);
                showToast('error', '文件上传失败', '服务器响应格式错误');
                resetUploadForm();
            }
        });
        
        // 设置上传错误监听
        xhr.addEventListener('error', function() {
            console.error('网络上传错误');
            showToast('error', '文件上传失败', '网络连接错误');
            resetUploadForm();
        });
        
        // 设置上传超时监听
        xhr.addEventListener('timeout', function() {
            console.error('上传超时');
            showToast('error', '文件上传失败', '上传超时，请重试');
            resetUploadForm();
        });
        
        // 配置和发送请求
        xhr.open('POST', '/api/upload', true);
        xhr.timeout = 300000; // 5分钟超时
        xhr.send(formData);
        
    } catch (error) {
        console.error('文件上传失败:', error);
        showToast('error', '文件上传失败', '网络错误或服务器异常');
        resetUploadForm();
    }
}

// 更新上传进度显示
function updateUploadProgress(percent) {
    const progressBar = document.getElementById('uploadProgressBar');
    const progressInfo = document.getElementById('uploadInfo');
    
    if (progressBar) {
        progressBar.style.width = percent + '%';
        progressBar.setAttribute('aria-valuenow', percent);
    }
    
    if (progressInfo) {
        progressInfo.textContent = percent + '%';
    }
    
    console.log(`上传进度: ${percent}%`);
}

// 处理上传的文件
async function handleUploadProcess(taskId) {
    console.log(`🚀🚀🚀 handleUploadProcess函数被调用 - 这是第三关键的步骤!!!`);
    console.log(`🚀🚀🚀 传入的任务ID: ${taskId}`);
    console.log(`🚀🚀🚀 全局变量检查 - uploadTaskId: ${uploadTaskId}, currentTaskId: ${currentTaskId}`);
    
    if (!taskId) {
        console.error('❌❌❌ handleUploadProcess收到空的taskId!');
        showToast('error', '处理失败', '任务ID为空，请重新上传文件');
        return;
    }
    
    try {
        console.log(`✅✅✅ 开始处理上传文件: ${taskId}`);
        
        // 立即测试：检查关键DOM元素
        console.log('🧪 紧急DOM元素检查:');
        const statusArea = document.getElementById('statusArea');
        const taskIdElement = document.getElementById('taskId');
        const providerElement = document.getElementById('uploadLlmProvider');
        
        console.log('🔍 DOM元素检查结果:');
        console.log('  statusArea:', statusArea ? '✅ 找到' : '❌ 未找到');
        console.log('  taskIdElement:', taskIdElement ? '✅ 找到' : '❌ 未找到');
        console.log('  providerElement:', providerElement ? '✅ 找到' : '❌ 未找到');
        
        if (!statusArea || !taskIdElement) {
            console.error('❌ 关键DOM元素缺失，无法继续处理');
            showToast('error', '处理失败', '页面元素缺失，请刷新页面');
            return;
        }
        
        // 获取LLM提供商
        const provider = providerElement ? providerElement.value : 'siliconflow';
        console.log(`LLM提供商元素: ${providerElement ? '找到' : '未找到'}, 值: ${provider}`);
        
        // 获取API配置
        let config = {};
        try {
            config = getApiConfig();
            console.log('API配置获取成功（已脱敏）:', getSafeLogPayload(config));
        } catch (configError) {
            console.warn(`获取API配置失败: ${configError.message}`);
            console.log(`使用空配置继续处理`);
        }
        
        console.log('处理参数（已脱敏）:', {
            task_id: taskId,
            provider,
            api_config: getSafeLogPayload(config)
        });
        
        // 验证必要参数
        if (!taskId) {
            throw new Error('任务ID不能为空');
        }
        
        const requestData = {
            task_id: taskId,
            llm_provider: provider,
            api_config: config
        };
        
        console.log('请求数据（已脱敏）:', getSafeLogPayload(requestData));
        
        const response = await fetch('/api/process-upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        console.log(`process-upload响应状态: ${response.status}`);
        
        console.log(`process-upload响应状态: ${response.status}`);
        console.log(`process-upload响应头:`, [...response.headers.entries()]);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        // 读取响应文本用于调试
        const responseText = await response.text();
        console.log(`process-upload响应文本:`, responseText);
        
        let result;
        try {
            result = JSON.parse(responseText);
            console.log(`process-upload解析响应:`, result);
        } catch (parseError) {
            console.error(`解析JSON响应失败: ${parseError.message}`);
            console.error(`响应内容: ${responseText}`);
            throw new Error(`服务器响应格式错误: ${parseError.message}`);
        }
        
        if (result.success) {
            uploadTaskId = result.data.task_id;
            currentTaskId = uploadTaskId;
            
            console.log(`处理任务已启动: ${uploadTaskId}`);
            
            // 显示处理状态区域
            const statusArea = document.getElementById('statusArea');
            if (statusArea) {
                console.log('显示处理状态区域');
                statusArea.style.display = 'block';
            } else {
                console.warn('未找到statusArea元素');
            }
            
            const taskIdElement = document.getElementById('taskId');
            if (taskIdElement) {
                console.log(`设置任务ID元素: ${uploadTaskId}`);
                taskIdElement.textContent = uploadTaskId;
            } else {
                console.warn('未找到taskId元素');
            }
            
            // 隐藏上传区域，显示处理状态
            console.log('重置上传表单');
            resetUploadForm();
            
            // 开始轮询进度
            console.log(`开始进度监控: ${uploadTaskId}`);
            startProgressMonitoring(uploadTaskId);
            
            showToast('success', '处理已开始', '正在处理上传的文件...');
        } else {
            console.error('处理启动失败:', result.error);
            showToast('error', '处理启动失败', result.error);
            resetUploadForm();
        }
    } catch (error) {
        console.error('处理启动失败:', error);
        console.error('错误堆栈:', error.stack);
        showToast('error', '处理启动失败', `网络错误或服务器异常: ${error.message}`);
        resetUploadForm();
    }
}

// 重置上传表单
function resetUploadForm() {
    clearFileSelection();
    
    const submitBtn = document.getElementById('submitUploadBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-bolt me-2"></i>开始智能处理';
    }
    
    const uploadContent = document.getElementById('uploadContent');
    const uploadProcessing = document.getElementById('uploadProcessing');
    
    if (uploadContent) {
        uploadContent.style.display = 'block';
    }
    if (uploadProcessing) {
        uploadProcessing.style.display = 'none';
    }
    
    // 重置进度条
    const progressBar = document.getElementById('uploadProgressBar');
    const uploadInfo = document.getElementById('uploadInfo');
    
    if (progressBar) {
        progressBar.style.width = '0%';
    }
    if (uploadInfo) {
        uploadInfo.textContent = '0%';
    }
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 文件上传表单提交处理
function handleUploadFormSubmit(event) {
    event.preventDefault();
    handleFileUpload();
}

// 初始化事件监听器
function initializeEventListeners() {
    // URL处理表单提交（仅音频）
    const urlForm = document.getElementById('processUrlForm');
    if (urlForm) {
        urlForm.addEventListener('submit', handleUrlFormSubmit);
    }

    // 视频下载表单提交（支持清晰度上限选择）
    const downloadForm = document.getElementById('downloadVideoForm');
    if (downloadForm) {
        downloadForm.addEventListener('submit', handleDownloadVideoSubmit);
    }

    // 获取清晰度按钮
    const fetchQualitiesBtn = document.getElementById('fetchQualitiesBtn');
    if (fetchQualitiesBtn) {
        fetchQualitiesBtn.addEventListener('click', fetchDownloadQualities);
    }

    
    // 文件上传表单提交
    const uploadForm = document.getElementById('processUploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUploadFormSubmit);
    }
    
    // 文件选择事件
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }
    
    // 选择文件按钮
    const selectFileBtn = document.getElementById('selectFileBtn');
    if (selectFileBtn) {
        selectFileBtn.addEventListener('click', triggerFileSelect);
    }
    
    // 清除文件按钮
    const clearFileBtn = document.getElementById('clearFileBtn');
    if (clearFileBtn) {
        clearFileBtn.addEventListener('click', clearFileSelection);
    }
    
    // 设置拖拽上传
    setupDragAndDrop();
    
    // 下载按钮
    const downloadTranscriptBtn = document.getElementById('downloadTranscript');
    if (downloadTranscriptBtn) {
        downloadTranscriptBtn.addEventListener('click', () => downloadFile('transcript'));
    }
    const translateBtn = document.getElementById('translateBilingual');
    if (translateBtn) {
        translateBtn.addEventListener('click', translateBilingualHandler);
    }
    const importObsidianBtn = document.getElementById('importObsidianRoot');
    if (importObsidianBtn) {
        importObsidianBtn.addEventListener('click', () => importToObsidian(''));
    }
    const downloadSummaryBtn = document.getElementById('downloadSummary');
    if (downloadSummaryBtn) {
        downloadSummaryBtn.addEventListener('click', () => downloadFile('summary'));
    }
    
    // 刷新任务列表
    const refreshTasksBtn = document.getElementById('refreshTasks');
    if (refreshTasksBtn) {
        refreshTasksBtn.addEventListener('click', loadHistoryTasks);
    }
    
    // 停止所有任务
    const stopAllBtn = document.getElementById('stopAllTasksBtn');
    if (stopAllBtn) {
        stopAllBtn.addEventListener('click', stopAllTasks);
    }
    
}



// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 触发中英对照翻译
async function translateBilingualHandler() {
    try {
        if (!currentTaskId) {
            showAlert('没有可翻译的任务', 'warning');
            return;
        }
        if (currentResultData && currentResultData.bilingual_transcript) {
            const bilingualSection = document.getElementById('bilingualSection');
            if (bilingualSection) {
                bilingualSection.style.display = 'block';
                bilingualSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            return;
        }
        const btn = document.getElementById('translateBilingual');
        const providerSelect = document.getElementById('llmProvider');
        const provider = providerSelect ? providerSelect.value : null;
        const config = getApiConfig();
        if (!config || !hasValidConfig(config)) {
            showAlert('请先配置API密钥', 'warning');
            return;
        }
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-language me-1"></i>正在生成...';
        const resp = await fetch('/api/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: currentTaskId, llm_provider: provider, api_config: config })
        });
        const result = await resp.json();
        if (result.success) {
            showToast('info', '已开始翻译', '正在生成中英对照逐字稿');
            // 等待后端完成，沿用进度轮询即可感知 translation_status
            startProgressMonitoring(currentTaskId);
        } else {
            showToast('error', '翻译启动失败', result.error || '');
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-language me-1"></i>生成中英对照';
        }
    } catch (e) {
        console.error('翻译触发失败:', e);
        showToast('error', '翻译失败', e.message || '');
        const btn = document.getElementById('translateBilingual');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-language me-1"></i>生成中英对照';
        }
    }
}

async function fetchDownloadQualities() {
    const videoUrlEl = document.getElementById('downloadVideoUrl');
    const submitBtn = document.getElementById('submitDownloadBtn');
    const fetchBtn = document.getElementById('fetchQualitiesBtn');
    const qualitySel = document.getElementById('downloadQualitySelect');

    if (!videoUrlEl || !qualitySel) return;

    const url = (videoUrlEl.value || '').trim();
    if (!url) {
        showAlert('请输入视频URL', 'warning');
        return;
    }
    if (!isValidUrl(url)) {
        showAlert('请输入有效的URL', 'warning');
        return;
    }

    // Avoid double click
    if (fetchBtn) {
        fetchBtn.disabled = true;
        fetchBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>获取中...';
    }
    // Only disable submit if a download is currently running.
    // Fetching qualities should not trigger a download.

    try {
        const config = (() => {
            try { return getApiConfig(); } catch (_) { return {}; }
        })();

        const requestData = { url };
        if (config && config.youtube && config.youtube.cookies) {
            requestData.youtube_cookies = config.youtube.cookies;
        }
        if (config && config.bilibili && config.bilibili.cookies) {
            requestData.bilibili_cookies = config.bilibili.cookies;
        }

        const resp = await fetch('/api/downloads/formats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        const result = await resp.json();
        if (!result.success) {
            showToast('error', '获取清晰度失败', result.message || result.error || '');
            return;
        }

        const qualities = (result.data && result.data.qualities) ? result.data.qualities : [];

        // Rebuild select options
        qualitySel.innerHTML = '';
        const autoOpt = document.createElement('option');
        autoOpt.value = '';
        autoOpt.textContent = '自动（最佳）';
        autoOpt.selected = true;
        qualitySel.appendChild(autoOpt);

        if (!qualities || qualities.length === 0) {
            showToast('warning', '未发现清晰度档位', '该链接未返回可用分辨率信息，将使用自动（最佳）下载');
            return;
        }

        for (const q of qualities) {
            const opt = document.createElement('option');
            opt.value = q.format || '';
            opt.textContent = q.label || (q.height ? `${q.height}p` : '未知');
            qualitySel.appendChild(opt);
        }

        showToast('success', '清晰度已加载', `共 ${qualities.length} 个档位，可选择上限分辨率`);

    } catch (e) {
        console.error('获取清晰度失败:', e);
        showToast('error', '获取清晰度失败', e && e.message ? e.message : '网络错误');
    } finally {
        if (fetchBtn) {
            fetchBtn.disabled = false;
            fetchBtn.innerHTML = '<i class="fas fa-list me-2"></i>获取清晰度';
        }
        if (submitBtn) submitBtn.disabled = false;
    }
}

// URL验证
function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
}

    // 视频下载表单提交（支持清晰度上限选择）
    async function handleDownloadVideoSubmit(e) {
    e.preventDefault();

    const videoUrlEl = document.getElementById('downloadVideoUrl');
    const submitBtn = document.getElementById('submitDownloadBtn');
    const resultArea = document.getElementById('downloadResultArea');
    const taskIdEl = document.getElementById('downloadTaskId');
    const progressBar = document.getElementById('downloadProgressBar');
    const progressText = document.getElementById('downloadProgressText');
    const statusText = document.getElementById('downloadStatusText');
    const fileLink = document.getElementById('downloadFileLink');

    if (!videoUrlEl || !submitBtn) return;

    const url = (videoUrlEl.value || '').trim();
    if (!url) {
        showAlert('请输入视频URL', 'warning');
        return;
    }
    if (!isValidUrl(url)) {
        showAlert('请输入有效的URL', 'warning');
        return;
    }

    if (activeDownloadSession) {
        showAlert('当前已有下载任务正在进行，请等待完成后再试', 'warning');
        return;
    }

    // 避免重复提交
    if (submitBtn.disabled) return;

    setDownloadSubmitButtonState('starting');

    // Reset UI
    if (resultArea) resultArea.style.display = 'block';
    if (taskIdEl) taskIdEl.textContent = '';
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', '0');
    }
    if (progressText) progressText.textContent = '0%';
    if (statusText) statusText.textContent = '';
    if (fileLink) {
        fileLink.style.display = 'none';
        fileLink.href = '#';
    }

    let createdTaskId = null;
    let downloadSession = null;

    try {
        const config = (() => {
            try { return getApiConfig(); } catch (_) { return {}; }
        })();

        const requestData = { url };

        // Optional quality selector (upper-bound tier)
        try {
            const qualitySel = document.getElementById('downloadQualitySelect');
            const selectedFormat = qualitySel ? String(qualitySel.value || '').trim() : '';
            if (selectedFormat) {
                requestData.format = selectedFormat;
            }
        } catch (_) {
            // ignore
        }
        // Site cookies（如果有配置）
        if (config && config.youtube && config.youtube.cookies) {
            requestData.youtube_cookies = config.youtube.cookies;
        }
        if (config && config.bilibili && config.bilibili.cookies) {
            requestData.bilibili_cookies = config.bilibili.cookies;
        }

        const response = await fetch('/api/downloads', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        const result = await response.json();
        if (!result.success) {
            showAlert(result.message || result.error || '创建下载任务失败', 'danger');
            return;
        }

        const taskId = result.data && result.data.task_id;
        if (!taskId) {
            showAlert('创建下载任务失败：缺少任务ID', 'danger');
            return;
        }

        createdTaskId = taskId;
        downloadSession = { taskId, poll: null, fallback: null };
        activeDownloadSession = downloadSession;
        setDownloadSubmitButtonState('active');

        if (taskIdEl) taskIdEl.textContent = taskId;
        if (statusText) statusText.textContent = '任务已创建，开始下载...';

        let fallback = null;
        const failDownloadSession = (message, title = '下载失败', level = 'error') => {
            clearActiveDownloadSession(taskId);
            if (statusText) {
                statusText.textContent = message || title;
            }
            showToast(level, title, message || '');
        };

        // Poll progress via existing endpoint
        const poll = setInterval(async () => {
            try {
                const resp = await fetch(`/api/progress/${taskId}`);
                let pr = null;
                try {
                    pr = await resp.json();
                } catch (_) {
                    if (!resp.ok) {
                        failDownloadSession(`无法获取下载进度（HTTP ${resp.status}）`);
                    }
                    return;
                }

                if (!resp.ok || !pr.success) {
                    const message = pr?.message || pr?.error || `无法获取下载进度（HTTP ${resp.status}）`;
                    failDownloadSession(message);
                    return;
                }

                const data = pr.data || {};
                const pct = typeof data.progress === 'number' ? data.progress : 0;
                const stage = data.progress_stage || '';
                const detail = data.progress_detail || '';

                if (progressBar) {
                    progressBar.style.width = `${pct}%`;
                    progressBar.setAttribute('aria-valuenow', String(pct));
                }
                if (progressText) progressText.textContent = `${pct}%`;
                if (statusText) statusText.textContent = [stage, detail].filter(Boolean).join(' - ');

                if (data.status === 'completed') {
                    clearActiveDownloadSession(taskId);
                    if (fileLink) {
                        fileLink.href = `/api/downloads/${taskId}/file`;
                        fileLink.style.display = 'inline-block';
                    }
                    showToast('success', '下载完成', '视频已下载，可点击下载文件');
                }

                if (data.status === 'failed') {
                    failDownloadSession(data.error_message || data.error || '');
                }
            } catch (e2) {
                // ignore transient errors while polling
            }
        }, 1000);
        downloadSession.poll = poll;

        // Ensure the UI eventually shows the file link even if progress polling misses the terminal state.
        // This happens when the backend finishes very quickly or the progress endpoint returns cached intermediate state.
        const maxWaitMs = 5 * 60 * 1000;
        const startedAt = Date.now();
        fallback = setInterval(async () => {
            if (Date.now() - startedAt > maxWaitMs) {
                clearActiveDownloadSession(taskId);
                if (statusText) {
                    statusText.textContent = '下载状态查询超时，请稍后重试';
                }
                showToast('warning', '下载状态超时', '长时间未获取到下载完成状态，请稍后刷新页面确认结果');
                return;
            }
            try {
                const f = await fetch(`/api/downloads/${taskId}/file`, { method: 'HEAD' });
                if (f.ok) {
                    clearActiveDownloadSession(taskId);
                    if (fileLink) {
                        fileLink.href = `/api/downloads/${taskId}/file`;
                        fileLink.style.display = 'inline-block';
                    }
                    showToast('success', '下载完成', '视频已下载，可点击下载文件');
                }
            } catch (_) {
                // ignore
            }
        }, 1500);
        downloadSession.fallback = fallback;

    } catch (error) {
        clearActiveDownloadSession(createdTaskId);
        console.error('下载任务创建失败:', error);
        showAlert('请求失败: ' + (error.message || '网络错误'), 'danger');
    } finally {
        if (activeDownloadSession && activeDownloadSession.taskId === createdTaskId) {
            setDownloadSubmitButtonState('active');
        } else if (!activeDownloadSession) {
            clearActiveDownloadSession(createdTaskId);
        }
    }
}

// 处理URL表单提交
async function handleUrlFormSubmit(e) {
    e.preventDefault();
    
    const videoUrl = document.getElementById('videoUrl').value.trim();
    const llmProvider = document.getElementById('llmProvider').value;
    const submitBtn = document.getElementById('submitUrlBtn');
    
    if (!videoUrl) {
        showAlert('请输入视频URL', 'warning');
        return;
    }
    
    if (!llmProvider) {
        showAlert('请先配置AI服务API密钥', 'warning');
        return;
    }
    
    // 获取API配置
    const config = getApiConfig();
    if (!config || !hasValidConfig(config)) {
        showAlert('请先配置API密钥', 'warning');
        return;
    }
    
    // 若已有进行中的任务，避免重复提交（部分浏览器扩展/回车可能触发多次）
    if (progressInterval) {
        showAlert('已有任务在处理，请等待完成或完成后再提交', 'info');
        return;
    }

    // 禁用提交按钮
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>处理中...';
    submitBtn.classList.add('loading-shimmer');
    
    try {
        const requestData = {
            video_url: videoUrl,
            llm_provider: llmProvider,
            api_config: config  // 传递API配置
        };
        
        // 添加 YouTube cookies（如果有配置）
        if (config && config.youtube && config.youtube.cookies) {
            requestData.youtube_cookies = config.youtube.cookies;
        }
        if (config && config.bilibili && config.bilibili.cookies) {
            requestData.bilibili_cookies = config.bilibili.cookies;
        }
        
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentTaskId = result.data.task_id;
            currentResultData = null;
            showStatusArea();
            startProgressMonitoring();
            showAlert(result.message, 'success');
        } else {
            // 显示具体的错误信息
            let errorMessage = result.message || result.error || '处理失败';
            if (result.error_type) {
                errorMessage += ` (${result.error_type})`;
            }
            showAlert(errorMessage, 'danger');
        }
        
    } catch (error) {
        console.error('请求失败:', error);
        // 网络错误或其他连接问题
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showAlert('网络连接失败，请检查网络连接', 'danger');
        } else if (error.name === 'SyntaxError') {
            showAlert('服务器响应格式错误，请稍后重试', 'danger');
        } else {
            showAlert('请求失败: ' + error.message, 'danger');
        }
    } finally {
        // 重新启用提交按钮
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-bolt me-2"></i>开始智能处理（仅音频）';
        submitBtn.classList.remove('loading-shimmer');
    }
}

// 显示状态区域
function showStatusArea() {
    const statusArea = document.getElementById('statusArea');
    const resultArea = document.getElementById('resultArea');
    
    statusArea.style.display = 'block';
    statusArea.classList.add('fade-in');
    resultArea.style.display = 'none';
    
    // 设置任务ID显示
    document.getElementById('taskId').textContent = `任务ID: ${currentTaskId}`;
    
    // 滚动到状态区域
    setTimeout(() => {
        statusArea.scrollIntoView({ behavior: 'smooth' });
    }, 100);
}

// 开始进度监控
function startProgressMonitoring(taskId = null) {
    // 如果传入了taskId，设置currentTaskId
    if (taskId) {
        console.log(`startProgressMonitoring收到任务ID: ${taskId}`);
        currentTaskId = taskId;
    }
    console.log(`startProgressMonitoring启动，当前任务ID: ${currentTaskId}`);
    stopProgressMonitoring();

    progressInterval = setInterval(async () => {
        if (!currentTaskId) return;

        try {
            const response = await fetch(`/api/progress/${currentTaskId}`);

            if (!response.ok) {
                if (response.status === 404) {
                    showAlert('任务不存在，可能已被删除', 'warning');
                    stopProgressMonitoring();
                    return;
                } else if (response.status >= 500) {
                    showAlert('服务器错误，无法获取进度信息', 'danger');
                    stopProgressMonitoring();
                    return;
                }
            }

            const result = await response.json();

            if (result.success) {
                const data = result.data;
                updateProgress(data);

                const ts = data.translation_status || '';
                const isTaskCompleted = data.status === 'completed';

                if (isTaskCompleted && ts === 'processing') {
                    // 任务已完成，但翻译在进行中：继续轮询直到翻译完成
                    return;
                }

                if (isTaskCompleted && ts === 'completed') {
                    stopProgressMonitoring();
                    await loadResults();
                    return;
                }

                if (isTaskCompleted && !ts) {
                    // 没有翻译，正常结束
                    stopProgressMonitoring();
                    await loadResults();
                    return;
                }

                if (data.status === 'failed') {
                    stopProgressMonitoring();
                    let errorMsg = data.error_message || '处理失败';
                    if (typeof errorMsg === 'string' && /^'?url'?$/.test(errorMsg.trim())) {
                        errorMsg = '视频信息返回不完整或站点暂不支持，请更换链接或稍后重试';
                    }
                    showAlert('处理失败: ' + errorMsg, 'danger');
                }
            } else {
                // API返回失败结果
                stopProgressMonitoring();
                showAlert(result.message || result.error || '无法获取进度信息', 'danger');
            }

            // 当翻译进行中时，给出轻提示
            if (result.success && result.data.translation_status === 'processing') {
                console.debug('翻译进行中...');
            }
        } catch (error) {
            console.error('获取进度失败:', error);
            // 网络错误不立即停止轮询，给用户一些容错时间
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                console.warn('网络连接问题，继续尝试获取进度...');
            } else {
                stopProgressMonitoring();
                showAlert('无法连接到服务器，进度监控已停止', 'warning');
            }
        }
    }, 2000);
}

// 更新进度显示
// 更新进度显示
function updateProgress(data) {
    const statusText = document.getElementById('statusText');
    const progressText = document.getElementById('progressText');
    const progressBar = document.getElementById('progressBar');
    const progressDetails = document.getElementById('progressDetails');
    const progressStage = document.getElementById('progressStage');
    const progressDetail = document.getElementById('progressDetail');
    const segmentProgress = document.getElementById('segmentProgress');
    const estimatedTime = document.getElementById('estimatedTime');
    const videoInfo = document.getElementById('videoInfo');
    const translateBtn = document.getElementById('translateBilingual');
    
    let statusMessage = '';
    
    switch (data.status) {
        case 'pending':
            statusMessage = '排队等待中...';
            progressDetails.style.display = 'none';
            break;
        case 'processing':
            // 使用服务器提供的详细阶段信息
            statusMessage = data.progress_stage || '处理中...';
            progressDetails.style.display = 'block';
            
            // 显示详细阶段信息
            if (data.progress_stage) {
                let stageIcon = getStageIcon(data.progress_stage);
                progressStage.textContent = '';
const __icoStage = document.createElement('span');
__icoStage.innerHTML = getStageIcon(String(data.progress_stage));
progressStage.appendChild(__icoStage);
const __strongStage = document.createElement('strong');
__strongStage.className = 'ms-1';
__strongStage.textContent = '当前阶段:';
progressStage.appendChild(__strongStage);
progressStage.appendChild(document.createTextNode(' ' + String(data.progress_stage)));
            }
            
            // 安全渲染详细进度与AI响应信息
progressDetail.textContent = '';
if (data.progress_detail) {
    const __icoInfo = document.createElement('i');
    __icoInfo.className = 'fas fa-info-circle me-1';
    progressDetail.appendChild(__icoInfo);
    progressDetail.appendChild(document.createTextNode(String(data.progress_detail)));
}
if (data.ai_response_times && Object.keys(data.ai_response_times).length > 0) {
    const __timing = document.createElement('div');
    __timing.className = 'ai-timing-info mt-2';
    const __addTiming = (label, val) => {
        if (val === undefined || val === null) return;
        const sm = document.createElement('small');
        sm.className = 'text-muted me-2';
        const i = document.createElement('i');
        i.className = 'fas fa-stopwatch me-1';
        sm.appendChild(i);
        sm.appendChild(document.createTextNode(`${label}: ${Number(val).toFixed(1)}s`));
        __timing.appendChild(sm);
    };
    __addTiming('逐字稿生成', data.ai_response_times.transcript);
    __addTiming('摘要生成', data.ai_response_times.summary);
    __addTiming('内容分析', data.ai_response_times.analysis);
    progressDetail.appendChild(__timing);
}
            
            // 显示逐字稿预览（如果已经生成）
            if (data.transcript_ready && data.transcript_preview) {
                showTranscriptPreview(data.transcript_preview, data.full_transcript);
            }
            
            // 显示音频段处理进度（仅在语音转文字阶段）
            if (data.total_segments > 1 && data.progress_stage === '语音转文字') {
                segmentProgress.style.display = 'block';
                segmentProgress.textContent = '';
const __icoSeg = document.createElement('i');
__icoSeg.className = 'fas fa-tasks me-1';
segmentProgress.appendChild(__icoSeg);
const __strongSeg = document.createElement('strong');
__strongSeg.textContent = '片段进度:';
segmentProgress.appendChild(__strongSeg);
segmentProgress.appendChild(document.createTextNode(` ${data.processed_segments}/${data.total_segments} 个音频片段`));
            } else {
                segmentProgress.style.display = 'none';
            }
            
            // 显示预估剩余时间
            if (data.estimated_time && data.estimated_time > 0) {
                estimatedTime.style.display = 'block';
                const minutes = Math.ceil(data.estimated_time / 60);
                estimatedTime.textContent = '';
const __icoTime = document.createElement('i');
__icoTime.className = 'fas fa-clock me-1';
estimatedTime.appendChild(__icoTime);
const __strongTime = document.createElement('strong');
__strongTime.textContent = '预计还需:';
estimatedTime.appendChild(__strongTime);
estimatedTime.appendChild(document.createTextNode(` ${minutes} 分钟`));
            } else {
                estimatedTime.style.display = 'none';
            }
            break;
        case 'completed':
            statusMessage = '处理完成!';
            progressDetails.style.display = 'block';
            progressStage.textContent = '';
{ const i = document.createElement('i'); i.className = 'fas fa-check-circle text-success me-1'; progressStage.appendChild(i); const s = document.createElement('strong'); s.textContent = '已完成:'; progressStage.appendChild(s); progressStage.appendChild(document.createTextNode(' 所有文件已生成')); }
            progressDetail.textContent = '';
{ const i = document.createElement('i'); i.className = 'fas fa-download me-1'; progressDetail.appendChild(i); progressDetail.appendChild(document.createTextNode('您现在可以下载结果文件')); }
            segmentProgress.style.display = 'none';
            estimatedTime.style.display = 'none';
            break;
        case 'failed':
            statusMessage = '处理失败';
            progressDetails.style.display = 'block';
            progressStage.textContent = '';
{ const i = document.createElement('i'); i.className = 'fas fa-exclamation-triangle text-danger me-1'; progressStage.appendChild(i); const s = document.createElement('strong'); s.textContent = '错误:'; progressStage.appendChild(s); progressStage.appendChild(document.createTextNode(' 处理失败')); }
            if (data.error_message) {
                progressDetail.textContent = '';
{ const i = document.createElement('i'); i.className = 'fas fa-info-circle me-1'; progressDetail.appendChild(i); progressDetail.appendChild(document.createTextNode(String(data.error_message))); }
            }
            segmentProgress.style.display = 'none';
            estimatedTime.style.display = 'none';
            break;
    }

    // 根据翻译状态更新按钮文案/状态
    if (translateBtn) {
        if (data.translation_status === 'processing') {
            translateBtn.disabled = true;
            translateBtn.innerHTML = '<i class="fas fa-language me-1"></i>正在生成...';
        } else if (data.translation_status === 'completed') {
            translateBtn.disabled = false;
            translateBtn.innerHTML = '<i class="fas fa-language me-1"></i>查看中英对照';
        } else {
            translateBtn.disabled = false;
            translateBtn.innerHTML = '<i class="fas fa-language me-1"></i>生成中英对照';
        }
    }
    
    statusText.textContent = statusMessage;
    progressText.textContent = `${data.progress}%`;
    progressBar.style.width = `${data.progress}%`;
    progressBar.setAttribute('aria-valuenow', data.progress);
    
    // 显示视频信息
    if (data.video_title) {
        document.getElementById('videoTitle').textContent = data.video_title;
        if (data.video_duration) {
            const duration = formatDuration(data.video_duration);
            document.getElementById('videoDuration').textContent = duration;
        }
        if (data.video_uploader) {
            document.getElementById('videoUploader').textContent = data.video_uploader;
        }
        videoInfo.style.display = 'block';
    }
}

// 获取阶段图标
function getStageIcon(stage) {
    const icons = {
        '获取视频信息': '<i class="fas fa-info-circle text-primary me-1"></i>',
        '下载音频': '<i class="fas fa-download text-info me-1"></i>',
        '处理音频': '<i class="fas fa-wave-square text-warning me-1"></i>',
        '语音转文字': '<i class="fas fa-microphone text-success me-1"></i>',
        '生成逐字稿': '<i class="fas fa-robot text-primary me-1 fa-spin"></i>',
        '生成总结报告': '<i class="fas fa-brain text-info me-1 fa-spin"></i>',
        '内容分析': '<i class="fas fa-search text-warning me-1 fa-spin"></i>',
        '保存结果': '<i class="fas fa-save text-secondary me-1"></i>',
        '完成': '<i class="fas fa-check-circle text-success me-1"></i>'
    };
    return icons[stage] || '<i class="fas fa-cog fa-spin me-1"></i>';
}

// 显示逐字稿预览
function showTranscriptPreview(preview, fullTranscript) {
    let previewDiv = document.getElementById('transcriptPreview');
    if (!previewDiv) {
        previewDiv = document.createElement('div');
        previewDiv.id = 'transcriptPreview';
        previewDiv.className = 'mt-3 p-3 bg-light border rounded fade-in';
        // 插入到进度详情后面
        const progressDetails = document.getElementById('progressDetails');
        progressDetails.appendChild(previewDiv);
    }

    // 清空容器，安全渲染
    previewDiv.textContent = '';

    const title = document.createElement('h6');
    const icon = document.createElement('i');
    icon.className = 'fas fa-file-lines me-2 text-primary';
    title.appendChild(icon);
    title.appendChild(document.createTextNode('逐字稿预览 '));
    const sm = document.createElement('small');
    sm.className = 'text-muted';
    sm.textContent = '(可先查看内容)';
    title.appendChild(sm);

    const content = document.createElement('div');
    content.className = 'transcript-content';
    content.style.maxHeight = '200px';
    content.style.overflowY = 'auto';
    content.style.background = 'white';
    content.style.padding = '10px';
    content.style.border = '1px solid #dee2e6';
    content.style.borderRadius = '4px';
    content.style.fontSize = '0.9em';
    content.style.lineHeight = '1.5';
    content.style.whiteSpace = 'pre-wrap';
    content.textContent = preview || '';

    const actions = document.createElement('div');
    actions.className = 'mt-2';
    const btn = document.createElement('button');
    btn.className = 'btn btn-sm btn-outline-primary';
    btn.innerHTML = '<i class="fas fa-expand me-1"></i>查看完整逐字稿';
    btn.addEventListener('click', showFullTranscript);
    actions.appendChild(btn);

    previewDiv.appendChild(title);
    previewDiv.appendChild(content);
    previewDiv.appendChild(actions);

    // 存储完整逐字稿
    previewDiv.dataset.fullTranscript = fullTranscript || '';
    previewDiv.style.display = 'block';
}

// 新增：优先从后端探测提供商，失败时回退到本地存储
async function loadAvailableProvidersServerFirst() {
    const select = document.getElementById('llmProvider');
    if (!select) return;
    select.innerHTML = '';

    const providerNames = {
        'siliconflow': '硅基流动',
        'openai': 'OpenAI GPT-4',
        'gemini': 'Google Gemini',
        'custom': '自定义(兼容OpenAI)'
    };

    // 1) 后端探测（依据服务端config.yaml）
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000);
        const resp = await fetch('/api/providers', { signal: controller.signal, headers: { 'Accept': 'application/json' } });
        clearTimeout(timeoutId);
        if (resp.ok) {
            const payload = await resp.json();
            const providers = (payload && payload.data && Array.isArray(payload.data.providers)) ? payload.data.providers : [];
            if (payload && payload.success && providers.length > 0) {
                const def = (payload.data && payload.data.default) ? payload.data.default : providers[0];
                for (const p of providers) {
                    const opt = document.createElement('option');
                    opt.value = p;
                    opt.textContent = providerNames[p] || p;
                    if (p === def) opt.selected = true;
                    select.appendChild(opt);
                }
                const uploadSel = document.getElementById('uploadLlmProvider');
                if (uploadSel) uploadSel.innerHTML = select.innerHTML;
                hideConfigWarning();
                return; // 成功则不再回退
            }
        }
    } catch (_) {
        // 忽略探测失败
    }

    // 2) 回退：本地存储方案
    await loadAvailableProviders();
}

// 显示完整逐字稿
function showFullTranscript() {
    const previewDiv = document.getElementById('transcriptPreview');
    const fullTranscript = (previewDiv && previewDiv.dataset.fullTranscript) || '';

    // 创建模态框显示完整逐字稿（安全渲染）
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'transcriptModal';

    const dialog = document.createElement('div');
    dialog.className = 'modal-dialog modal-lg';
    const content = document.createElement('div');
    content.className = 'modal-content';

    const header = document.createElement('div');
    header.className = 'modal-header';
    const title = document.createElement('h5');
    title.className = 'modal-title';
    const icon = document.createElement('i');
    icon.className = 'fas fa-file-lines me-2';
    title.appendChild(icon);
    title.appendChild(document.createTextNode('完整逐字稿'));
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn-close';
    closeBtn.setAttribute('data-bs-dismiss', 'modal');
    header.appendChild(title);
    header.appendChild(closeBtn);

    const body = document.createElement('div');
    body.className = 'modal-body';
    const transcriptBox = document.createElement('div');
    transcriptBox.className = 'transcript-content';
    Object.assign(transcriptBox.style, {
        maxHeight: '60vh',
        overflowY: 'auto',
        background: '#f8f9fa',
        padding: '15px',
        borderRadius: '4px',
        fontSize: '0.95em',
        lineHeight: '1.6',
        whiteSpace: 'pre-wrap'
    });
    transcriptBox.textContent = fullTranscript;
    body.appendChild(transcriptBox);

    const footer = document.createElement('div');
    footer.className = 'modal-footer';
    const btnClose = document.createElement('button');
    btnClose.type = 'button';
    btnClose.className = 'btn btn-secondary';
    btnClose.setAttribute('data-bs-dismiss', 'modal');
    btnClose.textContent = '关闭';
    const btnCopy = document.createElement('button');
    btnCopy.type = 'button';
    btnCopy.className = 'btn btn-primary';
    btnCopy.innerHTML = '<i class="fas fa-copy me-1"></i>复制文本';
    btnCopy.addEventListener('click', () => copyToClipboard(fullTranscript));
    footer.appendChild(btnClose);
    footer.appendChild(btnCopy);

    content.appendChild(header);
    content.appendChild(body);
    content.appendChild(footer);
    dialog.appendChild(content);
    modal.appendChild(dialog);

    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    modal.addEventListener('hidden.bs.modal', () => {
        if (modal.parentNode) modal.parentNode.removeChild(modal);
    });
}

// 复制到剪贴板
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showAlert('已复制到剪贴板', 'success');
    }).catch(err => {
        console.error('复制失败:', err);
        showAlert('复制失败', 'warning');
    });
}

// 格式化时长显示
function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}

// 加载处理结果
async function loadResults() {
    if (!currentTaskId) {
        console.error('loadResults: currentTaskId为空');
        showToast('error', '加载失败', '没有有效的任务ID');
        return;
    }
    
    console.log(`loadResults: 开始加载任务结果，任务ID: ${currentTaskId}`);
    
    try {
        const response = await fetch(`/api/result/${currentTaskId}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                showToast('warning', '加载失败', '任务结果不存在，可能任务未完成或已被删除');
                return;
            } else if (response.status >= 500) {
                showToast('error', '加载失败', '服务器错误，无法加载结果');
                return;
            }
        }
        
        const result = await response.json();
        
        if (result.success) {
            console.log(`loadResults: 结果加载成功，任务ID: ${currentTaskId}`);
            currentResultData = result.data;
            displayResults(result.data);
            showResultArea();
            loadHistoryTasks(); // 刷新历史任务
            
            // 确保下载按钮可用
            const downloadTranscriptBtn = document.getElementById('downloadTranscript');
            const downloadSummaryBtn = document.getElementById('downloadSummary');
            const importObsidianBtn = document.getElementById('importObsidianRoot');
            const translateBtn = document.getElementById('translateBilingual');
            
            if (downloadTranscriptBtn) {
                downloadTranscriptBtn.disabled = false;
                console.log('loadResults: 下载逐字稿按钮已启用');
            }
            if (translateBtn) {
                translateBtn.disabled = false;
                if (result.data && result.data.bilingual_transcript) {
                    translateBtn.innerHTML = '<i class="fas fa-language me-1"></i>查看中英对照';
                } else {
                    translateBtn.innerHTML = '<i class="fas fa-language me-1"></i>生成中英对照';
                }
            }
            if (downloadSummaryBtn) {
                downloadSummaryBtn.disabled = false;
                console.log('loadResults: 下载总结报告按钮已启用');
            }
            if (importObsidianBtn) {
                importObsidianBtn.disabled = false;
                console.log('loadResults: 导入Obsidian按钮已启用');
            }
        } else {
            console.error(`loadResults: 加载失败 - ${result.message || result.error}`);
            showToast('error', '加载失败', result.message || result.error || '加载结果失败');
        }
    } catch (error) {
        console.error('loadResults: 加载结果失败:', error);
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showToast('error', '加载失败', '网络连接失败，无法加载结果');
        } else if (error.name === 'SyntaxError') {
            showToast('error', '加载失败', '服务器响应格式错误');
        } else {
            showToast('error', '加载失败', `加载结果失败: ${error.message}`);
        }
    }
}

// 显示结果
function displayResults(data) {
    // 更新视频信息
    if (data.video_info) {
        document.getElementById('videoTitle').textContent = data.video_info.title;
        document.getElementById('videoUploader').textContent = data.video_info.uploader;
        document.getElementById('videoDuration').textContent = formatDuration(data.video_info.duration);
    }
    
    // 显示逐字稿
    document.getElementById('transcriptContent').textContent = data.transcript;
    const bilingualSection = document.getElementById('bilingualSection');
    const bilingualContent = document.getElementById('bilingualTranscriptContent');
    if (bilingualSection && bilingualContent) {
        if (data.bilingual_transcript) {
            bilingualSection.style.display = 'block';
            bilingualContent.textContent = data.bilingual_transcript;
        } else {
            bilingualSection.style.display = 'none';
            bilingualContent.textContent = '';
        }
    }
    
    // 显示总结
    if (data.summary) {
        document.getElementById('briefSummary').textContent = data.summary.brief_summary || '无';
        
        // 处理关键词显示
        const keywordsContainer = document.getElementById('keywords');
        if (data.summary.keywords) {
            const keywords = Array.isArray(data.summary.keywords) ? 
                data.summary.keywords : data.summary.keywords.split(',').map(k => k.trim());
            // 安全渲染关键词
            keywordsContainer.textContent = '';
            keywords.forEach((kw) => {
                const tag = document.createElement('span');
                tag.className = 'keyword-tag';
                tag.textContent = kw;
                keywordsContainer.appendChild(tag);
            });
        } else {
            keywordsContainer.textContent = '无关键词';
            keywordsContainer.classList.add('text-muted');
        }
        
        // 将Markdown转换为HTML显示
        if (data.summary.detailed_summary) {
            const ds = document.getElementById('detailedSummary');
            ds.style.whiteSpace = 'pre-wrap';
            ds.textContent = data.summary.detailed_summary;
        }
    }
    
    // 显示分析结果
    if (data.analysis && !data.analysis.error) {
        document.getElementById('contentType').textContent = data.analysis.content_type || '-';
        document.getElementById('sentiment').textContent = data.analysis.sentiment || '-';
        document.getElementById('languageStyle').textContent = data.analysis.language_style || '-';
        document.getElementById('difficulty').textContent = data.analysis.estimated_difficulty || '-';
        document.getElementById('targetAudience').textContent = data.analysis.target_audience || '-';
        
        if (data.analysis.main_topics && Array.isArray(data.analysis.main_topics)) {
            document.getElementById('mainTopics').textContent = data.analysis.main_topics.join(', ');
        } else {
            document.getElementById('mainTopics').textContent = '-';
        }
    }
}

// 显示结果区域
function showResultArea() {
    const statusArea = document.getElementById('statusArea');
    const resultArea = document.getElementById('resultArea');
    
    statusArea.style.display = 'none';
    resultArea.style.display = 'block';
    resultArea.classList.add('slide-in');
    
    // 滚动到结果区域
    setTimeout(() => {
        resultArea.scrollIntoView({ behavior: 'smooth' });
    }, 100);
}

// 下载文件
async function downloadFile(fileType) {
    if (!currentTaskId) {
        showAlert('没有可下载的文件', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`/api/download/${currentTaskId}/${fileType}`);
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            
            // 更好地处理中文文件名
            let filename = `${fileType}.txt`; // 默认文件名
            
            // 从 Content-Disposition 头获取文件名
            const contentDisposition = response.headers.get('Content-Disposition');
            if (contentDisposition) {
                // 处理 filename*=UTF-8'' 格式
                const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/);
                if (utf8Match) {
                    try {
                        filename = decodeURIComponent(utf8Match[1]);
                    } catch (e) {
                        console.warn('解码UTF-8文件名失败:', e);
                    }
                } else {
                    // 处理普通 filename= 格式
                    const normalMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                    if (normalMatch) {
                        filename = normalMatch[1];
                    }
                }
            }
            
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showAlert(`文件下载成功: ${filename}`, 'success');
        } else {
            const result = await response.json();
            showAlert(result.message, 'danger');
        }
    } catch (error) {
        showAlert('下载失败: ' + error.message, 'danger');
    }
}

// Obsidian配置验证函数
function validateObsidianConfig(obsidianConfig) {
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
    
    // 检查文件名格式
    const validFormats = ['title', 'date', 'datetime', 'title_date', 'date_title'];
    if (obsidianConfig.filename_format && !validFormats.includes(obsidianConfig.filename_format)) {
        errors.push('无效的文件名格式');
    }
    
    return errors;
}

// 导入Obsidian
async function importToObsidian() {
    if (!currentTaskId) {
        showAlert('没有可导入的内容', 'warning');
        return;
    }
    
    // 获取Obsidian配置
    const config = getApiConfig();
    const obsidianConfig = config?.obsidian || {};
    
    // 使用配置验证函数
    const configErrors = validateObsidianConfig(obsidianConfig);
    if (configErrors.length > 0) {
        showAlert(
            'Obsidian配置问题：<br>' + configErrors.map(err => `• ${err}`).join('<br>') + 
            '<br><small>请在API设置页面中检查配置。</small>', 
            'warning'
        );
        return;
    }
    
    const vaultName = obsidianConfig.vault_name;
    const folderPath = obsidianConfig.default_folder || '';
    const autoOpen = obsidianConfig.auto_open !== false;
    
    try {
        // 获取任务结果以获取视频信息
        const resultResponse = await fetch(`/api/result/${currentTaskId}`);
        const resultData = await resultResponse.json();
        
        if (!resultData.success) {
            showAlert('获取任务信息失败', 'danger');
            return;
        }
        
        const videoInfo = resultData.data.video_info;
        const transcript = resultData.data.transcript;
        
        // 生成Obsidian格式的Markdown内容
        const obsidianContent = generateObsidianMarkdown(videoInfo, transcript, obsidianConfig);
        
        // 生成文件名
        const fileName = generateObsidianFileName(videoInfo.title, obsidianConfig);
        
        // 构建文件路径
        let fullPath = fileName;
        if (folderPath) {
            fullPath = `${folderPath}/${fileName}`;
        }
        
        if (autoOpen) {
            // 先进行环境检测（现在不会阻止执行）
            const envCheck = await checkObsidianEnvironment();
            console.log('🔍 环境检测结果:', envCheck.reason);
            
            // 构建Obsidian URI
            const uriResult = buildObsidianUri(fullPath, obsidianContent, vaultName);
            
            // 显示内容截取提示
            if (uriResult.wasTruncated) {
                showAlert(
                    `⚠️ 内容过长已截取<br><small>原内容${uriResult.originalLength}字符，已压缩至${uriResult.contentLength}字符</small>`, 
                    'info'
                );
            }
            
            // 尝试复制内容到剪贴板（用于支持&clipboard参数的URI）
            try {
                await navigator.clipboard.writeText(obsidianContent);
                console.log('✅ 内容已复制到剪贴板');
            } catch (clipboardError) {
                console.warn('⚠️ 剪贴板复制失败:', clipboardError);
                // 即使剪贴板失败也继续执行，因为还有content参数的备选方案
            }
            
            // 尝试使用优化的URI格式
            const success = await tryOpenObsidianWithUris(uriResult.uris, fileName, folderPath, obsidianContent);
            
            if (success) {
                const folderInfo = folderPath ? `到文件夹 "${folderPath}"` : '到根目录';
                const truncateInfo = uriResult.wasTruncated ? '（内容已截取）' : '';
                showAlert(`✅ 成功打开Obsidian创建笔记${folderInfo}${truncateInfo}`, 'success');
            } else {
                // URI方式失败，自动回退到下载方式
                downloadMarkdownFile(obsidianContent, fileName);
                showAlert(
                    '⚠️ 无法直接打开Obsidian，已下载Markdown文件<br><small>' +
                    '可能原因：<br>' +
                    '1. Obsidian未运行或该仓库未打开<br>' +
                    '2. Advanced URI插件未安装<br>' +
                    '3. 仓库名称配置错误<br>' +
                    '请手动将下载的文件拖拽到Obsidian中</small>', 
                    'warning'
                );
            }
        } else {
            // 直接下载文件模式
            downloadMarkdownFile(obsidianContent, fileName);
            showAlert(`✅ 已下载笔记文件: ${fileName}`, 'success');
        }
        
    } catch (error) {
        console.error('Obsidian导入失败:', error);
        
        // 智能回退处理
        try {
            // 重新获取数据用于回退下载
            const resultResponse = await fetch(`/api/result/${currentTaskId}`);
            const resultData = await resultResponse.json();
            
            if (resultData.success) {
                const videoInfo = resultData.data.video_info;
                const transcript = resultData.data.transcript;
                const obsidianContent = generateObsidianMarkdown(videoInfo, transcript, obsidianConfig);
                const fileName = generateObsidianFileName(videoInfo.title, obsidianConfig);
                
                downloadMarkdownFile(obsidianContent, fileName);
                
                // 根据错误类型提供不同的提示
                let errorMsg = '⚠️ Obsidian导入失败，已下载笔记文件<br><small>';
                if (error.message.includes('未安装')) {
                    errorMsg += '请先安装Obsidian应用程序';
                } else if (error.message.includes('配置')) {
                    errorMsg += '请检查Obsidian配置设置';
                } else if (error.message.includes('仓库')) {
                    errorMsg += '请检查仓库名称是否正确';
                } else {
                    errorMsg += `错误：${error.message}`;
                }
                errorMsg += '<br>建议：手动将下载的文件拖拽到Obsidian中</small>';
                
                showAlert(errorMsg, 'warning');
            } else {
                throw new Error('无法获取任务数据');
            }
        } catch (fallbackError) {
            showAlert(
                `❌ 导入和下载都失败了<br><small>原因：${error.message}<br>回退错误：${fallbackError.message}</small>`, 
                'danger'
            );
        }
    }
}

// 优化的Obsidian URI打开函数
async function tryOpenObsidianWithUris(uris, fileName, folderPath, content) {
    console.log('📋 正在尝试打开Obsidian，共有', uris.length, '种URI格式');
    
    // 显示提示信息给用户
    showAlert('🚀 正在尝试打开Obsidian...请稍候<br><small>已复制内容到剪贴板</small>', 'info');
    
    for (let i = 0; i < uris.length; i++) {
        const uri = uris[i];
        try {
            console.log(`尝试URI格式 ${i + 1}/${uris.length}:`, uri.substring(0, 80) + '...');
            
            const success = await openObsidianUri(uri);
            if (success) {
                console.log(`✅ URI格式 ${i + 1} 成功打开Obsidian`);
                
                // 给用户一个确认提示
                setTimeout(() => {
                    const confirmMsg = `✅ Obsidian URI已发送！\n\n如果Obsidian没有自动打开或创建笔记，可能的原因：\n1. Obsidian应用未运行\n2. 仓库名称不匹配\n3. 浏览器阻止了URI协议\n\n请检查Obsidian是否已打开并创建了笔记："${fileName}"`;
                    showAlert(confirmMsg, 'success');
                }, 2000);
                
                return true;
            }
            
            console.log(`❌ URI格式 ${i + 1} 失败，尝试下一个格式`);
            
            // 短暂等待后尝试下一个格式，给Obsidian足够时间响应
            await new Promise(resolve => setTimeout(resolve, 1000));
            
        } catch (uriError) {
            console.warn(`URI格式 ${i + 1} 异常:`, uriError.message);
            continue;
        }
    }
    
    console.log('❌ 所有URI格式均失败');
    
    // 显示详细的失败说明
    const troubleshootMsg = `⚠️ 无法自动打开Obsidian\n\n可能的解决方案：\n1. 确保Obsidian已安装并运行\n2. 检查仓库名称是否正确\n3. 在Obsidian中打开对应的仓库\n4. 尝试手动导入下载的文件\n\n已为您下载Markdown文件，请手动拖拽到Obsidian中`;
    showAlert(troubleshootMsg, 'warning');
    
    return false;
}

// 实用的Obsidian环境检测（跳过不可靠的协议检测）
async function checkObsidianEnvironment() {
    try {
        // 不再依赖不可靠的协议检测，直接返回假设安装状态
        // 因为用户已经在配置中指定了要使用Obsidian
        return {
            isInstalled: true,  // 假设已安装，后续通过实际URI调用来验证
            hasAdvancedUri: true,  // 假设插件已安装，后续验证
            reason: 'Obsidian环境检测已跳过，将直接尝试连接'
        };
        
    } catch (error) {
        return {
            isInstalled: true,  // 即使检测失败也允许尝试
            reason: `环境检测跳过，将尝试直接连接`
        };
    }
}

// URI协议测试辅助函数
async function testUriProtocol(testUri) {
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
        }, 3000);
        
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

// 改进的URI打开方法，专门用于Obsidian URI
async function openObsidianUri(uri) {
    return new Promise((resolve) => {
        console.log('🚀 正在尝试打开URI:', uri);
        
        // 方法1: 创建隐藏的iframe（推荐方法，避免页面跳转）
        try {
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.style.position = 'absolute';
            iframe.style.left = '-9999px';
            iframe.src = uri;
            
            // 添加到DOM
            document.body.appendChild(iframe);
            
            // 设置超时清理
            setTimeout(() => {
                try {
                    document.body.removeChild(iframe);
                } catch (e) {
                    // 忽略清理错误
                }
            }, 3000);
            
            // 给Obsidian响应时间
            setTimeout(() => {
                console.log('✅ URI已通过iframe发送');
                resolve(true);
            }, 1500);
            
        } catch (iframeError) {
            console.log('❌ iframe方法失败，尝试链接点击方法');
            
            // 方法2: 创建链接并模拟点击
            try {
                const link = document.createElement('a');
                link.href = uri;
                link.target = '_blank'; // 避免当前页面跳转
                link.style.display = 'none';
                
                document.body.appendChild(link);
                
                // 创建点击事件
                const clickEvent = new MouseEvent('click', {
                    bubbles: true,
                    cancelable: true,
                    view: window
                });
                
                link.dispatchEvent(clickEvent);
                
                // 清理
                setTimeout(() => {
                    try {
                        document.body.removeChild(link);
                    } catch (e) {
                        // 忽略清理错误
                    }
                }, 1000);
                
                setTimeout(() => {
                    console.log('✅ URI已通过链接点击发送');
                    resolve(true);
                }, 1500);
                
            } catch (linkError) {
                console.log('❌ 链接点击失败，尝试最后的window.open方法');
                
                // 方法3: 使用window.open（最后的备选方案）
                try {
                    const newWindow = window.open(uri, '_blank');
                    
                    // 立即关闭窗口（如果可能）
                    setTimeout(() => {
                        if (newWindow && !newWindow.closed) {
                            newWindow.close();
                        }
                    }, 500);
                    
                    setTimeout(() => {
                        console.log('✅ URI已通过window.open发送');
                        resolve(true);
                    }, 1500);
                    
                } catch (windowError) {
                    console.log('❌ 所有方法都失败:', windowError.message);
                    resolve(false);
                }
            }
        }
    });
}

// 备选方法：使用iframe处理URI
function tryIframeMethod(uri, resolve) {
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = uri;
    
    let resolved = false;
    const timeout = setTimeout(() => {
        if (!resolved) {
            resolved = true;
            try {
                document.body.removeChild(iframe);
            } catch (e) {}
            console.log('⏱️ iframe方法超时');
            resolve(false);
        }
    }, 3000);
    
    iframe.onload = () => {
        if (!resolved) {
            resolved = true;
            clearTimeout(timeout);
            try {
                document.body.removeChild(iframe);
            } catch (e) {}
            console.log('✅ iframe方法成功');
            resolve(true);
        }
    };
    
    iframe.onerror = () => {
        if (!resolved) {
            resolved = true;
            clearTimeout(timeout);
            try {
                document.body.removeChild(iframe);
            } catch (e) {}
            console.log('❌ iframe方法失败');
            resolve(false);
        }
    };
    
    document.body.appendChild(iframe);
}
// 下载Markdown文件
function downloadMarkdownFile(content, fileName) {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

// 检查Obsidian是否安装 - 改进版
async function checkObsidianInstalled() {
    return new Promise((resolve) => {
        // 方法1: 尝试通过navigator检测protocol handler
        const testUri = 'obsidian://';
        
        // 检查是否可能安装了Obsidian
        // 注意：浏览器安全限制，无法100%可靠检测，但可以尝试
        
        // 创建一个隐藏的链接用于测试
        const testLink = document.createElement('a');
        testLink.href = testUri;
        testLink.style.display = 'none';
        document.body.appendChild(testLink);
        
        // 尝试点击并监听
        let detected = false;
        const timeout = setTimeout(() => {
            document.body.removeChild(testLink);
            resolve(detected);
        }, 500);
        
        // 监听blur事件作为可能的响应指标
        const handleBlur = () => {
            detected = true;
            clearTimeout(timeout);
            setTimeout(() => {
                document.body.removeChild(testLink);
                resolve(true);
            }, 100);
        };
        
        window.addEventListener('blur', handleBlur, { once: true });
        
        // 尝试点击
        try {
            testLink.click();
        } catch (e) {
            // 点击失败，可能未安装
            clearTimeout(timeout);
            window.removeEventListener('blur', handleBlur);
            document.body.removeChild(testLink);
            resolve(false);
        }
    });
}

// 构建Obsidian URI
function buildObsidianUri(filePath, content, vaultName) {
    if (!vaultName) {
        throw new Error('仓库名称不能为空');
    }
    
    // 优化内容处理：大幅减少长度限制，避免URI过长
    const maxContentLength = 4000; // 从8000减少到4000，提高兼容性
    let processedContent = content;
    
    // 统一换行符和清理特殊字符
    processedContent = processedContent
        .replace(/\r\n/g, '\n')  // 统一换行符
        .replace(/\r/g, '\n')   // 处理旧Mac格式
        .trim();                // 去除首尾空白
    
    if (processedContent.length > maxContentLength) {
        // 智能截取：优先保留标题和摘要部分
        const lines = processedContent.split('\n');
        const truncatedLines = [];
        let currentLength = 0;
        const reserveLength = 300; // 为提示信息预留空间
        
        for (const line of lines) {
            const lineLength = line.length + 1; // +1 for newline
            if (currentLength + lineLength <= maxContentLength - reserveLength) {
                truncatedLines.push(line);
                currentLength += lineLength;
            } else {
                break;
            }
        }
        
        processedContent = truncatedLines.join('\n') + 
            '\n\n---\n\n⚠️ **内容已截取**\n\n由于内容较长，仅显示前' + truncatedLines.length + '行。\n\n完整内容请：\n1. 手动下载完整文件\n2. 或在Obsidian中手动添加剩余内容';
    }
    
    // 改进编码方式，处理特殊字符
    const encodedVaultName = encodeURIComponent(vaultName);
    const encodedFilePath = encodeURIComponent(filePath);
    const encodedContent = encodeURIComponent(processedContent)
        .replace(/'/g, '%27')   // 单引号
        .replace(/"/g, '%22')   // 双引号
        .replace(/\(/g, '%28')  // 左括号
        .replace(/\)/g, '%29'); // 右括号
    
    // 根据官方插件抓取的请求格式构建URI
    
    // 提取文件名（去掉路径和.md扩展名）
    const fileName = filePath.split('/').pop().replace('.md', '');
    const folderPath = filePath.includes('/') ? filePath.substring(0, filePath.lastIndexOf('/')) : '';
    
    // 格式1: 官方插件使用的格式 - obsidian://new?file=完整路径&clipboard
    // 这是根据用户抓取的请求分析得出的正确格式
    const officialUri = `obsidian://new?file=${encodedFilePath}&clipboard`;
    
    // 格式2: 官方插件使用的格式（带仓库名）
    const officialWithVaultUri = `obsidian://new?vault=${encodedVaultName}&file=${encodedFilePath}&clipboard`;
    
    // 格式3: 传统的content参数格式（作为备选）
    const contentBasedUri = `obsidian://new?vault=${encodedVaultName}&file=${encodedFilePath}&content=${encodedContent}`;
    
    // 格式4: name + content 格式（作为备选）
    let nameContentUri = `obsidian://new?vault=${encodedVaultName}&name=${encodeURIComponent(fileName)}&content=${encodedContent}`;
    if (folderPath) {
        nameContentUri = `obsidian://new?vault=${encodedVaultName}&name=${encodeURIComponent(fileName)}&path=${encodeURIComponent(folderPath)}&content=${encodedContent}`;
    }
    
    // 格式5: Advanced URI格式 (需要插件支持)
    const advancedUri = `obsidian://advanced-uri?vault=${encodedVaultName}&file=${encodedFilePath}&data=${encodedContent}&mode=new`;
    
    // 调试信息：显示生成的URI（仅显示前部分，避免泄露内容）
    console.log('🔗 生成的Obsidian URI格式:');
    console.log('1. 官方插件格式:', officialUri);
    console.log('2. 官方插件+仓库:', officialWithVaultUri);
    console.log('3. 内容传递格式:', contentBasedUri.substring(0, 150) + '...');
    console.log('4. 名称+内容格式:', nameContentUri.substring(0, 150) + '...');
    console.log('5. Advanced URI:', advancedUri.substring(0, 150) + '...');
    console.log('📄 文件路径:', filePath);
    console.log('📝 内容长度:', processedContent.length, '字符');
    
    // 返回修正后的URI列表，按成功率排序（优先使用官方插件格式）
    return {
        uris: [officialUri, officialWithVaultUri, contentBasedUri, nameContentUri, advancedUri],
        contentLength: processedContent.length,
        originalLength: content.length,
        wasTruncated: content.length > maxContentLength
    };
}

// 生成Obsidian格式的Markdown
function generateObsidianMarkdown(videoInfo, transcript, obsidianConfig) {
    const title = videoInfo.title || '未命名视频';
    const uploader = videoInfo.uploader || '未知UP主';
    const url = videoInfo.url || '';
    const duration = videoInfo.duration ? formatDuration(videoInfo.duration) : '未知时长';
    
    const date = new Date().toISOString().split('T')[0];
    const tags = generateTags(title, transcript);
    const tagsString = tags.join(', ');
    
    // 支持自定义YAML前置信息
    const yamlFrontMatter = `---
title: "${title}"
author: "${uploader}"
source: "${url}"
duration: "${duration}"
created: "${date}"
tags: [${tagsString}]
platform: "VideoWhisper"
status: "processed"
---`;
    
    return `${yamlFrontMatter}

# ${title}

## 元信息
- **UP主:** ${uploader}
- **视频链接:** [点击观看](${url})
- **时长:** ${duration}
- **创建时间:** ${date}
- **处理时间:** ${new Date().toLocaleString('zh-CN')}

## 标签
${tags.map(tag => `- ${tag}`).join('\n')}

---

## 逐字稿

${transcript}

---

*此笔记由 [VideoWhisper](https://github.com/zhuguadundan/videowhisper) 自动生成*`;
}

// 生成Obsidian文件名
function generateObsidianFileName(title, obsidianConfig) {
    const format = obsidianConfig?.filename_format || 'title';
    const prefix = obsidianConfig?.filename_prefix || '';
    
    let fileName = '';
    const cleanTitle = (title || '视频笔记').replace(/[^\u4e00-\u9fa5\w\s\-\|\(\)\[\]【】（）]/g, '').slice(0, 30) || '视频笔记';
    
    switch (format) {
        case 'date_title':
            const date = new Date().toISOString().split('T')[0];
            fileName = `${date}_${cleanTitle}`;
            break;
        case 'prefix_title':
            if (prefix) {
                fileName = `${prefix}_${cleanTitle}`;
            } else {
                fileName = cleanTitle;
            }
            break;
        case 'title':
        default:
            fileName = cleanTitle;
            break;
    }
    
    return `${fileName}.md`;
}

// 生成标签
function generateTags(title, transcript) {
    const text = (title + ' ' + transcript).toLowerCase();
    const tags = new Set();
    
    // 基础标签
    tags.add('video');
    tags.add('transcript');
    tags.add('autogenerated');
    
    // 根据内容推断标签
    if (text.includes('教程') || text.includes('教学')) tags.add('教程');
    if (text.includes('技术') || text.includes('编程')) tags.add('技术');
    if (text.includes('科学') || text.includes('研究')) tags.add('科学');
    if (text.includes('历史')) tags.add('历史');
    if (text.includes('新闻') || text.includes('时事')) tags.add('新闻');
    if (text.includes('娱乐') || text.includes('游戏')) tags.add('娱乐');
    if (text.includes('音乐') || text.includes('歌曲')) tags.add('音乐');
    if (text.includes('电影') || text.includes('影视')) tags.add('影视');
    
    return Array.from(tags).slice(0, 10); // 最多10个标签
}

// 格式化时长
function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}

// 加载历史任务
async function loadHistoryTasks() {
    try {
        const response = await fetch('/api/tasks');
        const result = await response.json();
        
        if (result.success) {
            displayHistoryTasks(result.data);
        }
    } catch (error) {
        console.error('加载历史任务失败:', error);
    }
}

// 显示历史任务
function displayHistoryTasks(tasks) {
    const tbody = document.getElementById('tasksTableBody');

    // 清空
    tbody.textContent = '';

    if (!tasks || tasks.length === 0) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 4;
        td.className = 'text-center text-muted';
        td.textContent = '暂无历史任务';
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    tasks.forEach(task => {
        const tr = document.createElement('tr');

        // 标题
        const tdTitle = document.createElement('td');
        const titleDiv = document.createElement('div');
        titleDiv.className = 'text-truncate';
        titleDiv.style.maxWidth = '300px';
        const title = task.title || '未知标题';
        titleDiv.title = title;
        titleDiv.textContent = title;
        tdTitle.appendChild(titleDiv);

        // 状态
        const tdStatus = document.createElement('td');
        const badge = document.createElement('span');
        badge.className = `badge bg-secondary status-${task.status}`;
        const icon = document.createElement('span');
        icon.className = 'status-icon';
        const text = document.createTextNode(getStatusText(task.status));
        badge.appendChild(icon);
        badge.appendChild(document.createTextNode(' '));
        badge.appendChild(text);
        tdStatus.appendChild(badge);
        if (task.status === 'processing') {
            const small = document.createElement('small');
            small.className = 'text-muted ms-1';
            small.textContent = `(${task.progress}%)`;
            tdStatus.appendChild(small);
        }

        // 时间
        const tdTime = document.createElement('td');
        const smallTime = document.createElement('small');
        smallTime.textContent = task.created_at || '';
        tdTime.appendChild(smallTime);

        // 操作
        const tdOps = document.createElement('td');
        const btn = document.createElement('button');
        if (task.status === 'completed') {
            btn.className = 'btn btn-sm btn-outline-primary';
            btn.innerHTML = '<i class="fas fa-eye me-1"></i>查看';
            btn.addEventListener('click', () => loadTaskResult(task.id));
        } else {
            btn.className = 'btn btn-sm btn-outline-secondary';
            btn.disabled = true;
            btn.textContent = task.status === 'processing' ? '处理中...' : '不可用';
        }
        tdOps.appendChild(btn);

        // 删除按钮：除 processing 外均允许，避免残留记录无法清理
        const delBtn = document.createElement('button');
        if (task.status !== 'processing') {
            delBtn.className = 'btn btn-sm btn-outline-danger ms-2';
            delBtn.innerHTML = '<i class="fas fa-trash me-1"></i>删除';
            delBtn.addEventListener('click', () => deleteTaskRecord(task.id, task.title || ''));
        } else {
            delBtn.className = 'btn btn-sm btn-outline-secondary ms-2';
            delBtn.disabled = true;
            delBtn.textContent = '不可用';
        }
        tdOps.appendChild(delBtn);

        tr.appendChild(tdTitle);
        tr.appendChild(tdStatus);
        tr.appendChild(tdTime);
        tr.appendChild(tdOps);
        tbody.appendChild(tr);
    });
}

// 获取状态文本
function getStatusText(status) {
    const statusMap = {
        pending: '等待中',
        processing: '处理中',
        completed: '已完成',
        failed: '失败'
    };
    return statusMap[status] || status;
}

// 加载指定任务的结果
async function loadTaskResult(taskId) {
    if (!taskId) {
        console.error('loadTaskResult: taskId为空');
        showToast('error', '加载失败', '任务ID无效');
        return;
    }
    
    console.log(`loadTaskResult: 设置currentTaskId为 ${taskId}`);
    currentTaskId = taskId;
    
    // 验证currentTaskId是否正确设置
    if (currentTaskId !== taskId) {
        console.error('loadTaskResult: currentTaskId设置失败');
        showToast('error', '加载失败', '任务ID设置失败');
        return;
    }
    
    await loadResults();
    
    // 滚动到结果区域
    document.getElementById('resultArea').scrollIntoView({ behavior: 'smooth' });
}

// 显示提示信息
function showAlert(message, type = 'info') {
    // 移除现有的提示
    const existingAlert = document.querySelector('.alert');
    if (existingAlert) {
        existingAlert.remove();
    }

    // 创建安全的提示结构，避免注入
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show bounce-in`;

    const textSpan = document.createElement('span');
    textSpan.textContent = String(message || '');
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn-close';
    closeBtn.setAttribute('data-bs-dismiss', 'alert');

    alert.appendChild(textSpan);
    alert.appendChild(closeBtn);

    const mainEl = document.querySelector('main') || document.body;
    mainEl.insertBefore(alert, mainEl.firstChild);

    // 自动隐藏
    setTimeout(() => {
        if (alert.parentNode) {
            alert.classList.add('fade-out');
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.remove();
                }
            }, 300);
        }
    }, 5000);
}

// 格式化时长
function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}

// 停止所有任务
async function stopAllTasks() {
    const stopBtn = document.getElementById('stopAllTasksBtn');
    
    // 确认对话框
    if (!confirm('确定要停止所有正在处理的任务吗？\n\n这将中断所有正在进行的视频处理任务。')) {
        return;
    }
    
    // 禁用按钮并显示加载状态
    stopBtn.disabled = true;
    const originalText = stopBtn.innerHTML;
    stopBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>停止中...';
    
    try {
        const response = await fetch('/api/stop-all-tasks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            const stoppedCount = result.data.stopped_count || 0;
            if (stoppedCount > 0) {
                showToast('success', '任务已停止', `成功停止了 ${stoppedCount} 个正在处理的任务`);
                
                // 刷新任务列表以显示更新后的状态
                setTimeout(() => {
                    loadHistoryTasks();
                }, 1000);
            } else {
                showToast('info', '无任务运行', '当前没有正在处理的任务');
            }
        } else {
            showToast('error', '停止失败', result.message || '停止任务时发生错误');
        }
        
    } catch (error) {
        console.error('停止所有任务失败:', error);
        showToast('error', '停止失败', '网络错误或服务器异常');
    } finally {
        // 恢复按钮状态
        stopBtn.disabled = false;
        stopBtn.innerHTML = originalText;
    }
}

// 删除历史任务记录（含结果文件）
async function deleteTaskRecord(taskId, title) {
    if (!taskId) return;

    const name = title && String(title).trim() ? title : taskId;
    const confirmMsg = `确定要删除该处理历史记录吗？\n\n${name}\n\n这将删除与该任务相关的所有结果文件。`;
    if (!confirm(confirmMsg)) return;

    const headers = { 'Content-Type': 'application/json' };
    try {
        const cfg = getApiConfig();
        const adminToken = cfg?.security?.admin_token || localStorage.getItem('videowhisper_admin_token');
        if (adminToken) headers['X-Admin-Token'] = adminToken;
    } catch (e) { /* 忽略 */ }

    try {
        const res = await fetch(`/api/tasks/delete/${encodeURIComponent(taskId)}`, {
            method: 'POST',
            headers
        });
        const result = await res.json();
        if (result.success) {
            showToast('success', '已删除', `任务已删除：${name}`);
            if (currentTaskId === taskId) currentTaskId = null;
            setTimeout(() => loadHistoryTasks(), 300);
        } else {
            showToast('error', '删除失败', result.message || '服务器未返回成功');
        }
    } catch (err) {
        console.error('删除任务失败:', err);
        showToast('error', '删除失败', '网络错误或服务器异常');
    }
}
