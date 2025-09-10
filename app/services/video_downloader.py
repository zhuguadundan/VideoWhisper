import yt_dlp
import os
import asyncio
import shutil
import re
from typing import Dict, Any, Optional
from app.config.settings import Config
from app.services.file_manager import FileManager
import logging

# 统一将模块 print 输出到日志
_logger = logging.getLogger(__name__)
def _log_print(*args, **kwargs):
    try:
        msg = ' '.join(str(a) for a in args)
    except Exception:
        msg = ' '.join(repr(a) for a in args)
    level = kwargs.pop('level', None)
    if level == 'error':
        _logger.error(msg)
    elif level == 'warning':
        _logger.warning(msg)
    else:
        _logger.info(msg)

print = _log_print

class VideoDownloader:
    """简化的视频下载器 - 仅支持音频下载"""
    
    def __init__(self):
        self.config = Config.load_config()
        self.temp_dir = self.config['system']['temp_dir']
        self.file_manager = FileManager()
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符，适配Windows系统"""
        # Windows禁用字符: < > : " | ? * \ /
        # 同时处理其他可能引起问题的字符
        illegal_chars = r'[<>:"|?*\\\\/]'
        
        # 替换非法字符为下划线
        sanitized = re.sub(illegal_chars, '_', filename)
        
        # 移除开头结尾的空格和点号（Windows特殊要求）
        sanitized = sanitized.strip(' .')
        
        # 限制长度避免路径过长问题（Windows路径限制）
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        # 如果清理后为空，使用默认名称
        if not sanitized:
            sanitized = 'audio_file'
            
        return sanitized
    
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
        """专门用于信息提取的配置 - 避免PO Token问题和Chrome Cookie权限问题"""
        base_opts = {
            'quiet': self.config.get('downloader', {}).get('general', {}).get('quiet', False),
            'no_warnings': False,
            'extract_flat': False,  # 确保提取完整信息
            'writeinfojson': False,  # 不需要写入信息文件
        }
        
        # YouTube配置 - 使用单一web客户端避免PO Token要求
        if 'youtube.com' in url or 'youtu.be' in url:
            base_opts.update({
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web'],  # 仅使用web客户端避免PO Token
                        'player_skip': ['dash', 'hls'],  # 跳过可能需要认证的格式
                    }
                },
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
            })
        
        # 处理cookies（复用原有逻辑，但禁用浏览器导入）
        if cookies_str and ('youtube.com' in url or 'youtu.be' in url):
            import tempfile
            cookies_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            cookies_file.write("# Netscape HTTP Cookie File\n")
            
            for cookie_pair in cookies_str.split(';'):
                cookie_pair = cookie_pair.strip()
                if '=' in cookie_pair:
                    name, value = cookie_pair.split('=', 1)
                    name, value = name.strip(), value.strip()
                    cookies_file.write(f".youtube.com\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
            
            cookies_file.close()
            base_opts['cookiefile'] = cookies_file.name
        else:
            # 检查是否有cookies.txt文件
            cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
            if os.path.exists(cookies_path):
                base_opts['cookiefile'] = cookies_path
                print(f"[DEBUG] 信息提取使用cookies文件: {cookies_path}")
            else:
                # *** 禁用浏览器cookies导入以避免权限问题 ***
                print(f"[DEBUG] 信息提取跳过浏览器cookie导入")
        
        return base_opts

    def _get_downloader_config(self, url: str, cookies_str: str = None) -> Dict[str, Any]:
        """根据URL获取下载器配置 - 修复Chrome Cookie权限问题"""
        base_opts = {
            'quiet': self.config.get('downloader', {}).get('general', {}).get('quiet', False),
            'no_warnings': False,
        }
        
        # YouTube配置 - 使用兼容性更好的单一客户端
        if 'youtube.com' in url or 'youtu.be' in url:
            base_opts.update({
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web'],  # 仅使用web客户端
                        'player_skip': ['dash'],  # 跳过dash格式减少认证需求
                    }
                },
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
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
                    print(f"[DEBUG] 使用cookies文件: {cookies_path}")
                else:
                    # *** 禁用浏览器cookies导入以避免权限问题 ***
                    print(f"[DEBUG] 跳过浏览器cookie导入，避免权限问题")
                    # 不再尝试从浏览器导入cookies，这会导致权限错误
                    pass
        
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
        """获取视频基本信息 - 带降级策略"""
        # 使用专门的信息提取配置，确保获取完整元数据
        ydl_opts = self._get_info_extraction_config(url, cookies_str)
        
        # 尝试多种策略获取信息
        strategies = [
            # 策略1: 使用web客户端
            {'extractor_args': {'youtube': {'player_client': ['web']}}},
            # 策略2: 最小化配置
            {'extractor_args': {'youtube': {'player_client': ['web'], 'player_skip': ['dash', 'hls']}}},
            # 策略3: 基础配置
            {}
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                current_opts = ydl_opts.copy()
                if 'youtube.com' in url or 'youtu.be' in url:
                    current_opts.update(strategy)
                
                with yt_dlp.YoutubeDL(current_opts) as ydl:
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
                    
                    # 只在第一次尝试时显示调试信息
                    if i == 0:
                        print(f"[DEBUG] 视频信息提取成功 (策略{i+1}):")
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
                if i < len(strategies) - 1:
                    print(f"[INFO] 策略{i+1}失败，尝试策略{i+2}...")
                    continue
                else:
                    # 最后一次尝试也失败了
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
        """仅下载音频 - 带降级策略和文件名清理"""
        print(f"[DEBUG] download_audio_only 开始: url={url}, task_id={task_id}")
        
        # 尝试多种下载策略
        strategies = [
            # 策略1: 使用web客户端，跳过dash
            {'extractor_args': {'youtube': {'player_client': ['web'], 'player_skip': ['dash']}}},
            # 策略2: 仅使用web客户端
            {'extractor_args': {'youtube': {'player_client': ['web']}}},
            # 策略3: 基础配置
            {}
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                print(f"[DEBUG] 尝试下载策略 {i+1}")
                ydl_opts = self._get_downloader_config(url, cookies_str)
                if 'youtube.com' in url or 'youtu.be' in url:
                    ydl_opts.update(strategy)
                
                # 获取任务临时目录
                task_temp_dir = self.file_manager.get_task_temp_dir(task_id)
                print(f"[DEBUG] 任务临时目录: {task_temp_dir}")
                
                # 使用安全的文件名模板
                if not output_path:
                    output_path = os.path.join(task_temp_dir, '%(title)s.%(ext)s')
                print(f"[DEBUG] 初始输出路径模板: {output_path}")
                    
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
                    # 添加文件名清理选项
                    'restrictfilenames': True,  # 限制文件名为ASCII字符
                })
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    print(f"[DEBUG] 开始获取视频信息...")
                    # 首先获取视频信息
                    info = ydl.extract_info(url, download=False)
                    
                    # 清理标题作为文件名
                    original_title = info.get('title', 'audio_file')
                    print(f"[DEBUG] 原始标题: {original_title}")
                    safe_title = self._sanitize_filename(original_title)
                    print(f"[DEBUG] 清理后标题: {safe_title}")
                    
                    # 使用清理后的文件名重新构建路径
                    safe_output_path = os.path.join(task_temp_dir, f'{safe_title}.%(ext)s')
                    print(f"[DEBUG] 安全输出路径模板: {safe_output_path}")
                    ydl_opts['outtmpl'] = safe_output_path
                    
                    # 重新创建ydl对象并下载
                    print(f"[DEBUG] 开始下载音频...")
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                        try:
                            info_download = ydl_download.extract_info(url, download=True)
                            print(f"[DEBUG] yt-dlp下载完成")
                        except Exception as download_error:
                            print(f"[ERROR] yt-dlp下载失败: {download_error}")
                            print(f"[ERROR] 错误类型: {type(download_error)}")
                            raise download_error
                        
                        # 构建最终的音频文件路径
                        audio_filename = os.path.join(task_temp_dir, f'{safe_title}.wav')
                        print(f"[DEBUG] 预期音频文件路径: {audio_filename}")
                        
                        # 验证文件是否存在
                        if not os.path.exists(audio_filename):
                            print(f"[DEBUG] 预期文件不存在，搜索实际生成的文件...")
                            # 列出目录中的所有文件
                            try:
                                files_in_dir = os.listdir(task_temp_dir)
                                print(f"[DEBUG] 目录中的文件: {files_in_dir}")
                                
                                # 尝试查找实际生成的文件
                                for file in files_in_dir:
                                    file_path = os.path.join(task_temp_dir, file)
                                    print(f"[DEBUG] 检查文件: {file} -> {file_path}")
                                    if file.endswith('.wav') and safe_title in file:
                                        audio_filename = file_path
                                        print(f"[DEBUG] 找到匹配文件: {audio_filename}")
                                        break
                            except Exception as list_error:
                                print(f"[ERROR] 列出目录文件失败: {list_error}")
                                raise Exception(f"无法列出目录文件: {list_error}")
                        
                        print(f"[DEBUG] 最终音频文件路径: {audio_filename}")
                        if not os.path.exists(audio_filename):
                            raise Exception(f"音频文件未找到: {audio_filename}")
                    
                    # 注册文件到管理器
                    try:
                        print(f"[DEBUG] 注册文件到管理器: {audio_filename}")
                        self.file_manager.register_task(task_id, [audio_filename])
                        print(f"[DEBUG] 文件注册成功")
                    except Exception as register_error:
                        print(f"[ERROR] 文件注册失败: {register_error}")
                        # 注册失败不影响主流程，继续执行
                    
                    print(f"[INFO] 音频下载成功 (策略{i+1}): {audio_filename}")
                    return audio_filename
                    
            except Exception as e:
                error_msg = str(e)
                print(f"[ERROR] 策略{i+1}失败: {error_msg}")
                print(f"[ERROR] 错误类型: {type(e)}")
                
                # 检查是否是Errno 22错误
                if "[Errno 22]" in error_msg or "Invalid argument" in error_msg:
                    print(f"[ERROR] 发现Errno 22错误，详细信息:")
                    print(f"[ERROR] - 任务ID: {task_id}")
                    print(f"[ERROR] - URL: {url}")
                    print(f"[ERROR] - 策略: {strategy}")
                    if 'task_temp_dir' in locals():
                        print(f"[ERROR] - 临时目录: {task_temp_dir}")
                    if 'safe_title' in locals():
                        print(f"[ERROR] - 安全标题: {safe_title}")
                    if 'safe_output_path' in locals():
                        print(f"[ERROR] - 安全路径: {safe_output_path}")
                
                if i < len(strategies) - 1:
                    print(f"[INFO] 策略{i+1}失败，尝试策略{i+2}...")
                    continue
                else:
                    # 最后一次尝试也失败了
                    
                    # 检查是否是YouTube的机器人验证错误
                    if "Sign in to confirm you're not a bot" in error_msg or "Use --cookies" in error_msg:
                        raise Exception(f"YouTube 需要身份验证。请尝试以下解决方案：\n"
                                      f"1. 将 cookies.txt 文件放在项目根目录下\n"
                                      f"2. 确保已安装并登录 Chrome/Firefox 浏览器\n"
                                      f"3. 如果问题持续，请尝试其他视频链接\n"
                                      f"原始错误: {error_msg}")
                    else:
                        raise Exception(f"音频下载失败 (所有策略均失败): {error_msg}")
    
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
