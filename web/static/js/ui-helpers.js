// 简单UI辅助方法：toast、进度设置、文件大小格式化

window.UIHelpers = (function() {
  function showToast(message, type = 'info', title = '通知') {
    try {
      const toastEl = document.getElementById('liveToast');
      if (!toastEl) return;
      toastEl.querySelector('.toast-body').textContent = message;
      toastEl.querySelector('.toast-title').textContent = title;
      const icon = toastEl.querySelector('.toast-icon');
      if (icon) {
        icon.className = 'toast-icon me-2';
        const map = { info: 'text-primary', success: 'text-success', warning: 'text-warning', danger: 'text-danger' };
        icon.classList.add(map[type] || 'text-primary');
      }
      const toast = new bootstrap.Toast(toastEl);
      toast.show();
    } catch (_) {}
  }

  function setProgress(el, value) {
    if (!el) return;
    const v = Math.max(0, Math.min(100, Number(value) || 0));
    el.style.width = v + '%';
    el.setAttribute('aria-valuenow', v);
    el.textContent = v + '%';
  }

  function humanFileSize(bytes) {
    try {
      const thresh = 1024;
      if (Math.abs(bytes) < thresh) return bytes + ' B';
      const units = ['KB','MB','GB','TB','PB','EB','ZB','YB'];
      let u = -1;
      do {
        bytes /= thresh;
        ++u;
      } while (Math.abs(bytes) >= thresh && u < units.length - 1);
      return bytes.toFixed(2) + ' ' + units[u];
    } catch (_) { return String(bytes); }
  }

  return { showToast, setProgress, humanFileSize };
})();

