import yt_dlp
import os
import asyncio
from typing import Dict, Any, Optional
from app.config.settings import Config

class VideoDownloader:
    def __init__(self):
        self.config = Config.load_config()
        self.temp_dir = self.config['system']['temp_dir']
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
        
        # 抖音配置
        elif 'douyin.com' in url:
            douyin_config = self.config.get('downloader', {}).get('douyin', {})
            if douyin_config.get('enabled', False):
                # 添加cookie支持
                cookies_file = douyin_config.get('cookies_file')
                cookies_string = douyin_config.get('cookies_string')
                
                if cookies_file and os.path.exists(cookies_file):
                    base_opts['cookiefile'] = cookies_file
                elif cookies_string:
                    base_opts['cookiesfrombrowser'] = None
                    # 将cookie字符串转换为字典
                    cookies = {}
                    for cookie in cookies_string.split(';'):
                        if '=' in cookie:
                            key, value = cookie.strip().split('=', 1)
                            cookies[key] = value
                    base_opts['cookies'] = cookies
                
                # 添加请求头
                base_opts.update({
                    'user_agent': douyin_config.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
                    'referer': douyin_config.get('referer', 'https://www.douyin.com/'),
                    'sleep_interval': douyin_config.get('sleep_interval', 1),
                    'retries': douyin_config.get('max_retries', 3),
                })
        
        return base_opts
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息"""
        ydl_opts = self._get_downloader_config(url)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'url': url,
                    'formats': info.get('formats', [])
                }
            except Exception as e:
                # 提供更友好的错误信息
                error_msg = str(e)
                if 'Fresh cookies' in error_msg and 'douyin.com' in url:
                    raise Exception(f"抖音视频需要有效的Cookie才能下载。请参考项目根目录下的 cookies.txt.example 文件配置Cookie。错误详情: {error_msg}")
                elif 'douyin.com' in url:
                    raise Exception(f"抖音视频下载失败。请检查网络连接和URL有效性，或配置有效的Cookie。错误详情: {error_msg}")
                else:
                    raise Exception(f"无法获取视频信息: {error_msg}")
    
    def download_video(self, url: str, output_path: Optional[str] = None) -> str:
        """下载视频"""
        if not output_path:
            output_path = os.path.join(self.temp_dir, '%(title)s.%(ext)s')
        
        ydl_opts = self._get_downloader_config(url)
        ydl_opts.update({
            'outtmpl': output_path,
            'format': self.config.get('downloader', {}).get('general', {}).get('format', 'best[height<=720]/best'),
        })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return filename
            except Exception as e:
                error_msg = str(e)
                if 'Fresh cookies' in error_msg and 'douyin.com' in url:
                    raise Exception(f"抖音视频需要有效的Cookie才能下载。请参考项目根目录下的 cookies.txt.example 文件配置Cookie。错误详情: {error_msg}")
                elif 'douyin.com' in url:
                    raise Exception(f"抖音视频下载失败。请检查网络连接和URL有效性，或配置有效的Cookie。错误详情: {error_msg}")
                else:
                    raise Exception(f"下载失败: {error_msg}")
    
    def download_audio_only(self, url: str, output_path: Optional[str] = None) -> str:
        """仅下载音频"""
        if not output_path:
            output_path = os.path.join(self.temp_dir, '%(title)s.%(ext)s')
        
        ydl_opts = self._get_downloader_config(url)
        ydl_opts.update({
            'outtmpl': output_path,
            'format': self.config.get('downloader', {}).get('general', {}).get('audio_format', 'bestaudio/best'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'ffmpeg_location': 'C:\\ffmpeg',  # 明确指定ffmpeg位置
        })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                base_filename = ydl.prepare_filename(info)
                audio_filename = os.path.splitext(base_filename)[0] + '.wav'
                return audio_filename
            except Exception as e:
                error_msg = str(e)
                if 'Fresh cookies' in error_msg and 'douyin.com' in url:
                    raise Exception(f"抖音视频需要有效的Cookie才能下载音频。请参考项目根目录下的 cookies.txt.example 文件配置Cookie。错误详情: {error_msg}")
                elif 'douyin.com' in url:
                    raise Exception(f"抖音音频下载失败。请检查网络连接和URL有效性，或配置有效的Cookie。错误详情: {error_msg}")
                else:
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
                'notes': '支持所有公开视频'
            },
            'douyin': {
                'name': '抖音',
                'requires_login': True,
                'enabled': self.config.get('downloader', {}).get('douyin', {}).get('enabled', False),
                'cookie_configured': self._check_douyin_cookie_config(),
                'notes': '需要配置有效的Cookie才能下载'
            }
        }
    
    def _check_douyin_cookie_config(self) -> bool:
        """检查抖音Cookie配置是否有效"""
        douyin_config = self.config.get('downloader', {}).get('douyin', {})
        cookies_file = douyin_config.get('cookies_file')
        cookies_string = douyin_config.get('cookies_string')
        
        if cookies_file and os.path.exists(cookies_file):
            return True
        elif cookies_string and cookies_string.strip():
            return True
        return False

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