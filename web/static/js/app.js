// 全局变量
let currentTaskId = null;
let progressInterval = null;

// 辅助函数：获取API配置
function getApiConfig() {
    try {
        const storageKey = 'videowhisper_api_config';
        const encrypted = localStorage.getItem(storageKey);
        if (!encrypted) return null;
        
        return JSON.parse(atob(encrypted));
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

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    loadAvailableProviders();
    loadHistoryTasks();
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
        } else {
            // 没有可用的提供商，显示警告
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '请先配置API密钥';
            option.disabled = true;
            option.selected = true;
            select.appendChild(option);
            
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
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-cog me-2"></i>请先配置API';
    }
}

// 隐藏配置警告
function hideConfigWarning() {
    const warning = document.getElementById('configWarning');
    if (warning) {
        warning.style.display = 'none';
    }
    
    // 启用提交按钮
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fas fa-sparkles me-2"></i>开始智能处理（仅音频）';
    }
}

// 初始化事件监听器
function initializeEventListeners() {
    // 表单提交
    document.getElementById('processForm').addEventListener('submit', handleFormSubmit);
    
    // 下载按钮
    document.getElementById('downloadTranscript').addEventListener('click', () => downloadFile('transcript'));
    document.getElementById('downloadSummary').addEventListener('click', () => downloadFile('summary'));
    
    // 刷新任务列表
    document.getElementById('refreshTasks').addEventListener('click', loadHistoryTasks);
    
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

// URL验证
function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
}

// 处理表单提交
async function handleFormSubmit(e) {
    e.preventDefault();
    
    const videoUrl = document.getElementById('videoUrl').value.trim();
    const llmProvider = document.getElementById('llmProvider').value;
    const submitBtn = document.getElementById('submitBtn');
    
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
        submitBtn.innerHTML = '<i class="fas fa-sparkles me-2"></i>开始智能处理';
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
function startProgressMonitoring() {
    if (progressInterval) {
        clearInterval(progressInterval);
    }
    
    progressInterval = setInterval(async () => {
        if (!currentTaskId) return;
        
        try {
            const response = await fetch(`/api/progress/${currentTaskId}`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    showAlert('任务不存在，可能已被删除', 'warning');
                    clearInterval(progressInterval);
                    return;
                } else if (response.status >= 500) {
                    showAlert('服务器错误，无法获取进度信息', 'danger');
                    clearInterval(progressInterval);
                    return;
                }
            }
            
            const result = await response.json();
            
            if (result.success) {
                updateProgress(result.data);
                
                if (result.data.status === 'completed') {
                    clearInterval(progressInterval);
                    await loadResults();
                } else if (result.data.status === 'failed') {
                    clearInterval(progressInterval);
                    let errorMsg = result.data.error_message || '处理失败';
                    showAlert('处理失败: ' + errorMsg, 'danger');
                }
            } else {
                // API返回失败结果
                clearInterval(progressInterval);
                showAlert(result.message || result.error || '无法获取进度信息', 'danger');
            }
        } catch (error) {
            console.error('获取进度失败:', error);
            // 网络错误不立即停止轮询，给用户一些容错时间
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                console.warn('网络连接问题，继续尝试获取进度...');
            } else {
                clearInterval(progressInterval);
                showAlert('无法连接到服务器，进度监控已停止', 'warning');
            }
        }
    }, 2000);
}

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
                progressStage.innerHTML = `${stageIcon}<strong>当前阶段:</strong> ${data.progress_stage}`;
            }
            
            // 显示详细进度信息和AI响应速度
            let detailHtml = '';
            if (data.progress_detail) {
                detailHtml = `<i class="fas fa-info-circle me-1"></i>${data.progress_detail}`;
            }
            
            // 显示AI响应时间信息
            if (data.ai_response_times && Object.keys(data.ai_response_times).length > 0) {
                detailHtml += '<div class="ai-timing-info mt-2">';
                if (data.ai_response_times.transcript) {
                    detailHtml += `<small class="text-muted"><i class="fas fa-stopwatch me-1"></i>逐字稿生成: ${data.ai_response_times.transcript.toFixed(1)}s</small>`;
                }
                if (data.ai_response_times.summary) {
                    detailHtml += ` <small class="text-muted"><i class="fas fa-stopwatch me-1"></i>摘要生成: ${data.ai_response_times.summary.toFixed(1)}s</small>`;
                }
                if (data.ai_response_times.analysis) {
                    detailHtml += ` <small class="text-muted"><i class="fas fa-stopwatch me-1"></i>内容分析: ${data.ai_response_times.analysis.toFixed(1)}s</small>`;
                }
                detailHtml += '</div>';
            }
            
            progressDetail.innerHTML = detailHtml;
            
            // 显示逐字稿预览（如果已经生成）
            if (data.transcript_ready && data.transcript_preview) {
                showTranscriptPreview(data.transcript_preview, data.full_transcript);
            }
            
            // 显示音频段处理进度（仅在语音转文字阶段）
            if (data.total_segments > 1 && data.progress_stage === '语音转文字') {
                segmentProgress.style.display = 'block';
                segmentProgress.innerHTML = `<i class="fas fa-tasks me-1"></i><strong>片段进度:</strong> ${data.processed_segments}/${data.total_segments} 个音频片段`;
            } else {
                segmentProgress.style.display = 'none';
            }
            
            // 显示预估剩余时间
            if (data.estimated_time && data.estimated_time > 0) {
                estimatedTime.style.display = 'block';
                const minutes = Math.ceil(data.estimated_time / 60);
                estimatedTime.innerHTML = `<i class="fas fa-clock me-1"></i><strong>预计还需:</strong> ${minutes} 分钟`;
            } else {
                estimatedTime.style.display = 'none';
            }
            break;
        case 'completed':
            statusMessage = '处理完成!';
            progressDetails.style.display = 'block';
            progressStage.innerHTML = `<i class="fas fa-check-circle text-success me-1"></i><strong>已完成:</strong> 所有文件已生成`;
            progressDetail.innerHTML = `<i class="fas fa-download me-1"></i>您现在可以下载结果文件`;
            segmentProgress.style.display = 'none';
            estimatedTime.style.display = 'none';
            break;
        case 'failed':
            statusMessage = '处理失败';
            progressDetails.style.display = 'block';
            progressStage.innerHTML = `<i class="fas fa-exclamation-triangle text-danger me-1"></i><strong>错误:</strong> 处理失败`;
            if (data.error_message) {
                progressDetail.innerHTML = `<i class="fas fa-info-circle me-1"></i>${data.error_message}`;
            }
            segmentProgress.style.display = 'none';
            estimatedTime.style.display = 'none';
            break;
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
        videoInfo.style.display = 'block';
    }
}

// 获取阶段图标
function getStageIcon(stage) {
    const icons = {
        '获取视频信息': '<i class="fas fa-info-circle text-primary me-1"></i>',
        '下载音频': '<i class="fas fa-download text-info me-1"></i>',
        '处理音频': '<i class="fas fa-waveform-path text-warning me-1"></i>',
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
    
    previewDiv.innerHTML = `
        <h6><i class="fas fa-file-text me-2 text-primary"></i>逐字稿预览 <small class="text-muted">(可先查看内容)</small></h6>
        <div class="transcript-content" style="max-height: 200px; overflow-y: auto; background: white; padding: 10px; border: 1px solid #dee2e6; border-radius: 4px; font-size: 0.9em; line-height: 1.5;">
            ${preview.replace(/\n/g, '<br>')}
        </div>
        <div class="mt-2">
            <button class="btn btn-sm btn-outline-primary" onclick="showFullTranscript()">
                <i class="fas fa-expand me-1"></i>查看完整逐字稿
            </button>
        </div>
    `;
    
    // 存储完整逐字稿
    previewDiv.dataset.fullTranscript = fullTranscript;
    previewDiv.style.display = 'block';
}

// 显示完整逐字稿
function showFullTranscript() {
    const previewDiv = document.getElementById('transcriptPreview');
    const fullTranscript = previewDiv.dataset.fullTranscript;
    
    if (fullTranscript) {
        // 创建模态框显示完整逐字稿
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'transcriptModal';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title"><i class="fas fa-file-text me-2"></i>完整逐字稿</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="transcript-content" style="max-height: 60vh; overflow-y: auto; background: #f8f9fa; padding: 15px; border-radius: 4px; font-size: 0.95em; line-height: 1.6; white-space: pre-wrap;">
                            ${fullTranscript.replace(/\n/g, '<br>')}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                        <button type="button" class="btn btn-primary" onclick="copyToClipboard('${fullTranscript.replace(/'/g, '\\\'')}')">
                            <i class="fas fa-copy me-1"></i>复制文本
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        // 模态框关闭后移除元素
        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }
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
    try {
        const response = await fetch(`/api/result/${currentTaskId}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                showAlert('任务结果不存在，可能任务未完成或已被删除', 'warning');
                return;
            } else if (response.status >= 500) {
                showAlert('服务器错误，无法加载结果', 'danger');
                return;
            }
        }
        
        const result = await response.json();
        
        if (result.success) {
            displayResults(result.data);
            showResultArea();
            loadHistoryTasks(); // 刷新历史任务
        } else {
            showAlert(result.message || result.error || '加载结果失败', 'danger');
        }
    } catch (error) {
        console.error('加载结果失败:', error);
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showAlert('网络连接失败，无法加载结果', 'danger');
        } else if (error.name === 'SyntaxError') {
            showAlert('服务器响应格式错误', 'danger');
        } else {
            showAlert('加载结果失败: ' + error.message, 'danger');
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
    
    // 显示总结
    if (data.summary) {
        document.getElementById('briefSummary').textContent = data.summary.brief_summary || '无';
        
        // 处理关键词显示
        const keywordsContainer = document.getElementById('keywords');
        if (data.summary.keywords) {
            const keywords = Array.isArray(data.summary.keywords) ? 
                data.summary.keywords : data.summary.keywords.split(',').map(k => k.trim());
            
            keywordsContainer.innerHTML = keywords.map(keyword => 
                `<span class="keyword-tag">${keyword}</span>`
            ).join('');
        } else {
            keywordsContainer.innerHTML = '<span class="text-muted">无关键词</span>';
        }
        
        // 将Markdown转换为HTML显示
        if (data.summary.detailed_summary) {
            document.getElementById('detailedSummary').innerHTML = 
                data.summary.detailed_summary.replace(/\n/g, '<br>');
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
    
    if (!tasks || tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">暂无历史任务</td></tr>';
        return;
    }
    
    tbody.innerHTML = tasks.map(task => {
        const statusClass = `status-${task.status}`;
        const statusText = getStatusText(task.status);
        const title = task.title || '未知标题';
        
        return `
            <tr>
                <td>
                    <div class="text-truncate" style="max-width: 300px;" title="${title}">
                        ${title}
                    </div>
                </td>
                <td>
                    <span class="badge bg-secondary ${statusClass}">
                        <span class="status-icon"></span>
                        ${statusText}
                    </span>
                    ${task.status === 'processing' ? `<small class="text-muted ms-1">(${task.progress}%)</small>` : ''}
                </td>
                <td><small>${task.created_at}</small></td>
                <td>
                    ${task.status === 'completed' ? 
                        `<button class="btn btn-sm btn-outline-primary" onclick="loadTaskResult('${task.id}')">
                            <i class="fas fa-eye me-1"></i>查看
                        </button>` : 
                        `<button class="btn btn-sm btn-outline-secondary" disabled>
                            ${task.status === 'processing' ? '处理中...' : '不可用'}
                        </button>`
                    }
                </td>
            </tr>
        `;
    }).join('');
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
    currentTaskId = taskId;
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
    
    // 创建新的提示
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show bounce-in`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // 插入到页面顶部
    document.querySelector('main').insertBefore(alert, document.querySelector('main').firstChild);
    
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