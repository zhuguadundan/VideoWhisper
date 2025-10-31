import os
import re
import uuid
import mimetypes
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
from app.config.settings import Config
from app.services.file_manager import FileManager
from app.models.data_models import UploadTask
import logging

logger = logging.getLogger(__name__)


class FileUploader:
    """文件上传服务 - 处理本地视频和音频文件上传"""
    
    def __init__(self):
        self.config = Config.load_config()
        self.file_manager = FileManager()
        
        # 获取上传配置
        self.max_upload_size = self.config.get('upload', {}).get('max_upload_size', 500) * 1024 * 1024  # MB to bytes
        self.allowed_video_formats = self.config.get('upload', {}).get('allowed_video_formats', 
                                                                   ['mp4', 'avi', 'mov', 'mkv', 'webm', 'flv'])
        self.allowed_audio_formats = self.config.get('upload', {}).get('allowed_audio_formats', 
                                                                   ['mp3', 'wav', 'aac', 'm4a', 'ogg'])
        self.upload_chunk_size = self.config.get('upload', {}).get('upload_chunk_size', 5) * 1024 * 1024  # MB to bytes
        
        # 临时存储目录（锚定项目根）
        base_tmp = Config.resolve_path(self.config['system']['temp_dir'])
        self.temp_upload_dir = os.path.join(base_tmp, 'uploads')
        os.makedirs(self.temp_upload_dir, exist_ok=True)
        
        # 支持的MIME类型
        self.supported_video_mimes = [
            'video/mp4', 'video/avi', 'video/quicktime', 'video/x-matroska', 
            'video/webm', 'video/x-flv'
        ]
        self.supported_audio_mimes = [
            'audio/mp3', 'audio/wav', 'audio/aac', 'audio/mp4', 'audio/ogg',
            'audio/mpeg', 'audio/x-wav', 'audio/x-m4a'
        ]
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符，适配Windows系统"""
        if not filename:
            return "uploaded_file"
        
        # Windows禁用字符: < > : " | ? * \ /
        illegal_chars = r'[<>:"|?*\\\/]'
        
        # 替换非法字符为下划线
        sanitized = re.sub(illegal_chars, '_', filename)
        
        # 移除开头结尾的空格和点号（Windows特殊要求）
        sanitized = sanitized.strip(' .')
        
        # 限制长度避免路径过长问题
        if len(sanitized) > 100:
            name_part, ext_part = os.path.splitext(sanitized)
            if ext_part:
                # 保留扩展名，截断文件名部分
                max_name_length = 100 - len(ext_part)
                sanitized = name_part[:max_name_length] + ext_part
            else:
                sanitized = sanitized[:100]
        
        # 如果清理后为空，使用默认名称
        if not sanitized:
            sanitized = 'uploaded_file'
            
        return sanitized
    
    def _get_file_info(self, filename: str, file_size: int) -> Dict[str, Any]:
        """获取文件基本信息"""
        # 确定文件类型
        file_ext = os.path.splitext(filename)[1].lower().lstrip('.')
        
        if file_ext in self.allowed_video_formats:
            file_type = "video"
            need_audio_extraction = True
        elif file_ext in self.allowed_audio_formats:
            file_type = "audio"
            need_audio_extraction = False
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}")
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            # 根据扩展名推断MIME类型
            if file_type == "video":
                mime_type = f"video/{file_ext}"
            else:
                mime_type = f"audio/{file_ext}"
        
        return {
            'file_type': file_type,
            'file_ext': file_ext,
            'mime_type': mime_type,
            'need_audio_extraction': need_audio_extraction,
            'file_size': file_size
        }
    
    def _validate_file(self, filename: str, file_size: int, mime_type: str) -> Tuple[bool, str]:
        """验证文件是否合法"""
        # 检查文件大小
        if file_size > self.max_upload_size:
            return False, f"文件大小超过限制（最大 {self.max_upload_size // (1024*1024)}MB）"
        
        if file_size == 0:
            return False, "文件为空"
        
        # 检查文件扩展名
        file_ext = os.path.splitext(filename)[1].lower().lstrip('.')
        if (file_ext not in self.allowed_video_formats and 
            file_ext not in self.allowed_audio_formats):
            return False, f"不支持的文件格式: {file_ext}"
        
        # 检查MIME类型
        if mime_type:
            if (mime_type not in self.supported_video_mimes and 
                mime_type not in self.supported_audio_mimes):
                logger.warning(f"MIME类型不匹配: {mime_type}")
        
        # 基本安全检查 - 防止路径遍历攻击
        if '..' in filename or '/' in filename or '\\' in filename:
            return False, "文件名包含非法字符"
        
        return True, "文件验证通过"
    
    def _generate_unique_filename(self, original_filename: str) -> str:
        """生成唯一的文件名"""
        # 清理文件名
        safe_filename = self._sanitize_filename(original_filename)
        
        # 生成唯一标识符
        unique_id = str(uuid.uuid4())[:8]

        # 分割文件名和扩展名
        name_part, ext_part = os.path.splitext(safe_filename)

        # 构建新文件名（扩展名只拼接一次）
        base_name = f"{name_part}_{unique_id}"
        new_filename = f"{base_name}{ext_part}"

        # 确保文件名唯一
        counter = 1
        while os.path.exists(os.path.join(self.temp_upload_dir, new_filename)):
            new_filename = f"{base_name}_{counter}{ext_part}"
            counter += 1
        
        return new_filename
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件的MD5哈希值，用于去重"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def create_upload_task(self, original_filename: str, file_size: int, 
                        file_type: str, mime_type: str) -> UploadTask:
        """创建上传任务"""
        task_id = str(uuid.uuid4())
        
        task = UploadTask(
            id=task_id,
            video_url="",  # 文件上传任务没有URL
            file_type=file_type,
            original_filename=original_filename,
            file_size=file_size,
            upload_status="pending",
            need_audio_extraction=(file_type == "video")
        )
        
        return task
    
    def get_upload_progress(self, task_id: str) -> Dict[str, Any]:
        """获取上传进度"""
        # 这里可以实现更复杂的进度跟踪逻辑
        # 目前返回基本任务信息
        return {
            'task_id': task_id,
            'upload_progress': 0,
            'upload_status': 'pending',
            'message': '等待上传'
        }
    
    def save_uploaded_file(self, file_obj, original_filename: str, 
                        file_size: int, chunk_size: int = None) -> Dict[str, Any]:
        """保存上传的文件"""
        if chunk_size is None:
            chunk_size = self.upload_chunk_size
        
        try:
            # 验证文件
            file_info = self._get_file_info(original_filename, file_size)
            mime_type = file_info['mime_type']
            
            is_valid, message = self._validate_file(original_filename, file_size, mime_type)
            if not is_valid:
                raise ValueError(message)
            
            # 生成唯一文件名
            unique_filename = self._generate_unique_filename(original_filename)
            file_path = os.path.join(self.temp_upload_dir, unique_filename)
            
            # 保存文件（任务统一由 VideoProcessor 管理，此处不创建 UploadTask）
            _upload_progress = 0
            
            saved_size = 0
            chunk_count = 0
            total_chunks = (file_size + chunk_size - 1) // chunk_size
            
            with open(file_path, 'wb') as f:
                while True:
                    chunk = file_obj.read(chunk_size)
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    saved_size += len(chunk)
                    chunk_count += 1
                    
                    # 更新上传进度
                    progress = int((saved_size / file_size) * 100)
                    _upload_progress = progress
                    
                    # 每10个chunk更新一次进度（避免过于频繁）
                    if chunk_count % 10 == 0 or progress == 100:
                        logger.info(
                            f"上传进度: {progress}% ({saved_size}/{file_size} bytes) — {unique_filename}"
                        )
            
            # 验证文件完整性
            if saved_size != file_size:
                os.remove(file_path)
                raise ValueError(f"文件上传不完整（预期 {file_size} bytes，实际 {saved_size} bytes）")
            
            # 上传完成
            _upload_progress = 100
            
            # 计算文件哈希
            file_hash = self._calculate_file_hash(file_path)
            
            logger.info(f"文件上传完成: {unique_filename}")
            logger.debug(f"文件路径: {file_path}")
            logger.debug(f"文件哈希: {file_hash}")
            
            return {
                'success': True,
                'file_path': file_path,
                'file_hash': file_hash,
                'message': '文件上传成功'
            }
            
        except Exception as e:
            # 清理可能已创建的文件
            if 'file_path' in locals() and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            
            return {
                'success': False,
                'error': str(e),
                'message': f'文件上传失败: {str(e)}'
            }
    
    def get_file_info_from_path(self, file_path: str) -> Dict[str, Any]:
        """从文件路径获取文件信息"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        file_stat = os.stat(file_path)
        filename = os.path.basename(file_path)
        file_size = file_stat.st_size
        
        try:
            file_info = self._get_file_info(filename, file_size)
            
            # 获取音频/视频时长（需要外部工具）
            duration = self._get_media_duration(file_path, file_info['file_type'])
            
            return {
                'filename': filename,
                'file_size': file_size,
                'file_type': file_info['file_type'],
                'file_ext': file_info['file_ext'],
                'mime_type': file_info['mime_type'],
                'duration': duration,
                'need_audio_extraction': file_info['need_audio_extraction'],
                'created_time': datetime.fromtimestamp(file_stat.st_ctime),
                'modified_time': datetime.fromtimestamp(file_stat.st_mtime)
            }
            
        except Exception as e:
            return {
                'filename': filename,
                'file_size': file_size,
                'error': f"获取文件信息失败: {str(e)}"
            }
    
    def _get_media_duration(self, file_path: str, file_type: str) -> float:
        """获取媒体文件时长（需要安装ffprobe）"""
        try:
            import subprocess
            import json
            
            # 使用ffprobe获取媒体信息
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format',
                '-show_streams', file_path
            ]
            
            # 首先检查ffprobe是否可用
            import shutil
            if not shutil.which('ffprobe'):
                logger.warning("ffprobe未安装，无法获取媒体时长")
                return 0.0
            
            logger.debug(f"正在获取媒体时长: {file_path}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                logger.warning(f"ffprobe执行失败，返回码: {result.returncode}")
                logger.warning(f"错误输出: {result.stderr}")
                return 0.0
            
            if not result.stdout.strip():
                logger.warning("ffprobe返回空输出")
                return 0.0
            
            try:
                media_info = json.loads(result.stdout)
                logger.debug("ffprobe成功解析媒体信息")
            except json.JSONDecodeError as e:
                logger.warning(f"解析ffprobe输出失败: {e}")
                logger.debug(f"ffprobe输出: {result.stdout[:200]}...")
                return 0.0
            
            # 获取时长
            if 'format' in media_info and 'duration' in media_info['format']:
                duration = float(media_info['format']['duration'])
                logger.debug(f"从format获取时长: {duration}")
                return duration
            elif 'streams' in media_info:
                # 从视频或音频流中获取时长
                for stream in media_info['streams']:
                    if 'duration' in stream:
                        duration = float(stream['duration'])
                        logger.debug(f"从stream获取时长: {duration}")
                        return duration
            
            logger.warning("无法从媒体信息中获取时长")
            logger.debug(f"媒体信息: {str(media_info)[:200]}...")
            return 0.0
            
        except ImportError as e:
            logger.warning(f"导入依赖失败: {e}")
            return 0.0
        except Exception as e:
            logger.warning(f"获取媒体时长时发生异常: {e}")
            return 0.0
    
    def cleanup_upload_file(self, file_path: str) -> bool:
        """清理上传的文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"清理上传文件: {file_path}")
                return True
            return False
        except Exception as e:
            logger.warning(f"清理上传文件失败 {file_path}: {e}")
            return False
    
    def get_upload_config(self) -> Dict[str, Any]:
        """获取上传配置信息"""
        return {
            'max_upload_size_mb': self.max_upload_size // (1024 * 1024),
            'max_upload_size_bytes': self.max_upload_size,
            'allowed_video_formats': self.allowed_video_formats,
            'allowed_audio_formats': self.allowed_audio_formats,
            'upload_chunk_size_mb': self.upload_chunk_size // (1024 * 1024),
            'upload_chunk_size_bytes': self.upload_chunk_size,
            'supported_video_mimes': self.supported_video_mimes,
            'supported_audio_mimes': self.supported_audio_mimes
        }


if __name__ == "__main__":
    # 测试代码
    uploader = FileUploader()
    config = uploader.get_upload_config()
    print("文件上传器初始化成功")
    print(f"最大上传大小: {config['max_upload_size_mb']}MB")
    print(f"支持的视频格式: {config['allowed_video_formats']}")
    print(f"支持的音频格式: {config['allowed_audio_formats']}")
