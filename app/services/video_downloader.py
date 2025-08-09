import yt_dlp
import os
import asyncio
from typing import Dict, Any, Optional
from app.config.settings import Config
from app.services.file_manager import FileManager

class VideoDownloader:
    """简化的视频下载器 - 仅支持音频下载"""
    
    def __init__(self):
        self.config = Config.load_config()
        self.temp_dir = self.config['system']['temp_dir']
        self.file_manager = FileManager()
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def _get_downloader_config(self, url: str) -> Dict[str, Any]:
        """根据URL获取下载器配置"""
        base_opts = {
            'quiet': self.config.get('downloader', {}).get('general', {}).get('quiet', False),
            'no_warnings': False,
        }
        
        # YouTube配置
        if 'youtube.com' in url or 'youtu.be' in url:
            base_opts.update({
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['webpage']
                    }
                },
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
        
        return base_opts
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频基本信息"""
        ydl_opts = self._get_downloader_config(url)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'url': url,
                    'thumbnail': info.get('thumbnail', ''),
                    'description': info.get('description', '')[:500] + '...' if info.get('description', '') else ''
                }
            except Exception as e:
                # 提供更友好的错误信息
                error_msg = str(e)
                raise Exception(f"无法获取视频信息: {error_msg}")
    
    def download_audio_only(self, url: str, task_id: str, output_path: Optional[str] = None) -> str:
        """仅下载音频"""
        if not output_path:
            task_temp_dir = self.file_manager.get_task_temp_dir(task_id)
            output_path = os.path.join(task_temp_dir, '%(title)s.%(ext)s')
        
        ydl_opts = self._get_downloader_config(url)
        ydl_opts.update({
            'outtmpl': output_path,
            'format': self.config.get('downloader', {}).get('general', {}).get('audio_format', 'bestaudio/best'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'ffmpeg_location': '/usr/bin/ffmpeg' if os.name == 'posix' else 'C:\\ffmpeg',  # 根据系统指定ffmpeg位置
        })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                base_filename = ydl.prepare_filename(info)
                audio_filename = os.path.splitext(base_filename)[0] + '.wav'
                
                # 注册文件到管理器
                self.file_manager.register_task(task_id, [audio_filename])
                
                return audio_filename
            except Exception as e:
                error_msg = str(e)
                raise Exception(f"音频下载失败: {error_msg}")
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        try:
            for file in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        except Exception as e:
            print(f"清理临时文件失败: {e}")

    def get_supported_platforms_info(self) -> Dict[str, Any]:
        """获取支持平台的配置信息"""
        return {
            'youtube': {
                'name': 'YouTube',
                'requires_login': False,
                'notes': '支持所有公开视频，仅音频下载'
            }
        }

if __name__ == "__main__":
    # 测试代码
    downloader = VideoDownloader()
    try:
        info = downloader.get_video_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        print(f"视频标题: {info['title']}")
        print(f"时长: {info['duration']}秒")
        
        # 显示支持的平台信息
        platforms = downloader.get_supported_platforms_info()
        print("\n支持的平台:")
        for platform, info in platforms.items():
            print(f"- {info['name']}: {info['notes']}")
    except Exception as e:
        print(f"测试失败: {e}")