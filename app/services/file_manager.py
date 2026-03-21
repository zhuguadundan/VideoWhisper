import os
import json
import shutil
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.config.settings import Config

logger = logging.getLogger(__name__)

class FileManager:
    def __init__(self):
        try:
            cfg = Config.get_config() or {}
        except Exception:
            cfg = {}
        system_cfg = cfg.get('system') or {}
        temp_dir = system_cfg.get('temp_dir', 'temp')
        output_dir = system_cfg.get('output_dir', 'output')
        self.temp_dir = Config.resolve_path(temp_dir)
        self.output_dir = Config.resolve_path(output_dir)
        self.max_temp_tasks = 3
        self._ensure_directories()
        self.task_history_file = os.path.join(self.temp_dir, '.task_history.json')
        self._init_task_history_file()

    def _ensure_directories(self):
        try:
            os.makedirs(self.temp_dir, exist_ok=True)
            os.makedirs(self.output_dir, exist_ok=True)
        except Exception as e:
            logger.error(f'创建目录失败: {e}')

    def _init_task_history_file(self):
        if not os.path.exists(self.task_history_file):
            try:
                with open(self.task_history_file, 'w', encoding='utf-8') as f:
                    json.dump([], f)
            except Exception as e:
                logger.error(f'初始化任务历史文件失败: {e}')

    def get_task_history(self) -> List[Dict[str, Any]]:
        try:
            if os.path.exists(self.task_history_file):
                with open(self.task_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f) or []
        except Exception:
            return []
        return []

    def save_task_history(self, history: List[Dict[str, Any]]):
        try:
            with open(self.task_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f'保存任务历史失败: {e}')

    def register_task(self, task_id: str, files: List[str], register_dir: bool = False):
        history = self.get_task_history()
        for entry in history:
            if entry.get('task_id') == task_id:
                existing = set(entry.get('files', []))
                for fp in files:
                    if fp not in existing:
                        entry.setdefault('files', []).append(fp)
                if register_dir:
                    entry['task_dir'] = os.path.join(self.temp_dir, task_id)
                break
        else:
            new_task = {
                'task_id': task_id,
                'created_at': datetime.now().isoformat(),
                'files': files or []
            }
            if register_dir:
                new_task['task_dir'] = os.path.join(self.temp_dir, task_id)
            history.append(new_task)
        history.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        history = history[: self.max_temp_tasks]
        self.save_task_history(history)

    def _is_valid_task_id(self, task_id: str) -> bool:
        try:
            uuid_obj = uuid.UUID(str(task_id))
            return str(uuid_obj) == str(task_id).lower()
        except Exception:
            return False

    def _is_safe_within_temp(self, path: str) -> bool:
        try:
            base = os.path.realpath(self.temp_dir)
            target = os.path.realpath(path)
            return os.path.commonpath([base]) == os.path.commonpath([base, target])
        except Exception:
            return False

    def _get_safe_output_task_dir(self, task_id: str) -> Optional[str]:
        try:
            if not self._is_valid_task_id(task_id):
                return None
            base_abs = os.path.realpath(self.output_dir)
            task_dir = os.path.realpath(os.path.join(base_abs, task_id))
            if os.path.commonpath([base_abs]) != os.path.commonpath([base_abs, task_dir]):
                return None
            return task_dir
        except Exception:
            return None

    def _get_dir_size_bytes(self, directory: str) -> int:
        total = 0
        try:
            for root, _dirs, files in os.walk(directory):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    if os.path.exists(file_path):
                        total += os.path.getsize(file_path)
        except Exception:
            return total
        return total

    def _safe_remove_task_dir(self, task_id: str, task_temp_dir: str):
        try:
            if not self._is_valid_task_id(task_id):
                return
            if not self._is_safe_within_temp(task_temp_dir):
                return
            if os.path.exists(task_temp_dir):
                shutil.rmtree(task_temp_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f'安全删除目录失败: {task_temp_dir}, 错误: {e}')

    def cleanup_task_files(self, task_id: str):
        history = self.get_task_history()
        for task in list(history):
            if task.get('task_id') == task_id:
                try:
                    for fp in task.get('files', []):
                        if os.path.exists(fp):
                            os.remove(fp)
                    task_temp_dir = os.path.join(self.temp_dir, task_id)
                    self._safe_remove_task_dir(task_id, task_temp_dir)
                    history.remove(task)
                    self.save_task_history(history)
                except Exception as e:
                    logger.error(f'清理任务 {task_id} 文件时出错: {e}')
                break

    def cleanup_excess_tasks(self):
        """清理超过 max_temp_tasks 限制的历史任务及其临时文件。

        设计目标：
        - 仅作为“软限制”保护磁盘空间，失败不应影响主流程。
        - 依赖已有的 cleanup_task_files 实现，避免重复路径处理逻辑。
        """
        try:
            history = self.get_task_history()
            if len(history) <= self.max_temp_tasks:
                return
            # history 按创建时间倒序，保留前 max_temp_tasks 个，清掉更旧的
            overflow = history[self.max_temp_tasks :]
            for entry in overflow:
                task_id = entry.get('task_id')
                if not task_id:
                    continue
                try:
                    self.cleanup_task_files(task_id)
                except Exception as e:
                    logger.warning(f'清理历史任务 {task_id} 时出错: {e}')
        except Exception as e:
            logger.warning(f'执行 cleanup_excess_tasks 时出错: {e}')

    def get_task_temp_dir(self, task_id: str) -> str:
        return os.path.join(self.temp_dir, task_id)

    def get_temp_file_path(self, task_id: str, filename: str) -> str:
        return os.path.join(self.get_task_temp_dir(task_id), filename)

    def delete_output_task_dir(self, task_id: str) -> bool:
        try:
            task_dir = self._get_safe_output_task_dir(task_id)
            if not task_dir:
                return False
            if os.path.exists(task_dir):
                shutil.rmtree(task_dir, ignore_errors=True)
                return True
            return False
        except Exception:
            return False

    def cleanup_task_partial_dir(self, task_id: str) -> bool:
        try:
            task_dir = self._get_safe_output_task_dir(task_id)
            if not task_dir:
                return False
            partial_dir = os.path.realpath(os.path.join(task_dir, '.partial'))
            if os.path.commonpath([task_dir]) != os.path.commonpath([task_dir, partial_dir]):
                return False
            if os.path.isdir(partial_dir):
                shutil.rmtree(partial_dir, ignore_errors=True)
                return not os.path.exists(partial_dir)
            return False
        except Exception:
            return False

    def cleanup_stale_partial_dirs(self, active_task_ids: Optional[List[str]] = None) -> Dict[str, int]:
        removed_count = 0
        reclaimed_bytes = 0
        active_ids = {str(task_id).lower() for task_id in (active_task_ids or [])}
        try:
            if not os.path.exists(self.output_dir):
                return {'removed_count': 0, 'reclaimed_bytes': 0}

            for task_id in os.listdir(self.output_dir):
                task_dir = self._get_safe_output_task_dir(task_id)
                if not task_dir or task_id.lower() in active_ids:
                    continue

                partial_dir = os.path.realpath(os.path.join(task_dir, '.partial'))
                if os.path.commonpath([task_dir]) != os.path.commonpath([task_dir, partial_dir]):
                    continue
                if not os.path.isdir(partial_dir):
                    continue

                reclaimed_bytes += self._get_dir_size_bytes(partial_dir)
                shutil.rmtree(partial_dir, ignore_errors=True)
                if not os.path.exists(partial_dir):
                    removed_count += 1
        except Exception as e:
            logger.warning(f'清理残留部分下载目录时出错: {e}')
        return {'removed_count': removed_count, 'reclaimed_bytes': reclaimed_bytes}

    def get_file_size_mb(self, file_path: str) -> float:
        if os.path.exists(file_path):
            return os.path.getsize(file_path) / (1024 * 1024)
        return 0.0

    def get_storage_stats(self) -> Dict[str, Any]:
        temp_size = 0
        output_size = 0
        temp_count = 0
        output_count = 0
        if os.path.exists(self.temp_dir):
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    if not file.startswith('.'):
                        temp_size += os.path.getsize(os.path.join(root, file))
                        temp_count += 1
        if os.path.exists(self.output_dir):
            for root, dirs, files in os.walk(self.output_dir):
                for file in files:
                    output_size += os.path.getsize(os.path.join(root, file))
                    output_count += 1
        return {
            'temp_size_mb': round(temp_size / (1024 * 1024), 2),
            'output_size_mb': round(output_size / (1024 * 1024), 2),
            'temp_file_count': temp_count,
            'output_file_count': output_count,
            'active_tasks': len(self.get_task_history()),
        }

if __name__ == '__main__':
    fm = FileManager()
    stats = fm.get_storage_stats()
    logger.info(f'存储统计: {stats}')
