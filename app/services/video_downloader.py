import yt_dlp
import os
import asyncio
import shutil
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
    
    def _get_ffmpeg_path(self) -> Optional[str]:
        """检测FFmpeg路径"""
        # 首先尝试从系统PATH中找到ffmpeg
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            return ffmpeg_path
        
        # Windows下的常见安装位置
        if os.name == 'nt':
            common_paths = [
                'C:\\ffmpeg\\bin\\ffmpeg.exe',
                'C:\\ffmpeg\\ffmpeg.exe',
                'C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe',
                'C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe'
            ]
            for path in common_paths:
                if os.path.exists(path):
                    return path
        
        # Linux/Mac下的常见位置
        else:
            common_paths = [
                '/usr/bin/ffmpeg',
                '/usr/local/bin/ffmpeg',
                '/opt/homebrew/bin/ffmpeg'
            ]
            for path in common_paths:
                if os.path.exists(path):
                    return path
        
        print("警告: 未找到FFmpeg，请确保已安装FFmpeg并添加到系统PATH")
        return None
    
    def _get_info_extraction_config(self, url: str, cookies_str: str = None) -> Dict[str, Any]:
        """专门用于信息提取的配置 - 确保获取完整元数据"""
        base_opts = {
            'quiet': self.config.get('downloader', {}).get('general', {}).get('quiet', False),
            'no_warnings': False,
            'extract_flat': False,  # 确保提取完整信息
            'writeinfojson': False,  # 不需要写入信息文件
        }
        
        # YouTube配置 - 专门为信息提取优化
        if 'youtube.com' in url or 'youtu.be' in url:
            base_opts.update({
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web', 'android', 'ios'],  # 多客户端尝试
                        # 不跳过网页解析，确保获取完整元数据
                        'skip': [],  # 不跳过任何信息源
                    }
                },
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
        
        # 处理cookies（复用原有逻辑）
        if cookies_str and ('youtube.com' in url or 'youtu.be' in url):
            import tempfile
            cookies_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            cookies_file.write("# Netscape HTTP Cookie File\n")
            
            for cookie_pair in cookies_str.split(';'):
                cookie_pair = cookie_pair.strip()
                if '=' in cookie_pair:
                    name, value = cookie_pair.split('=', 1)
                    name, value = name.strip(), value.strip()
                    cookies_file.write(f"youtube.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
            
            cookies_file.close()
            base_opts['cookiefile'] = cookies_file.name
        
        return base_opts

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
        # 使用专门的信息提取配置，确保获取完整元数据
        ydl_opts = self._get_info_extraction_config(url, cookies_str)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                # 尝试多个可能的上传者字段，确保获取到准确信息
                # 按优先级顺序尝试不同的字段
                uploader = None
                
                # 优先级1: 频道相关信息（通常最准确）
                if info.get('channel'):
                    uploader = info['channel']
                elif info.get('channel_id'):
                    uploader = info['channel_id']
                
                # 优先级2: 上传者信息
                elif info.get('uploader'):
                    uploader = info['uploader']
                elif info.get('uploader_id'):
                    uploader = info['uploader_id']
                
                # 优先级3: 其他创建者信息
                elif info.get('creator'):
                    uploader = info['creator']
                elif info.get('artist'):
                    uploader = info['artist']
                
                # 最后的备选
                if not uploader or uploader == 'NA':
                    uploader = 'Unknown'
                
                # 调试输出 - 帮助诊断问题
                print(f"[DEBUG] 视频信息提取:")
                print(f"  - channel: {info.get('channel', 'None')}")
                print(f"  - uploader: {info.get('uploader', 'None')}")
                print(f"  - uploader_id: {info.get('uploader_id', 'None')}")
                print(f"  - creator: {info.get('creator', 'None')}")
                print(f"  - 最终选择: {uploader}")
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': uploader,
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
            # 检测FFmpeg位置
            'ffmpeg_location': self._get_ffmpeg_path(),
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