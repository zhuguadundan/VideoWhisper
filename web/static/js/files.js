class FilesManager {
    constructor() {
        this.files = [];
        this.selectedFiles = new Set();
        this.filteredFiles = [];
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadFiles();
    }

    bindEvents() {
        // 刷新按钮
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.loadFiles();
        });

        // 搜索功能
        document.getElementById('search-input').addEventListener('input', (e) => {
            this.filterFiles(e.target.value);
        });

        // 全选功能
        document.getElementById('select-all-checkbox').addEventListener('change', (e) => {
            this.toggleSelectAll(e.target.checked);
        });

        document.getElementById('select-all-btn').addEventListener('click', () => {
            document.getElementById('select-all-checkbox').checked = true;
            this.toggleSelectAll(true);
        });

        document.getElementById('clear-selection-btn').addEventListener('click', () => {
            document.getElementById('select-all-checkbox').checked = false;
            this.toggleSelectAll(false);
        });

        // 下载和删除按钮
        document.getElementById('download-selected-btn').addEventListener('click', () => {
            this.downloadSelected();
        });

        document.getElementById('delete-selected-btn').addEventListener('click', () => {
            this.showDeleteModal();
        });

        // 删除确认
        document.getElementById('confirm-delete-btn').addEventListener('click', () => {
            this.deleteSelected();
        });

        // 任务删除确认
        document.getElementById('confirm-task-delete-btn').addEventListener('click', () => {
            this.deleteTask();
        });
    }

    async loadFiles() {
        try {
            this.showLoading(true);
            
            const response = await fetch('/api/files');
            const result = await response.json();
            
            if (result.success) {
                this.files = result.data;
                this.filteredFiles = [...this.files];
                this.renderFiles();
                this.updateStats();
                this.showLoading(false);
                
                if (this.files.length === 0) {
                    this.showEmptyState(true);
                }
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            console.error('加载文件失败:', error);
            this.showError('加载文件失败: ' + error.message);
            this.showLoading(false);
        }
    }

    filterFiles(searchTerm) {
        const term = searchTerm.toLowerCase();
        this.filteredFiles = this.files.filter(file => 
            file.file_name.toLowerCase().includes(term) ||
            file.task_title.toLowerCase().includes(term) ||
            file.description.toLowerCase().includes(term)
        );
        this.renderFiles();
        this.clearSelection();
    }

    renderFiles() {
        const tbody = document.getElementById('files-tbody');
        tbody.innerHTML = '';

        if (this.filteredFiles.length === 0) {
            if (this.files.length === 0) {
                this.showEmptyState(true);
                document.getElementById('files-list').classList.add('d-none');
            } else {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="text-center text-muted py-4">
                            <i class="bi bi-search"></i> 没有找到匹配的文件
                        </td>
                    </tr>
                `;
            }
            return;
        }

        this.showEmptyState(false);
        document.getElementById('files-list').classList.remove('d-none');

        this.filteredFiles.forEach(file => {
            const row = document.createElement('tr');
            row.className = 'file-item';
            row.dataset.fileId = file.id;
            
            const isSelected = this.selectedFiles.has(file.id);
            if (isSelected) {
                row.classList.add('selected');
            }

            row.innerHTML = `
                <td>
                    <input type="checkbox" class="form-check-input file-checkbox" 
                           data-file-id="${file.id}" ${isSelected ? 'checked' : ''}>
                </td>
                <td>
                    <div class="file-type-icon file-type-${file.file_type}">
                        ${this.getFileTypeIcon(file.file_type)}
                    </div>
                </td>
                <td>
                    <div class="d-flex flex-column">
                        <span class="fw-medium">${this.escapeHtml(file.file_name)}</span>
                        <small class="text-muted">${file.description}</small>
                    </div>
                </td>
                <td>
                    <span class="badge bg-secondary">${this.escapeHtml(file.task_title)}</span>
                </td>
                <td>${file.size_human}</td>
                <td>
                    <small>${file.modified_time}</small>
                </td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary download-btn" 
                                data-file-id="${file.id}" title="下载">
                            <i class="bi bi-download"></i>
                        </button>
                        <button class="btn btn-outline-secondary info-btn" 
                                data-file-id="${file.id}" title="详情">
                            <i class="bi bi-info-circle"></i>
                        </button>
                        ${file.task_id !== 'temp' ? 
                            `<button class="btn btn-outline-danger delete-task-btn" 
                                     data-task-id="${file.task_id}" 
                                     data-task-title="${this.escapeHtml(file.task_title)}" 
                                     title="删除整个任务">
                                <i class="bi bi-folder-x"></i>
                             </button>` : ''
                        }
                    </div>
                </td>
            `;

            tbody.appendChild(row);
        });

        // 绑定事件
        this.bindFileEvents();
    }

    bindFileEvents() {
        // 文件选择框
        document.querySelectorAll('.file-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const fileId = e.target.dataset.fileId;
                const row = e.target.closest('tr');
                
                if (e.target.checked) {
                    this.selectedFiles.add(fileId);
                    row.classList.add('selected');
                } else {
                    this.selectedFiles.delete(fileId);
                    row.classList.remove('selected');
                }
                
                this.updateSelectionUI();
            });
        });

        // 下载按钮
        document.querySelectorAll('.download-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const fileId = e.target.closest('button').dataset.fileId;
                this.downloadFile(fileId);
            });
        });

        // 信息按钮
        document.querySelectorAll('.info-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const fileId = e.target.closest('button').dataset.fileId;
                this.showFileInfo(fileId);
            });
        });

        // 删除任务按钮
        document.querySelectorAll('.delete-task-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const taskId = e.target.closest('button').dataset.taskId;
                const taskTitle = e.target.closest('button').dataset.taskTitle;
                this.showDeleteTaskModal(taskId, taskTitle);
            });
        });
    }

    toggleSelectAll(selected) {
        this.selectedFiles.clear();
        
        if (selected) {
            this.filteredFiles.forEach(file => {
                this.selectedFiles.add(file.id);
            });
        }

        document.querySelectorAll('.file-checkbox').forEach(checkbox => {
            checkbox.checked = selected;
        });

        document.querySelectorAll('.file-item').forEach(row => {
            if (selected) {
                row.classList.add('selected');
            } else {
                row.classList.remove('selected');
            }
        });

        this.updateSelectionUI();
    }

    updateSelectionUI() {
        const selectedCount = this.selectedFiles.size;
        const downloadBtn = document.getElementById('download-selected-btn');
        const deleteBtn = document.getElementById('delete-selected-btn');
        
        downloadBtn.disabled = selectedCount === 0;
        deleteBtn.disabled = selectedCount === 0;
        
        downloadBtn.innerHTML = selectedCount > 0 ? 
            `<i class="bi bi-download"></i> 下载选中 (${selectedCount})` :
            `<i class="bi bi-download"></i> 下载选中`;
            
        deleteBtn.innerHTML = selectedCount > 0 ? 
            `<i class="bi bi-trash"></i> 删除选中 (${selectedCount})` :
            `<i class="bi bi-trash"></i> 删除选中`;

        // 更新全选框状态
        const selectAllCheckbox = document.getElementById('select-all-checkbox');
        if (selectedCount === 0) {
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.checked = false;
        } else if (selectedCount === this.filteredFiles.length) {
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.checked = true;
        } else {
            selectAllCheckbox.indeterminate = true;
            selectAllCheckbox.checked = false;
        }
    }

    clearSelection() {
        this.selectedFiles.clear();
        document.querySelectorAll('.file-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
        document.querySelectorAll('.file-item').forEach(row => {
            row.classList.remove('selected');
        });
        this.updateSelectionUI();
    }

    async downloadFile(fileId) {
        try {
            const url = `/api/files/download/${encodeURIComponent(fileId)}`;
            
            // 创建隐藏的下载链接
            const link = document.createElement('a');
            link.href = url;
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
        } catch (error) {
            console.error('下载失败:', error);
            this.showError('下载失败: ' + error.message);
        }
    }

    async downloadSelected() {
        if (this.selectedFiles.size === 0) return;

        try {
            // 依次下载所有选中的文件
            for (const fileId of this.selectedFiles) {
                await this.downloadFile(fileId);
                // 稍微延迟，避免浏览器阻止多个下载
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            
            this.showSuccess(`已开始下载 ${this.selectedFiles.size} 个文件`);
        } catch (error) {
            console.error('批量下载失败:', error);
            this.showError('批量下载失败: ' + error.message);
        }
    }

    showDeleteModal() {
        console.log('showDeleteModal called, selectedFiles:', this.selectedFiles);
        if (this.selectedFiles.size === 0) {
            this.showError('请先选择要删除的文件');
            return;
        }
        
        document.getElementById('delete-count').textContent = this.selectedFiles.size;
        const modal = new bootstrap.Modal(document.getElementById('deleteModal'));
        modal.show();
    }

    showDeleteTaskModal(taskId, taskTitle) {
        document.getElementById('task-title-to-delete').textContent = taskTitle;
        document.getElementById('confirm-task-delete-btn').dataset.taskId = taskId;
        
        const modal = new bootstrap.Modal(document.getElementById('deleteTaskModal'));
        modal.show();
    }

    async deleteSelected() {
        console.log('deleteSelected called, selectedFiles:', this.selectedFiles);
        if (this.selectedFiles.size === 0) return;

        try {
            const fileIds = Array.from(this.selectedFiles);
            console.log('Sending delete request with fileIds:', fileIds);
            
            const response = await fetch('/api/files/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ file_ids: fileIds })
            });

            console.log('Delete response status:', response.status);
            const result = await response.json();
            console.log('Delete response result:', result);
            
            if (result.success) {
                this.showSuccess(result.message);
                
                if (result.errors && result.errors.length > 0) {
                    console.warn('部分删除失败:', result.errors);
                }
                
                // 关闭模态框并重新加载文件列表
                const modal = bootstrap.Modal.getInstance(document.getElementById('deleteModal'));
                if (modal) {
                    modal.hide();
                }
                
                this.clearSelection();
                await this.loadFiles();
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            console.error('删除失败:', error);
            this.showError('删除失败: ' + error.message);
        }
    }

    async deleteTask() {
        const taskId = document.getElementById('confirm-task-delete-btn').dataset.taskId;
        if (!taskId) return;

        try {
            const response = await fetch(`/api/files/delete-task/${encodeURIComponent(taskId)}`, {
                method: 'POST'
            });

            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(result.message);
                
                // 关闭模态框并重新加载文件列表
                const modal = bootstrap.Modal.getInstance(document.getElementById('deleteTaskModal'));
                modal.hide();
                
                this.clearSelection();
                await this.loadFiles();
            } else {
                throw new Error(result.message);
            }
        } catch (error) {
            console.error('删除任务失败:', error);
            this.showError('删除任务失败: ' + error.message);
        }
    }

    showFileInfo(fileId) {
        const file = this.files.find(f => f.id === fileId);
        if (!file) return;

        const info = `
            文件名: ${file.file_name}
            类型: ${file.description}
            任务: ${file.task_title}
            大小: ${file.size_human}
            修改时间: ${file.modified_time}
            路径: ${file.file_path}
        `;
        
        alert(info);
    }

    updateStats() {
        const totalFiles = this.files.length;
        const totalSize = this.files.reduce((sum, file) => sum + file.size, 0);
        const videoCount = this.files.filter(f => f.file_type === 'video').length;
        const audioCount = this.files.filter(f => f.file_type === 'audio').length;

        document.getElementById('total-files').textContent = totalFiles;
        document.getElementById('total-size').textContent = this.formatBytes(totalSize);
        document.getElementById('video-count').textContent = videoCount;
        document.getElementById('audio-count').textContent = audioCount;
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    getFileTypeIcon(fileType) {
        const icons = {
            video: '<i class="bi bi-play-circle"></i>',
            audio: '<i class="bi bi-music-note"></i>',
            transcript: 'TXT',
            summary: 'MD',
            data: 'JSON',
            text: 'TXT',
            image: '<i class="bi bi-image"></i>',
            other: '?'
        };
        return icons[fileType] || icons.other;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showLoading(show) {
        const loading = document.getElementById('loading');
        const filesList = document.getElementById('files-list');
        const emptyState = document.getElementById('empty-state');
        
        if (show) {
            loading.classList.remove('d-none');
            filesList.classList.add('d-none');
            emptyState.classList.add('d-none');
        } else {
            loading.classList.add('d-none');
        }
    }

    showEmptyState(show) {
        const emptyState = document.getElementById('empty-state');
        if (show) {
            emptyState.classList.remove('d-none');
        } else {
            emptyState.classList.add('d-none');
        }
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showError(message) {
        this.showToast(message, 'danger');
    }

    showToast(message, type) {
        // 创建一个简单的toast提示
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <span class="me-2">${message}</span>
                <button type="button" class="btn-close" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // 3秒后自动消失
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 3000);
    }
}

// 初始化文件管理器
document.addEventListener('DOMContentLoaded', () => {
    new FilesManager();
});