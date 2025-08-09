from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

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
    start_time: float
    end_time: float
    index: int

@dataclass
class TranscriptionSegment:
    """转录片段"""
    text: str
    start_time: float
    end_time: float
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
            'segments': [
                {
                    'text': seg.text,
                    'start_time': seg.start_time,
                    'end_time': seg.end_time,
                    'confidence': seg.confidence
                } for seg in self.segments
            ],
            'full_text': self.full_text,
            'language': self.language,
            'duration': self.duration
        }

@dataclass
class ProcessingTask:
    """处理任务 - 简化版，仅支持音频处理"""
    id: str
    video_url: str
    status: str = "pending"  # pending, processing, completed, failed
    created_at: datetime = field(default_factory=datetime.now)
    # 音频文件路径
    audio_file_path: Optional[str] = None  # 音频文件路径
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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'video_url': self.video_url,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'audio_file_path': self.audio_file_path,
            'video_info': {
                'title': self.video_info.title if self.video_info else '',
                'duration': self.video_info.duration if self.video_info else 0,
                'uploader': self.video_info.uploader if self.video_info else '',
                'description': self.video_info.description if self.video_info else ''
            } if self.video_info else None,
            'transcript': self.transcript,
            'summary': self.summary,
            'analysis': self.analysis,
            'error_message': self.error_message,
            'progress': self.progress,
            'progress_stage': self.progress_stage,
            'progress_detail': self.progress_detail,
            'estimated_time': self.estimated_time,
            'processed_segments': self.processed_segments,
            'total_segments': self.total_segments
        }