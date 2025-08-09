import os
import json
import shutil
from datetime import datetime
from typing import List, Dict, Any
from app.config.settings import Config

class FileManager:
    """文件管理器 - 处理临时文件的存储策略，支持Docker环境"""
    
    def __init__(self):
        self.config = Config.load_config()
        
        # 使用绝对路径，确保Docker环境兼容
        temp_dir = self.config['system']['temp_dir']
        output_dir = self.config['system']['output_dir']
        
        # 转换为绝对路径
        if not os.path.isabs(temp_dir):
            self.temp_dir = os.path.abspath(temp_dir)
        else:
            self.temp_dir = temp_dir
            
        if not os.path.isabs(output_dir):
            self.output_dir = os.path.abspath(output_dir)
        else:
            self.output_dir = output_dir
        
        self.max_temp_tasks = 3  # 保留最近3次任务的临时文件
        
        # 确保目录存在，Docker环境下可能需要特殊权限处理
        self._ensure_directories()
        
        # 任务历史文件
        self.task_history_file = os.path.join(self.temp_dir, '.task_history.json')
        
        # 初始化任务历史文件
        self._init_task_history_file()
    
    def _ensure_directories(self):
        """确保目录存在并设置正确权限"""
        try:
            os.makedirs(self.temp_dir, exist_ok=True)
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Docker环境下设置权限
            if self._is_docker_environment():
                try:
                    os.chmod(self.temp_dir, 0o755)
                    os.chmod(self.output_dir, 0o755)
                except PermissionError:
                    # 在某些Docker环境中可能没有chmod权限，忽略错误
                    pass
                    
        except Exception as e:
            print(f"创建目录时出错: {e}")
    
    def _is_docker_environment(self) -> bool:
        """检测是否运行在Docker环境中"""
        return (
            os.path.exists('/.dockerenv') or 
            os.environ.get('FLASK_ENV') == 'production' or
            self.temp_dir.startswith('/app/')
        )
    
    def _init_task_history_file(self):
        """初始化任务历史文件"""
        if not os.path.exists(self.task_history_file):
            try:
                with open(self.task_history_file, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                
                # Docker环境下设置文件权限
                if self._is_docker_environment():
                    try:
                        os.chmod(self.task_history_file, 0o644)
                    except PermissionError:
                        pass
                        
            except Exception as e:
                print(f"初始化任务历史文件失败: {e}")
    
    def get_task_history(self) -> List[Dict[str, Any]]:
        """获取任务历史记录"""
        if os.path.exists(self.task_history_file):
            try:
                with open(self.task_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []
    
    def save_task_history(self, history: List[Dict[str, Any]]):
        """保存任务历史记录"""
        try:
            with open(self.task_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存任务历史失败: {e}")
    
    def register_task(self, task_id: str, files: List[str]):
        """注册新任务的文件"""
        history = self.get_task_history()
        
        # 添加新任务记录
        new_task = {
            'task_id': task_id,
            'created_at': datetime.now().isoformat(),
            'files': files
        }
        history.append(new_task)
        
        # 按创建时间排序
        history.sort(key=lambda x: x['created_at'], reverse=True)
        
        # 清理超过限制的任务文件
        self._cleanup_old_tasks(history)
        
        # 只保留最近的任务记录
        history = history[:self.max_temp_tasks]
        self.save_task_history(history)
    
    def _cleanup_old_tasks(self, history: List[Dict[str, Any]]):
        """清理超出保留限制的任务文件"""
        if len(history) <= self.max_temp_tasks:
            return
        
        # 需要清理的任务（超过最近3个的）
        tasks_to_cleanup = history[self.max_temp_tasks:]
        
        for task in tasks_to_cleanup:
            try:
                # 删除任务相关的所有文件
                for file_path in task.get('files', []):
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"清理临时文件: {file_path}")
                
                # 清理任务目录（如果为空）
                task_temp_dir = os.path.join(self.temp_dir, task['task_id'])
                if os.path.exists(task_temp_dir) and not os.listdir(task_temp_dir):
                    os.rmdir(task_temp_dir)
                    
            except Exception as e:
                print(f"清理任务 {task['task_id']} 的文件时出错: {e}")
    
    def get_task_temp_dir(self, task_id: str) -> str:
        """获取任务专用的临时目录"""
        task_temp_dir = os.path.join(self.temp_dir, task_id)
        os.makedirs(task_temp_dir, exist_ok=True)
        return task_temp_dir
    
    def cleanup_task_files(self, task_id: str):
        """立即清理指定任务的所有文件"""
        history = self.get_task_history()
        
        for task in history:
            if task['task_id'] == task_id:
                try:
                    for file_path in task.get('files', []):
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    
                    # 删除任务目录
                    task_temp_dir = os.path.join(self.temp_dir, task_id)
                    if os.path.exists(task_temp_dir):
                        shutil.rmtree(task_temp_dir)
                        
                    # 从历史记录中移除
                    history.remove(task)
                    self.save_task_history(history)
                    print(f"已清理任务 {task_id} 的所有文件")
                    
                except Exception as e:
                    print(f"清理任务 {task_id} 文件时出错: {e}")
                break
    
    def get_temp_file_path(self, task_id: str, filename: str) -> str:
        """获取任务临时文件的完整路径"""
        task_temp_dir = self.get_task_temp_dir(task_id)
        return os.path.join(task_temp_dir, filename)
    
    def get_file_size_mb(self, file_path: str) -> float:
        """获取文件大小（MB）"""
        if os.path.exists(file_path):
            return os.path.getsize(file_path) / (1024 * 1024)
        return 0.0
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        temp_size = 0
        output_size = 0
        temp_count = 0
        output_count = 0
        
        # 统计临时目录
        if os.path.exists(self.temp_dir):
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    if not file.startswith('.'):  # 忽略隐藏文件
                        file_path = os.path.join(root, file)
                        temp_size += os.path.getsize(file_path)
                        temp_count += 1
        
        # 统计输出目录
        if os.path.exists(self.output_dir):
            for root, dirs, files in os.walk(self.output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    output_size += os.path.getsize(file_path)
                    output_count += 1
        
        return {
            'temp_size_mb': round(temp_size / (1024 * 1024), 2),
            'output_size_mb': round(output_size / (1024 * 1024), 2),
            'temp_file_count': temp_count,
            'output_file_count': output_count,
            'active_tasks': len(self.get_task_history())
        }

if __name__ == "__main__":
    # 测试代码
    fm = FileManager()
    stats = fm.get_storage_stats()
    print(f"存储统计: {stats}")