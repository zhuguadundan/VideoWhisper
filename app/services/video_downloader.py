import yt_dlp
import os
import asyncio
import shutil
import re
from typing import Dict, Any, Optional
from app.config.settings import Config
from app.services.file_manager import FileManager
from app.utils.helpers import sanitize_filename as utils_sanitize_filename
import logging

logger = logging.getLogger(__name__)

class VideoDownloader:
    """简化的视频下载器 - 仅支持音频下载"""
    
    def __init__(self):
        self.config = Config.load_config()
        # 使用项目根锚定路径，确保不同工作目录一致
        self.temp_dir = Config.resolve_path(self.config['system']['temp_dir'])
        self.file_manager = FileManager()
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def _sanitize_filename(self, filename: str) -> str:
        """统一文件名清洗，复用公共实现"""
        return utils_sanitize_filename(filename, default_name='audio_file', max_length=100)
    
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
        
        logger.warning("未找到FFmpeg，请确保已安装并添加到系统PATH")
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
            # 记录临时cookie文件，调用方完成后负责清理
            base_opts['_temp_cookiefile'] = cookies_file.name
        else:
            # 检查是否有cookies.txt文件
            cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
            if os.path.exists(cookies_path):
                base_opts['cookiefile'] = cookies_path
                logger.debug(f"信息提取使用cookies文件: {cookies_path}")
            else:
                # *** 禁用浏览器cookies导入以避免权限问题 ***
                logger.debug("信息提取跳过浏览器cookie导入")
        
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
                # 记录临时cookie文件，调用方完成后负责清理
                base_opts['_temp_cookiefile'] = cookies_file.name
            else:
                # 尝试从 cookies 文件加载
                cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
                if os.path.exists(cookies_path):
                    base_opts['cookiefile'] = cookies_path
                    logger.debug(f"使用cookies文件: {cookies_path}")
                else:
                    # *** 禁用浏览器cookies导入以避免权限问题 ***
                    logger.debug("跳过浏览器cookie导入，避免权限问题")
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
            logger.error(f"解析cookies失败: {e}")
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
                        logger.debug(f"视频信息提取成功 (策略{i+1}):")
                        logger.debug(f"  - channel: {info.get('channel', 'None')}")
                        logger.debug(f"  - uploader: {info.get('uploader', 'None')}")
                        logger.debug(f"  - uploader_id: {info.get('uploader_id', 'None')}")
                        logger.debug(f"  - creator: {info.get('creator', 'None')}")
                        logger.debug(f"  - 最终选择: {uploader}")
                    
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
                    logger.info(f"策略{i+1}失败，尝试策略{i+2}...")
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
            finally:
                # 清理临时 cookies 文件（若有）
                try:
                    temp_cookie = current_opts.get('_temp_cookiefile') if 'current_opts' in locals() else None
                    if temp_cookie and os.path.exists(temp_cookie):
                        os.remove(temp_cookie)
                except Exception:
                    pass
    
    def download_audio_only(self, url: str, task_id: str, output_path: Optional[str] = None, cookies_str: str = None) -> str:
        """仅下载音频 - 带降级策略和文件名清理
        注意：若调用方提供了 output_path，则尊重调用方路径（Never break userspace）。
        返回实际生成的 .wav 文件的绝对路径。
        """
        logger.debug(f"download_audio_only 开始: url={url}, task_id={task_id}")
        
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
                logger.debug(f"尝试下载策略 {i+1}")
                ydl_opts = self._get_downloader_config(url, cookies_str)
                if 'youtube.com' in url or 'youtu.be' in url:
                    ydl_opts.update(strategy)
                
                # 获取任务临时目录
                task_temp_dir = self.file_manager.get_task_temp_dir(task_id)
                logger.debug(f"任务临时目录: {task_temp_dir}")
                
                # 使用调用方提供的输出模板；若未提供则基于 title 生成模板
                if output_path:
                    # 若是相对路径，锚定到任务目录
                    if not os.path.isabs(output_path):
                        output_path = os.path.join(task_temp_dir, output_path)
                else:
                    output_path = os.path.join(task_temp_dir, '%(title)s.%(ext)s')
                logger.debug(f"初始输出路径模板: {output_path}")
                    
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
                    logger.debug("开始获取视频信息...")
                    # 先探测信息
                    info = ydl.extract_info(url, download=False)

                # 基于标题生成安全文件名（用于默认 outtmpl 和最终名称推断）
                original_title = info.get('title', 'audio_file')
                logger.debug(f"原始标题: {original_title}")
                safe_title = self._sanitize_filename(original_title)
                logger.debug(f"清理后标题: {safe_title}")

                # 若调用方未指定 outtmpl 文件名部分，确保文件名安全
                outtmpl = ydl_opts.get('outtmpl', output_path)
                if '%(title)s' in outtmpl:
                    # 改为安全标题模板（避免 restrictfilenames 与自定义清洗产生不一致）
                    outtmpl = outtmpl.replace('%(title)s', safe_title)
                ydl_opts['outtmpl'] = outtmpl

                logger.debug("开始下载音频...")
                # 执行下载并获取实际结果
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                    try:
                        info_download = ydl_download.extract_info(url, download=True)
                        logger.debug("yt-dlp下载完成")
                    except Exception as download_error:
                        logger.error(f"yt-dlp下载失败: {download_error}")
                        logger.error(f"错误类型: {type(download_error)}")
                        raise download_error

                # 推断最终生成的 wav 文件路径
                # 1) yt-dlp 音频提取 postprocessor 通常把扩展名改为 .wav
                # 2) 当 outtmpl 为 .../<name>.%(ext)s 时，最终为 .../<name>.wav
                # 因此直接在模板位置替换 %(ext)s 为 wav
                final_path = outtmpl
                final_path = final_path.replace('%(ext)s', 'wav') if '%(ext)s' in final_path else final_path
                # 若 outtmpl 没有 %(ext)s，但不是 .wav，尝试替换结尾扩展名
                if not final_path.lower().endswith('.wav'):
                    root, _ = os.path.splitext(final_path)
                    final_path = f"{root}.wav"

                # 如果文件不存在，做一次目录扫描兜底（只要 .wav 且包含 safe_title）
                audio_filename = final_path
                if not os.path.exists(audio_filename):
                    logger.debug("按推断路径未找到文件，进行目录兜底扫描...")
                    try:
                        for file in os.listdir(task_temp_dir):
                            if file.lower().endswith('.wav') and safe_title in file:
                                audio_filename = os.path.join(task_temp_dir, file)
                                break
                    except Exception as list_error:
                        logger.error(f"列出目录文件失败: {list_error}")
                        raise Exception(f"无法列出目录文件: {list_error}")

                logger.debug(f"最终音频文件路径: {audio_filename}")
                if not os.path.exists(audio_filename):
                    raise Exception(f"音频文件未找到: {audio_filename}")

                # 成功路径：注册并返回
                try:
                    logger.debug(f"注册文件到管理器: {audio_filename}")
                    self.file_manager.register_task(task_id, [audio_filename], register_dir=True)
                    logger.debug("文件注册成功")
                except Exception as register_error:
                    logger.error(f"文件注册失败: {register_error}")
                    # 注册失败不影响主流程

                logger.info(f"音频下载成功 (策略{i+1}): {audio_filename}")
                return audio_filename
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"策略{i+1}失败: {error_msg}")
                logger.error(f"错误类型: {type(e)}")
                
                # 检查是否是Errno 22错误
                if "[Errno 22]" in error_msg or "Invalid argument" in error_msg:
                    logger.error("发现Errno 22错误，详细信息:")
                    logger.error(f"- 任务ID: {task_id}")
                    logger.error(f"- URL: {url}")
                    logger.error(f"- 策略: {strategy}")
                    if 'task_temp_dir' in locals():
                        logger.error(f"- 临时目录: {task_temp_dir}")
                    if 'safe_title' in locals():
                        logger.error(f"- 安全标题: {safe_title}")
                    if 'safe_output_path' in locals():
                        logger.error(f"- 安全路径: {safe_output_path}")
                
                if i < len(strategies) - 1:
                    logger.info(f"策略{i+1}失败，尝试策略{i+2}...")
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
            finally:
                # 清理临时 cookies 文件（若有）
                try:
                    temp_cookie = ydl_opts.get('_temp_cookiefile') if 'ydl_opts' in locals() else None
                    if temp_cookie and os.path.exists(temp_cookie):
                        os.remove(temp_cookie)
                except Exception:
                    pass
    
    def cleanup_temp_files(self):
        """清理临时文件（兼容保留）
        为避免误删，已改为委托 FileManager 的历史任务清理逻辑，
        按“仅保留最近N次任务”的策略递归删除旧任务目录。
        """
        try:
            self.file_manager.cleanup_excess_tasks()
            logger.info("已触发历史任务清理（按配置的保留数量）")
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")

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
