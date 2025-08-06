// 全局变量
let currentTaskId = null;
let progressInterval = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    loadHistoryTasks();
});

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
    
    // 禁用提交按钮
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>处理中...';
    submitBtn.classList.add('loading-shimmer');
    
    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                video_url: videoUrl,
                llm_provider: llmProvider
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentTaskId = result.task_id;
            showStatusArea();
            startProgressMonitoring();
            showAlert(result.message, 'success');
        } else {
            showAlert(result.message, 'danger');
        }
        
    } catch (error) {
        showAlert('请求失败: ' + error.message, 'danger');
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
            const result = await response.json();
            
            if (result.success) {
                updateProgress(result.data);
                
                if (result.data.status === 'completed') {
                    clearInterval(progressInterval);
                    await loadResults();
                } else if (result.data.status === 'failed') {
                    clearInterval(progressInterval);
                    showAlert('处理失败: ' + result.data.error_message, 'danger');
                }
            }
        } catch (error) {
            console.error('获取进度失败:', error);
        }
    }, 2000);
}

// 更新进度显示
function updateProgress(data) {
    const statusText = document.getElementById('statusText');
    const progressText = document.getElementById('progressText');
    const progressBar = document.getElementById('progressBar');
    const videoInfo = document.getElementById('videoInfo');
    
    // 更新状态文本
    let statusMessage = '';
    switch (data.status) {
        case 'pending':
            statusMessage = '等待处理...';
            break;
        case 'processing':
            if (data.progress < 10) statusMessage = '获取视频信息...';
            else if (data.progress < 30) statusMessage = '下载音频...';
            else if (data.progress < 40) statusMessage = '处理音频...';
            else if (data.progress < 60) statusMessage = '语音转文字...';
            else if (data.progress < 80) statusMessage = '生成逐字稿...';
            else if (data.progress < 90) statusMessage = '生成总结报告...';
            else if (data.progress < 95) statusMessage = '内容分析...';
            else statusMessage = '保存结果...';
            break;
        case 'completed':
            statusMessage = '处理完成!';
            break;
        case 'failed':
            statusMessage = '处理失败';
            break;
    }
    
    statusText.textContent = statusMessage;
    progressText.textContent = `${data.progress}%`;
    progressBar.style.width = `${data.progress}%`;
    progressBar.setAttribute('aria-valuenow', data.progress);
    
    // 显示视频信息
    if (data.video_title) {
        document.getElementById('videoTitle').textContent = data.video_title;
        videoInfo.style.display = 'block';
    }
}

// 加载处理结果
async function loadResults() {
    try {
        const response = await fetch(`/api/result/${currentTaskId}`);
        const result = await response.json();
        
        if (result.success) {
            displayResults(result.data);
            showResultArea();
            loadHistoryTasks(); // 刷新历史任务
        } else {
            showAlert(result.message, 'danger');
        }
    } catch (error) {
        showAlert('加载结果失败: ' + error.message, 'danger');
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
            a.download = response.headers.get('Content-Disposition')?.split('filename=')[1]?.replace(/"/g, '') || `${fileType}.txt`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
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