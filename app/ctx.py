"""应用级单例上下文，集中服务对象，避免跨蓝图循环依赖。
后续蓝图拆分可从此处引入统一实例。
"""

from app.services.video_processor import VideoProcessor
from app.services.video_downloader import VideoDownloader
from app.services.file_uploader import FileUploader

# 全局单例
video_processor = VideoProcessor()
video_downloader = VideoDownloader()
file_uploader = FileUploader()

