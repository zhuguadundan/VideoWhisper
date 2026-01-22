from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime


@dataclass
class VideoInfo:
    """视频信息"""

    title: str
    url: str
    duration: float
    uploader: str = ""
    description: str = ""


@dataclass
class AudioSegment:
    """音频片段"""

    path: str
    index: int


@dataclass
class TranscriptionSegment:
    """转录片段"""

    text: str
    confidence: float = 0.0


@dataclass
class TranscriptionResult:
    """转录结果"""

    segments: List[TranscriptionSegment]
    full_text: str
    language: str
    duration: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segments": [
                {
                    "text": seg.text,
                    "confidence": seg.confidence,
                }
                for seg in self.segments
            ],
            "full_text": self.full_text,
            "language": self.language,
            "duration": self.duration,
        }


@dataclass
class ProcessingTask:
    """处理任务 - 基础任务类，支持URL和文件上传"""

    id: str
    video_url: str = ""  # 可以为空，如果是文件上传任务
    status: str = "pending"  # pending, processing, completed, failed
    created_at: datetime = field(default_factory=datetime.now)
    # 音频文件路径
    audio_file_path: Optional[str] = None
    # 视频下载产物路径（如仅下载视频，不进入转写流程）
    video_file_path: Optional[str] = None
    # Site cookies（可选）
    youtube_cookies: Optional[str] = None
    bilibili_cookies: Optional[str] = None
    # 原有字段
    video_info: Optional[VideoInfo] = None
    transcription: Optional[TranscriptionResult] = None
    transcript: str = ""
    summary: Dict[str, str] = field(default_factory=dict)
    analysis: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    progress: int = 0
    progress_stage: str = "准备中"  # 当前处理阶段
    progress_detail: str = ""  # 详细进度信息
    estimated_time: Optional[int] = None  # 预估剩余时间(秒)
    processed_segments: int = 0  # 已处理的音频段数
    total_segments: int = 0  # 总音频段数
    # 翻译（对照稿）相关
    translation_status: str = ""  # '', processing, completed, failed
    translation_ready: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "processing",
            "id": self.id,
            "video_url": self.video_url,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "audio_file_path": self.audio_file_path,
            "video_file_path": self.video_file_path,
            "youtube_cookies": None,
            "bilibili_cookies": None,
            "video_info": {
                "title": self.video_info.title if self.video_info else "",
                "url": self.video_info.url if self.video_info else "",
                "duration": self.video_info.duration if self.video_info else 0,
                "uploader": self.video_info.uploader if self.video_info else "",
                "description": self.video_info.description if self.video_info else "",
            }
            if self.video_info
            else None,
            "transcript": self.transcript,
            "summary": self.summary,
            "analysis": self.analysis,
            "error_message": self.error_message,
            "progress": self.progress,
            "progress_stage": self.progress_stage,
            "progress_detail": self.progress_detail,
            "estimated_time": self.estimated_time,
            "processed_segments": self.processed_segments,
            "total_segments": self.total_segments,
        }


@dataclass
class UploadTask(ProcessingTask):
    """文件上传任务 - 继承自 ProcessingTask"""

    file_type: Literal["video", "audio"] = "audio"
    original_filename: str = ""
    file_size: int = 0
    file_duration: float = 0.0
    upload_time: Optional[datetime] = None
    need_audio_extraction: bool = False
    upload_progress: int = 0
    upload_status: str = "pending"  # pending, uploading, completed, failed
    upload_error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["type"] = "upload"
        data.update(
            {
                "file_type": self.file_type,
                "original_filename": self.original_filename,
                "file_size": self.file_size,
                "file_duration": self.file_duration,
                "upload_time": self.upload_time.isoformat()
                if self.upload_time
                else None,
                "need_audio_extraction": self.need_audio_extraction,
                "upload_progress": self.upload_progress,
                "upload_status": self.upload_status,
                "upload_error_message": self.upload_error_message,
            }
        )
        return data
