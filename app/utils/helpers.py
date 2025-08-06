import os
import shutil
from typing import Optional

def ensure_directory_exists(directory: str):
    """确保目录存在"""
    if not os.path.exists(directory):
        os.makedirs(directory)

def clean_directory(directory: str, keep_files: Optional[list] = None):
    """清理目录中的文件"""
    if not os.path.exists(directory):
        return
    
    keep_files = keep_files or []
    
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if filename not in keep_files:
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"清理文件失败 {file_path}: {e}")

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def is_valid_url(url: str) -> bool:
    """检查URL是否有效"""
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return url_pattern.match(url) is not None

def sanitize_filename(filename: str) -> str:
    """清理文件名，移除特殊字符"""
    import re
    # 移除或替换特殊字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 限制长度
    if len(filename) > 200:
        filename = filename[:200]
    return filename.strip()

def get_video_platform(url: str) -> str:
    """识别视频平台"""
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'YouTube'
    elif 'bilibili.com' in url:
        return 'Bilibili'
    elif 'douyin.com' in url or 'tiktok.com' in url:
        return 'TikTok/抖音'
    else:
        return '其他平台'