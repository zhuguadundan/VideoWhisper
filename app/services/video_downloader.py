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
    
    def _get_downloader_config(self, url: str, cookies_str: str = None) -> Dict[str, Any]:
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
            
            # 优先使用传入的 cookies 字符串
            if cookies_str:
                # 创建临时 cookies 文件
                import tempfile
                cookies_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
                cookies_file.write("# Netscape HTTP Cookie File\n")
                
                # 解析 cookies 字符串并写入文件
                for cookie_pair in cookies_str.split(';'):
                    cookie_pair = cookie_pair.strip()
                    if '=' in cookie_pair:
                        name, value = cookie_pair.split('=', 1)
                        name, value = name.strip(), value.strip()
                        # 简化的 Netscape cookies 格式
                        cookies_file.write(f".youtube.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
                
                cookies_file.close()
                base_opts['cookiefile'] = cookies_file.name
            else:
                # 尝试从 cookies 文件加载
                cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
                if os.path.exists(cookies_path):
                    base_opts['cookiefile'] = cookies_path
                else:
                    # 尝试从浏览器导入 cookies
                    try:
                        base_opts['cookiesfrombrowser'] = ('chrome',)
                    except:
                        # 如果浏览器 cookies 导入失败，尝试其他浏览器
                        for browser in ['firefox', 'edge', 'safari']:
                            try:
                                base_opts['cookiesfrombrowser'] = (browser,)
                                break
                            except:
                                continue
        
        return base_opts
    
    def _parse_cookies_string(self, cookies_str: str) -> Dict[str, str]:
        """解析 cookies 字符串为字典"""
        try:
            cookies_dict = {}
            # 处理格式: "name1=value1; name2=value2; ..."
            for cookie_pair in cookies_str.split(';'):
                cookie_pair = cookie_pair.strip()
                if '=' in cookie_pair:
                    name, value = cookie_pair.split('=', 1)
                    cookies_dict[name.strip()] = value.strip()
            return cookies_dict
        except Exception as e:
            print(f"解析cookies失败: {e}")
            return {}
    
    def get_video_info(self, url: str, cookies_str: str = None) -> Dict[str, Any]:
        """获取视频基本信息"""
        ydl_opts = self._get_downloader_config(url, cookies_str)
        
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
                
                # 检查是否是YouTube的机器人验证错误
                if "Sign in to confirm you're not a bot" in error_msg or "Use --cookies" in error_msg:
                    raise Exception(f"YouTube 需要身份验证。请尝试以下解决方案：\n"
                                  f"1. 将 cookies.txt 文件放在项目根目录下\n"
                                  f"2. 确保已安装并登录 Chrome/Firefox 浏览器\n"
                                  f"3. 如果问题持续，请尝试其他视频链接\n"
                                  f"原始错误: {error_msg}")
                else:
                    raise Exception(f"无法获取视频信息: {error_msg}")
    
    def download_audio_only(self, url: str, task_id: str, output_path: Optional[str] = None, cookies_str: str = None) -> str:
        """仅下载音频"""
        if not output_path:
            task_temp_dir = self.file_manager.get_task_temp_dir(task_id)
            output_path = os.path.join(task_temp_dir, '%(title)s.%(ext)s')
        
        ydl_opts = self._get_downloader_config(url, cookies_str)
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
                
                # 检查是否是YouTube的机器人验证错误
                if "Sign in to confirm you're not a bot" in error_msg or "Use --cookies" in error_msg:
                    raise Exception(f"YouTube 需要身份验证。请尝试以下解决方案：\n"
                                  f"1. 将 cookies.txt 文件放在项目根目录下\n"
                                  f"2. 确保已安装并登录 Chrome/Firefox 浏览器\n"
                                  f"3. 如果问题持续，请尝试其他视频链接\n"
                                  f"原始错误: {error_msg}")
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