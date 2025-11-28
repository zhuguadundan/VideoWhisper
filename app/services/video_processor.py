import os
import logging
import json
import uuid
import glob
import re
import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from app.models.data_models import ProcessingTask, VideoInfo, TranscriptionResult, TranscriptionSegment, UploadTask
from app.services.video_downloader import VideoDownloader
from app.services.audio_extractor import AudioExtractor
from app.services.speech_to_text import SpeechToText
from app.services.text_processor import TextProcessor
from app.services.file_uploader import FileUploader
from app.config.settings import Config
from app.utils.helpers import sanitize_filename as utils_sanitize_filename


class _TaskStore:
    """管理 VideoProcessor 的任务存储和取消标记逻辑（内部使用）。"""

    def __init__(self, owner: "VideoProcessor") -> None:
        self._owner = owner

    def request_cancel(self, task_id: str) -> None:
        with self._owner._lock:
            self._owner._cancel_flags[task_id] = True

    def cancel_all_processing(self) -> List[str]:
        affected: List[str] = []
        with self._owner._lock:
            for tid, t in self._owner.tasks.items():
                if getattr(t, "status", None) == "processing":
                    self._owner._cancel_flags[tid] = True
                    affected.append(tid)
        return affected

    def is_cancelled(self, task_id: str) -> bool:
        with self._owner._lock:
            return self._owner._cancel_flags.get(task_id, False)

    def create_task(self, video_url: str, youtube_cookies: str = None) -> str:
        """与原 VideoProcessor.create_task 行为保持一致。"""

        with self._owner._lock:
            for tid, t in self._owner.tasks.items():
                try:
                    if (
                        getattr(t, "video_url", "") == video_url
                        and getattr(t, "status", "pending")
                        in ("pending", "processing")
                    ):
                        return tid
                except Exception:
                    continue

        task_id = str(uuid.uuid4())
        task = ProcessingTask(id=task_id, video_url=video_url)
        if youtube_cookies:
            task.youtube_cookies = youtube_cookies
        with self._owner._lock:
            self._owner.tasks[task_id] = task
            self._owner.save_tasks_to_disk()
        return task_id

    def create_upload_task(
        self,
        original_filename: str,
        file_size: int,
        file_type: str,
        mime_type: str,
    ) -> str:
        """与原 VideoProcessor.create_upload_task 行为保持一致。"""

        task_id = str(uuid.uuid4())
        upload_task = UploadTask(
            id=task_id,
            video_url="",
            file_type=file_type,
            original_filename=original_filename,
            file_size=file_size,
            upload_status="pending",
            need_audio_extraction=(file_type == "video"),
        )
        with self._owner._lock:
            self._owner.tasks[task_id] = upload_task
            self._owner.save_tasks_to_disk()
        return task_id

    def get_task(self, task_id: str) -> Optional[ProcessingTask]:
        with self._owner._lock:
            return self._owner.tasks.get(task_id)


class _ProcessingPipeline:
    """预留给处理流水线逻辑的内部封装类（目前主要作为结构占位）。"""

    def __init__(self, owner: "VideoProcessor") -> None:
        self._owner = owner


class VideoProcessor:
    """视频处理核心类"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = Config.load_config()
        self._lock = threading.RLock()
        # 处理相对路径，转换为绝对路径
        output_dir = self.config['system']['output_dir']
        if not os.path.isabs(output_dir):
            # 如果是相对路径，基于项目根目录
            from app.config.settings import Config as _Cfg
            self.output_dir = _Cfg.resolve_path(output_dir)
        else:
            self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 添加临时目录配置
        temp_dir = self.config['system']['temp_dir']
        if not os.path.isabs(temp_dir):
            from app.config.settings import Config as _Cfg
            self.temp_dir = _Cfg.resolve_path(temp_dir)
        else:
            self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 初始化服务
        self.video_downloader = VideoDownloader()
        self.audio_extractor = AudioExtractor()
        self.speech_to_text = SpeechToText()
        self.text_processor = TextProcessor()
        self.file_uploader = FileUploader()

        # 处理参数（可配置，提供默认值保持兼容）
        proc_cfg = (self.config.get('processing') or {})
        self.long_audio_threshold = int(proc_cfg.get('long_audio_threshold_seconds', 300))
        self.segment_duration = int(proc_cfg.get('segment_duration_seconds', 300))
        self.max_consecutive_failures = int(proc_cfg.get('max_consecutive_failures', 3))
        self.short_audio_max_retries = int(proc_cfg.get('short_audio_max_retries', 3))
        self.retry_sleep_short = float(proc_cfg.get('retry_sleep_short_seconds', 1.0))
        self.retry_sleep_long = float(proc_cfg.get('retry_sleep_long_seconds', 2.0))
        
        # 存储处理任务
        self.tasks: Dict[str, Union[ProcessingTask, UploadTask]] = {}
        self.tasks_file = os.path.join(self.output_dir, 'tasks.json')
        # 任务取消标记存储
        self._cancel_flags: Dict[str, bool] = {}

        # 内部子组件：任务存储与处理流水线（保持对外 API 不变）
        self._task_store = _TaskStore(self)
        self._pipeline = _ProcessingPipeline(self)

        # 加载已有任务数据
        self.load_tasks_from_disk()

    def request_cancel(self, task_id: str):
        """请求取消指定任务"""
        self._task_store.request_cancel(task_id)

    def cancel_all_processing(self) -> List[str]:
        """标记所有 processing 状态任务为取消，返回受影响的任务ID列表"""
        return self._task_store.cancel_all_processing()

    def _is_cancelled(self, task_id: str) -> bool:
        return self._task_store.is_cancelled(task_id)
    
    def _sanitize_filename(self, filename: str) -> str:
        """统一文件名清洗，复用公共实现"""
        return utils_sanitize_filename(filename, default_name='video_task', max_length=100)
    
    def create_task(self, video_url: str, youtube_cookies: str = None) -> str:
        """创建新的处理任务 - 简化版"""
        # 去重：如果同一 URL 已有进行中的任务，直接复用 task_id（幂等性）
        with self._lock:
            for tid, t in self.tasks.items():
                try:
                    if getattr(t, 'video_url', '') == video_url and getattr(t, 'status', 'pending') in ('pending', 'processing'):
                        return tid
                except Exception:
                    continue

        task_id = str(uuid.uuid4())
        task = ProcessingTask(id=task_id, video_url=video_url)
        
        # 如果提供了 cookies，存储到任务中
        if youtube_cookies:
            task.youtube_cookies = youtube_cookies
        with self._lock:
            self.tasks[task_id] = task
            self.save_tasks_to_disk()
        return task_id
    
    def create_upload_task(self, original_filename: str, file_size: int, 
                         file_type: str, mime_type: str) -> str:
        """创建文件上传任务（统一由 VideoProcessor 管理）"""
        task_id = str(uuid.uuid4())
        upload_task = UploadTask(
            id=task_id,
            video_url="",
            file_type=file_type,
            original_filename=original_filename,
            file_size=file_size,
            upload_status="pending",
            need_audio_extraction=(file_type == "video")
        )

        with self._lock:
            self.tasks[task_id] = upload_task
            self.save_tasks_to_disk()
        return task_id
    
    def update_upload_progress(self, task_id: str, progress: int, 
                            status: str = "uploading", error_message: str = ""):
        """更新上传进度"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task and isinstance(task, UploadTask):
                task.upload_progress = progress
                task.upload_status = status
                if error_message:
                    task.upload_error_message = error_message
                self.save_tasks_to_disk()
    
    def complete_upload_task(self, task_id: str, file_path: str, 
                           file_duration: float = 0):
        """完成上传任务，设置文件路径"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task and isinstance(task, UploadTask):
                task.upload_status = "completed"
                task.upload_progress = 100
                task.upload_time = datetime.now()
                task.audio_file_path = file_path
                task.file_duration = file_duration
                self.save_tasks_to_disk()
    
    def fail_upload_task(self, task_id: str, error_message: str):
        """标记上传任务为失败"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task and isinstance(task, UploadTask):
                task.upload_status = "failed"
                task.upload_progress = 0
                task.upload_error_message = error_message
                self.save_tasks_to_disk()
    
    def get_task(self, task_id: str) -> Optional[ProcessingTask]:
        """获取任务"""
        with self._lock:
            return self.tasks.get(task_id)

    # -------------------------
    # 内部步骤接口（不改变对外行为）
    # -------------------------
    def _fail_if_cancelled(self, task_id: str, task: ProcessingTask) -> bool:
        """若任务已被取消则统一标记失败并持久化，返回 True"""
        if self._is_cancelled(task_id):
            task.status = "failed"
            task.error_message = "用户手动停止任务"
            self.save_tasks_to_disk()
            return True
        return False

    def _update_progress(self, task: ProcessingTask, *, progress: Optional[int] = None,
                          stage: Optional[str] = None, detail: Optional[str] = None):
        """统一更新进度并落盘"""
        if progress is not None:
            task.progress = progress
        if stage is not None:
            task.progress_stage = stage
        if detail is not None:
            task.progress_detail = detail
        self.save_tasks_to_disk()

    def _step_get_video_info(self, task_id: str, task: ProcessingTask) -> Optional[Dict[str, Any]]:
        try:
            video_info_dict = self.video_downloader.get_video_info(task.video_url, task.youtube_cookies)
        except Exception as e:
            # 友好错误：抓取失败，带原因提示
            self.logger.exception(f"[{task_id}] 获取视频信息失败: {e}")
            task.status = 'failed'
            task.error_message = '获取视频信息失败：链接不可用或站点暂不支持'
            self.save_tasks_to_disk()
            return None

        # 兼容缺失字段，提供安全默认值，避免 KeyError
        title = (video_info_dict or {}).get('title') or '未命名视频'
        url = (video_info_dict or {}).get('url') or (video_info_dict or {}).get('webpage_url') or task.video_url
        try:
            duration = float((video_info_dict or {}).get('duration') or 0)
        except Exception:
            duration = 0.0
        uploader = (video_info_dict or {}).get('uploader') or ''

        task.video_info = VideoInfo(
            title=title,
            url=url,
            duration=duration,
            uploader=uploader,
        )
        task.progress = 10
        try:
            task.estimated_time = int(duration * 0.3)
        except Exception:
            task.estimated_time = None
        return video_info_dict

    def _step_download_audio(self, task_id: str, task: ProcessingTask) -> str:
        self.logger.info(f"[{task_id}] 下载音频...")
        self._update_progress(task, stage="下载音频", detail="正在下载音频文件...")
        try:
            self.logger.debug("[DEBUG] 开始调用download_audio_only")
            audio_path = self.video_downloader.download_audio_only(task.video_url, task.id, cookies_str=task.youtube_cookies)
            self.logger.debug(f"[DEBUG] download_audio_only完成，返回路径: {audio_path}")
            task.audio_file_path = audio_path
            task.progress = 30
            return audio_path
        except Exception as download_error:
            self.logger.error(f"[ERROR] 音频下载阶段失败: {download_error}")
            self.logger.error(f"[ERROR] 错误类型: {type(download_error)}")
            raise Exception(f"音频下载失败: {download_error}")

    def _step_process_audio_and_transcribe(self, task_id: str, task: ProcessingTask, audio_path: str):
        """处理音频（获取信息、必要时分段、逐段转写或短音频直接转写），返回(full_text, all_segments, language, audio_info)"""
        if self._fail_if_cancelled(task_id, task):
            return None, None, None, None
        self.logger.info(f"[{task_id}] 处理音频...")
        self._update_progress(task, stage="处理音频", detail="分析音频文件...")
        try:
            self.logger.debug(f"[DEBUG] 开始获取音频信息: {audio_path}")
            audio_info = self.audio_extractor.get_audio_info(audio_path)
            self.logger.debug(f"[DEBUG] 音频信息: {audio_info}")
        except Exception as audio_info_error:
            self.logger.error(f"[ERROR] 获取音频信息失败: {audio_info_error}")
            self.logger.error(f"[ERROR] 错误类型: {type(audio_info_error)}")
            raise Exception(f"获取音频信息失败: {audio_info_error}")

        # 长音频分段处理
        if audio_info['duration'] > self.long_audio_threshold:
            try:
                self.logger.debug(f"[DEBUG] 音频超过阈值({self.long_audio_threshold}s)，开始分段处理")
                segments = self.audio_extractor.split_audio_by_duration(audio_path, self.segment_duration)
                self.logger.debug(f"[DEBUG] 音频分段完成，共 {len(segments)} 个片段（每段 {self.segment_duration}s）")
                task.progress = 40
                task.total_segments = len(segments)
                task.progress_detail = f"音频已分割为 {len(segments)} 个片段"
                self.save_tasks_to_disk()
            except Exception as split_error:
                self.logger.error(f"[ERROR] 音频分段失败: {split_error}")
                self.logger.error(f"[ERROR] 错误类型: {type(split_error)}")
                raise Exception(f"音频分段失败: {split_error}")

            self.logger.info(f"[{task_id}] 语音转文字...")
            task.progress_stage = "语音转文字"
            transcription_results = []
            consecutive_failures = 0
            max_consecutive_failures = self.max_consecutive_failures
            for i, segment in enumerate(segments):
                if self._fail_if_cancelled(task_id, task):
                    return None, None, None, None
                task.processed_segments = i + 1
                task.progress_detail = f"正在处理第 {i+1}/{len(segments)} 个音频片段..."
                progress_increment = (60 - 40) * (i + 1) / len(segments)
                task.progress = 40 + int(progress_increment)
                self.save_tasks_to_disk()
                try:
                    segment_result = self.speech_to_text.transcribe_audio(segment['path'])
                    text = segment_result.get('text', '').strip()
                    if not text or len(text) < 3:
                        raise Exception(f"转录文本无效: 长度={len(text)}")
                    transcription_results.append({
                        'segment_index': segment['index'],
                        'text': text,
                        'segments': segment_result.get('segments', []),
                        'start_time': segment['start_time'],
                        'end_time': segment['end_time'],
                        'language': segment_result.get('language', 'unknown')
                    })
                    self.logger.info(f"[{task_id}] 片段 {i+1} 处理成功: 文本长度={len(text)}")
                    consecutive_failures = 0
                    time.sleep(self.retry_sleep_short)
                except Exception as e:
                    consecutive_failures += 1
                    self.logger.warning(f"[{task_id}] 片段 {i+1} 处理失败: {e} (连续失败次数: {consecutive_failures})")
                    transcription_results.append({
                        'segment_index': segment['index'],
                        'text': '',
                        'segments': [],
                        'start_time': segment['start_time'],
                        'end_time': segment['end_time'],
                        'error': str(e)
                    })
                    if consecutive_failures >= max_consecutive_failures:
                        self.logger.warning(f"[{task_id}] 连续失败次数达到上限 ({max_consecutive_failures})，停止处理")
                        remaining_segments = len(segments) - (i + 1)
                        if remaining_segments > 0:
                            self.logger.info(f"[{task_id}] 跳过剩余 {remaining_segments} 个片段")
                        break
                    time.sleep(self.retry_sleep_long)

            task.progress = 60
            # 注册所有分段文件，便于统一清理
            try:
                self.file_uploader.file_manager.register_task(task_id, [s['path'] for s in segments])
            except Exception as reg_err:
                self.logger.warning(f"[{task_id}] 分段文件注册失败: {reg_err}")
            transcription_results.sort(key=lambda x: x.get('segment_index', 0))
            all_segments: List[TranscriptionSegment] = []
            full_text = ""
            successful_segments = 0
            failed_segments = 0
            processed_segments_count = len(transcription_results)
            for result in transcription_results:
                if not result.get('error'):
                    text = result.get('text', '').strip()
                    if text and len(text) >= 3:
                        successful_segments += 1
                        full_text += text + " "
                    else:
                        self.logger.warning(f"[{task_id}] 警告: 片段 {result.get('segment_index', '未知')} 返回无效文本")
                    for seg in result.get('segments', []):
                        all_segments.append(TranscriptionSegment(
                            text=seg.get('text', ''),
                            confidence=seg.get('confidence', 0.0)
                        ))
                else:
                    failed_segments += 1
                    self.logger.warning(f"[{task_id}] 片段 {result.get('segment_index', '未知')} 处理失败: {result.get('error', '未知错误')}")

            self.logger.info(f"[{task_id}] 处理统计: 成功 {successful_segments}/{processed_segments_count} 个片段, 失败 {failed_segments} 个片段")
            if processed_segments_count < len(segments):
                remaining_segments = len(segments) - processed_segments_count
                self.logger.info(f"[{task_id}] 跳过未处理片段: {remaining_segments} 个 (因连续失败而提前终止)")
            if successful_segments == 0:
                raise Exception(f"所有音频片段处理失败，共处理 {processed_segments_count} 个片段")

            # 语言
            language = 'unknown'
            for result in transcription_results:
                if not result.get('error') and result.get('language'):
                    language = result['language']
                    break
            return full_text.strip(), all_segments, language, audio_info
        else:
            # 短音频直接处理
            self._update_progress(task, stage="语音转文字", detail="处理短音频文件...")
            task.total_segments = 1
            task.processed_segments = 1
            self.save_tasks_to_disk()
            max_retries = self.short_audio_max_retries
            transcription_result = None
            for retry in range(max_retries):
                if self._fail_if_cancelled(task_id, task):
                    return None, None, None, None
                try:
                    transcription_result = self.speech_to_text.transcribe_audio(audio_path)
                    text = transcription_result.get('text', '').strip()
                    if not text or len(text) < 3:
                        if retry < max_retries - 1:
                            self.logger.warning(f"[{task_id}] 短音频返回无效文本（长度={len(text)}），第 {retry+1} 次重试...")
                            time.sleep(self.retry_sleep_long)
                            continue
                        else:
                            raise Exception(f"短音频处理重试{max_retries}次后仍返回无效文本")
                    self.logger.info(f"[{task_id}] 短音频处理成功: 文本长度={len(text)}")
                    break
                except Exception as e:
                    if retry < max_retries - 1:
                        self.logger.warning(f"[{task_id}] 短音频处理失败: {e}，第 {retry+1} 次重试...")
                        time.sleep(self.retry_sleep_long)
                    else:
                        raise Exception(f"短音频处理重试{max_retries}次后仍然失败: {e}")
            if not transcription_result or not transcription_result.get('text'):
                raise Exception("短音频处理失败：无法获取转录文本")
            full_text = transcription_result['text'].strip()
            all_segments = [TranscriptionSegment(text=full_text, confidence=0.8)]
            language = transcription_result.get('language', 'unknown')
            time.sleep(self.retry_sleep_short)
            return full_text, all_segments, language, audio_info

    def _step_generate_text_outputs(self, task: ProcessingTask, llm_provider: str):
        # 逐字稿
        if self._is_cancelled(task.id):
            task.status = "failed"
            task.error_message = "用户手动停止任务"
            self.save_tasks_to_disk()
            return
        self.logger.info(f"[{task.id}] 生成逐字稿...")
        self._update_progress(task, stage="生成逐字稿", detail="使用AI优化文本格式...")
        task.ai_start_time = time.time()
        start_time = time.time()
        task.transcript = self.text_processor.generate_transcript(task.transcription.full_text, provider=llm_provider)
        ai_response_time = time.time() - start_time
        task.ai_response_times = getattr(task, 'ai_response_times', {})
        task.ai_response_times['transcript'] = ai_response_time
        task.progress = 70
        task.progress_detail = f"逐字稿生成完成 (耗时 {ai_response_time:.1f}s)"
        self.save_tasks_to_disk()

        # 摘要
        if self._is_cancelled(task.id):
            task.status = "failed"
            task.error_message = "用户手动停止任务"
            self.save_tasks_to_disk()
            return
        self.logger.info(f"[{task.id}] 生成总结报告...")
        self._update_progress(task, stage="生成总结报告", detail=f"AI正在分析内容并生成摘要... (使用 {llm_provider})")
        start_time = time.time()
        task.summary = self.text_processor.generate_summary(task.transcript, provider=llm_provider)
        ai_response_time = time.time() - start_time
        task.ai_response_times['summary'] = ai_response_time
        task.progress = 85
        task.progress_detail = f"摘要生成完成 (耗时 {ai_response_time:.1f}s)"
        self.save_tasks_to_disk()

        # 分析
        if self._is_cancelled(task.id):
            task.status = "failed"
            task.error_message = "用户手动停止任务"
            self.save_tasks_to_disk()
            return
        self.logger.info(f"[{task.id}] 内容分析...")
        self._update_progress(task, stage="内容分析", detail=f"提取关键信息和主题... (使用 {llm_provider})")
        start_time = time.time()
        task.analysis = self.text_processor.analyze_content(task.transcript, provider=llm_provider)
        ai_response_time = time.time() - start_time
        task.ai_response_times['analysis'] = ai_response_time
        task.progress = 95
        task.progress_detail = f"内容分析完成 (耗时 {ai_response_time:.1f}s)"
        self.save_tasks_to_disk()
    
    def process_video(self, task_id: str, llm_provider: str = None, api_config: dict = None) -> ProcessingTask:
        """处理视频的完整流程"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        try:
            # 如果传入了api_config，临时设置配置
            if api_config:
                self.logger.info(f"[{task_id}] 使用前端传递的API配置")
                # 临时更新speech_to_text和text_processor的配置
                if hasattr(self.speech_to_text, 'set_runtime_config'):
                    self.speech_to_text.set_runtime_config(api_config.get('siliconflow', {}))
                if hasattr(self.text_processor, 'set_runtime_config'):
                    self.text_processor.set_runtime_config(api_config.get('text_processor', {}))
            
            # 检查文本处理器是否有可用的提供商
            available_providers = self.text_processor.get_available_providers()
            has_text_provider = bool(available_providers)
            
            # 如果指定的provider不可用，使用默认provider（仅在有文本处理提供商时）
            if has_text_provider:
                if not llm_provider or not self.text_processor.is_provider_available(llm_provider):
                    llm_provider = self.text_processor.get_default_provider()
                    self.logger.info(f"[{task_id}] 使用默认AI提供商: {llm_provider}")
                else:
                    self.logger.info(f"[{task_id}] 使用指定AI提供商: {llm_provider}")
            else:
                llm_provider = None
                self.logger.info(f"[{task_id}] 无可用AI文本处理提供商，跳过AI生成阶段")
            
            task.status = "processing"
            task.progress = 0
            task.progress_stage = "获取视频信息"
            task.progress_detail = "正在解析视频链接..."
            self.save_tasks_to_disk()  # 保存状态更新
            
            # 1. 获取视频信息
            if self._fail_if_cancelled(task_id, task):
                return task
            info = self._step_get_video_info(task_id, task)
            if info is None:
                # 已在 _step_get_video_info 中设置失败状态和错误信息
                return task

            # 2. 下载音频
            if self._fail_if_cancelled(task_id, task):
                return task
            audio_path = self._step_download_audio(task_id, task)

            # 3/4. 处理音频并转写
            if self._fail_if_cancelled(task_id, task):
                return task
            full_text, all_segments, language, audio_info = self._step_process_audio_and_transcribe(task_id, task, audio_path)
            if full_text is None:
                return task
            self.logger.info(f"[{task_id}] 合并转录结果: 文本长度={len(full_text)}, 片段数={len(all_segments)}")
            task.transcription = TranscriptionResult(
                segments=all_segments,
                full_text=full_text.strip(),
                language=language,
                duration=audio_info['duration']
            )
            task.progress = 60
            
            # 先用原始转写文本作为可预览内容，尽早给用户看到
            if not getattr(task, 'transcript', None):
                task.transcript = task.transcription.full_text
            task.transcript_ready = True
            self.save_tasks_to_disk()

            # 5-7. 文本生成/摘要/分析（若有可用的文本处理提供商）
            if has_text_provider:
                self._step_generate_text_outputs(task, llm_provider)
            else:
                # 无文本处理提供商：跳过AI润色/摘要/分析，直接使用原始转写文本
                self.logger.warning(f"[{task_id}] 没有可用的AI文本处理服务提供商，仅输出原始转写文本")
                task.progress = max(task.progress, 70)
                task.progress_stage = "生成逐字稿"
                task.progress_detail = "未配置文本处理服务，已使用原始转写文本"
                self.save_tasks_to_disk()
            
            # 8. 保存结果
            task.progress_stage = "保存结果"
            task.progress_detail = "生成输出文件..."
            self.save_tasks_to_disk()
            self._save_results(task)
            task.progress = 100
            task.status = "completed"
            task.progress_stage = "完成"
            task.progress_detail = "处理完成！"
            task.estimated_time = 0
            
            # 清理临时文件 - 智能保留最近3次任务的文件
            self._smart_cleanup_temp_files(task_id, audio_path)
            
            self.logger.info(f"[{task_id}] 处理完成!")
            
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            self.logger.error(f"[{task_id}] 处理失败: {e}")
        
        # 保存任务状态到磁盘
        self.save_tasks_to_disk()
        return task
    
    def process_upload(self, task_id: str, llm_provider: str = None, api_config: dict = None) -> ProcessingTask:
        """处理上传的文件的完整流程"""
        self.logger.info(f"[{task_id}] 开始process_upload处理")
        # 开始处理上传的文件
        
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        self.logger.debug(f"[{task_id}] 获取到任务对象: {type(task).__name__}")
        
        if not isinstance(task, UploadTask):
            raise ValueError(f"不是上传任务: {task_id}")
        
        self.logger.info(f"[{task_id}] 任务状态: status={task.status}, upload_status={task.upload_status}")
        self.logger.info(f"[{task_id}] 文件信息: audio_file_path={task.audio_file_path}, file_type={task.file_type}, need_audio_extraction={task.need_audio_extraction}")
        
        try:
            # 如果传入了api_config，临时设置配置
            if api_config:
                self.logger.info(f"[{task_id}] 使用前端传递的API配置")
                # 临时更新speech_to_text和text_processor的配置
                if hasattr(self.speech_to_text, 'set_runtime_config'):
                    self.speech_to_text.set_runtime_config(api_config.get('siliconflow', {}))
                if hasattr(self.text_processor, 'set_runtime_config'):
                    self.text_processor.set_runtime_config(api_config.get('text_processor', {}))
            
            # 检查文本处理器是否有可用的提供商
            available_providers = self.text_processor.get_available_providers()
            has_text_provider = bool(available_providers)
            
            # 如果指定的provider不可用，使用默认provider
            if has_text_provider:
                if not llm_provider or not self.text_processor.is_provider_available(llm_provider):
                    llm_provider = self.text_processor.get_default_provider()
                    self.logger.info(f"[{task_id}] 使用默认AI提供商: {llm_provider}")
                else:
                    self.logger.info(f"[{task_id}] 使用指定AI提供商: {llm_provider}")
            else:
                llm_provider = None
                self.logger.info(f"[{task_id}] 无可用AI文本处理提供商，跳过AI生成阶段")
            
            task.status = "processing"
            task.progress = 0
            task.progress_stage = "文件预处理"
            task.progress_detail = "正在分析上传的文件..."
            self.save_tasks_to_disk()
            
            # 获取文件信息
            if self._is_cancelled(task_id):
                task.status = "failed"
                task.error_message = "用户手动停止任务"
                self.save_tasks_to_disk()
                return task
            self.logger.info(f"[{task_id}] 获取文件信息...")
            file_info = self.file_uploader.get_file_info_from_path(task.audio_file_path)
            
            # 创建视频信息对象
            task.video_info = VideoInfo(
                title=task.original_filename,
                url=f"file://{task.audio_file_path}",
                duration=file_info.get('duration', 0),
                uploader="本地文件"
            )
            task.progress = 10
            task.progress_detail = f"文件大小: {file_info.get('file_size', 0) // (1024*1024)}MB"
            task.estimated_time = int(file_info.get('duration', 300) * 0.3)  # 粗略估计处理时间
            
            # 如果是视频文件，需要先提取音频
            if task.need_audio_extraction:
                if self._is_cancelled(task_id):
                    task.status = "failed"
                    task.error_message = "用户手动停止任务"
                    self.save_tasks_to_disk()
                    return task
                self.logger.info(f"[{task_id}] 提取视频音频...")
                task.progress_stage = "音频提取"
                task.progress_detail = "正在从视频中提取音频..."
                self.save_tasks_to_disk()
                
                try:
                    audio_path = self.audio_extractor.extract_audio_from_video(task.audio_file_path)
                    # 删除原始视频文件以节省空间
                    try:
                        os.remove(task.audio_file_path)
                        self.logger.info(f"[{task_id}] 已删除原始视频文件")
                    except Exception as delete_error:
                        self.logger.warning(f"[{task_id}] 删除原始视频文件失败: {delete_error}")
                    
                    task.audio_file_path = audio_path
                    # 注册提取后的音频文件到任务
                    try:
                        self.file_uploader.file_manager.register_task(task_id, [audio_path], register_dir=True)
                    except Exception as reg_err:
                        self.logger.warning(f"[{task_id}] 注册音频文件失败: {reg_err}")
                    task.progress = 25
                except Exception as extract_error:
                    raise Exception(f"音频提取失败: {extract_error}")
            else:
                # 音频文件，直接使用
                self.logger.info(f"[{task_id}] 使用音频文件...")
                task.progress = 25
                task.progress_detail = "音频文件准备就绪"
            
            # 从这里开始，复用现有的音频处理流程
            # 获取音频信息
            try:
                if self._is_cancelled(task_id):
                    task.status = "failed"
                    task.error_message = "用户手动停止任务"
                    self.save_tasks_to_disk()
                    return task
                self.logger.debug(f"[{task_id}] 开始获取音频信息: {task.audio_file_path}")
                audio_info = self.audio_extractor.get_audio_info(task.audio_file_path)
                self.logger.debug(f"[{task_id}] 音频信息: {audio_info}")
            except Exception as audio_info_error:
                self.logger.error(f"[ERROR] 获取音频信息失败: {audio_info_error}")
                self.logger.error(f"[ERROR] 错误类型: {type(audio_info_error)}")
                raise Exception(f"获取音频信息失败: {audio_info_error}")
            
            # 统一音频处理（分段或短音频）
            result = self._step_process_audio_and_transcribe(task_id, task, task.audio_file_path)
            if result is None:
                return task
            full_text, all_segments, language, audio_info = result

            # 创建转录结果对象（与 URL 流程一致）
            self.logger.info(f"[{task_id}] 合并转录结果: 文本长度={len(full_text)}, 片段数={len(all_segments)}")
            task.transcription = TranscriptionResult(
                segments=all_segments,
                full_text=full_text.strip(),
                language=language,
                duration=audio_info['duration']
            )
            task.progress = 60

            # 先将原始转写文本作为可预览内容，尽早给用户看到
            if not getattr(task, 'transcript', None):
                task.transcript = task.transcription.full_text
            task.transcript_ready = True
            self.save_tasks_to_disk()

            # 文本生成 / 摘要 / 分析（与 URL 流程一致）
            if has_text_provider:
                self._step_generate_text_outputs(task, llm_provider)
            else:
                self.logger.warning(f"[{task_id}] 没有可用的AI文本处理服务提供商，仅输出原始转写文本")
                task.progress = max(task.progress, 70)
                task.progress_stage = "生成逐字稿"
                task.progress_detail = "未配置文本处理服务，已使用原始转写文本"
                self.save_tasks_to_disk()

            # 保存结果
            task.progress_stage = "保存结果"
            task.progress_detail = "生成输出文件..."
            self.save_tasks_to_disk()
            self._save_results(task)
            task.progress = 100
            task.status = "completed"
            task.progress_stage = "完成"
            task.progress_detail = "处理完成！"
            task.estimated_time = 0

            # 清理临时文件
            self._smart_cleanup_temp_files(task_id, task.audio_file_path)
            self.logger.info(f"[{task_id}] 处理完成!")
            return task

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            self.logger.error(f"[{task_id}] 处理失败: {e}")
        
        # 保存任务状态到磁盘
        self.save_tasks_to_disk()
        return task
    
    def _save_results(self, task: ProcessingTask):
        """保存处理结果"""
        # 使用任务ID作为目录名，确保路径安全
        task_dir = os.path.join(self.output_dir, task.id)
        os.makedirs(task_dir, exist_ok=True)
        
        # 安全的文件名基础（基于清理后的标题或任务ID）
        if task.video_info and task.video_info.title:
            safe_filename_base = self._sanitize_filename(task.video_info.title)
        else:
            safe_filename_base = f"video_{task.id[:8]}"
        
        # 保存逐字稿 (改为Markdown格式)
        transcript_path = os.path.join(task_dir, f'transcript_{safe_filename_base}.md')
        try:
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(f"# {task.video_info.title if task.video_info else '视频逐字稿'}\n\n")
                url_line = task.video_info.url if task.video_info and getattr(task.video_info, 'url', '') else getattr(task, 'video_url', '')
                f.write(f"**视频URL:** {url_line}\n\n")
                if task.video_info:
                    if task.video_info.uploader:
                        f.write(f"**UP主:** {task.video_info.uploader}\n")
                    if task.video_info.duration:
                        duration = self._format_duration(task.video_info.duration)
                        f.write(f"**时长:** {duration}\n")
                f.write(f"**处理时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                f.write(task.transcript)
        except Exception as e:
            self.logger.warning(f"保存逐字稿失败: {e}")
            # 使用基础文件名重试
            transcript_path = os.path.join(task_dir, 'transcript.md')
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(f"# 视频逐字稿\n\n")
                url_line = task.video_info.url if task.video_info and getattr(task.video_info, 'url', '') else getattr(task, 'video_url', '')
                f.write(f"**视频URL:** {url_line}\n\n")
                f.write(f"**处理时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                f.write(task.transcript)
        
        # 保存总结报告
        summary_path = os.path.join(task_dir, f'summary_{safe_filename_base}.md')
        try:
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(f"# {task.video_info.title if task.video_info else '视频总结报告'}\n\n")
                url_line = task.video_info.url if task.video_info and getattr(task.video_info, 'url', '') else getattr(task, 'video_url', '')
                f.write(f"**视频URL:** {url_line}\n")
                if task.video_info:
                    f.write(f"**上传者:** {task.video_info.uploader}\n")
                    f.write(f"**时长:** {self._format_duration(task.video_info.duration)}\n")
                f.write(f"**处理时间:** {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                if task.summary.get('brief_summary'):
                    f.write("## 简要摘要\n\n")
                    f.write(task.summary['brief_summary'] + "\n\n")
                
                if task.summary.get('detailed_summary'):
                    f.write(task.summary['detailed_summary'] + "\n\n")
                
                if task.summary.get('keywords'):
                    f.write("## 关键词\n\n")
                    f.write(task.summary['keywords'] + "\n\n")
        except Exception as e:
            self.logger.warning(f"保存总结报告失败: {e}")
            # 使用基础文件名重试
            summary_path = os.path.join(task_dir, 'summary.md')
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(f"# 视频总结报告\n\n")
                url_line = task.video_info.url if task.video_info and getattr(task.video_info, 'url', '') else getattr(task, 'video_url', '')
                f.write(f"**视频URL:** {url_line}\n")
                f.write(f"**处理时间:** {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                if task.summary.get('brief_summary'):
                    f.write("## 简要摘要\n\n")
                    f.write(task.summary['brief_summary'] + "\n\n")
        
        # 保存完整数据（JSON格式）
        data_path = os.path.join(task_dir, f'data_{safe_filename_base}.json')
        try:
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"保存JSON数据失败: {e}")
            # 使用基础文件名重试
            data_path = os.path.join(task_dir, 'data.json')
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _format_duration(self, seconds: float) -> str:
        """格式化时长显示"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def get_task_progress(self, task_id: str) -> Dict[str, Any]:
        """获取任务进度"""
        task = self.get_task(task_id)
        if not task:
            return {"error": "任务不存在"}
        
        progress_info = {
            "id": task.id,
            "status": task.status,
            "progress": task.progress,
            "progress_stage": task.progress_stage,
            "progress_detail": task.progress_detail,
            "estimated_time": task.estimated_time,
            "processed_segments": task.processed_segments,
            "total_segments": task.total_segments,
            "video_title": task.video_info.title if task.video_info else "",
            "video_uploader": task.video_info.uploader if task.video_info else "",
            "video_duration": task.video_info.duration if task.video_info else 0,
            "error_message": task.error_message,
            "ai_response_times": getattr(task, 'ai_response_times', {}),
            "transcript_ready": getattr(task, 'transcript_ready', False),
            "translation_status": getattr(task, 'translation_status', ''),
            "translation_ready": getattr(task, 'translation_ready', False)
        }
        
        # 返回逐字稿/预览：优先返回 task.transcript；若无则降级为原始转写文本
        if task.transcript and task.transcript.strip():
            progress_info["transcript_preview"] = task.transcript[:500] + "..." if len(task.transcript) > 500 else task.transcript
            progress_info["full_transcript"] = task.transcript
            progress_info["transcript_ready"] = True
        elif task.transcription and getattr(task.transcription, 'full_text', '').strip():
            raw_text = task.transcription.full_text.strip()
            progress_info["transcript_preview"] = raw_text[:500] + "..." if len(raw_text) > 500 else raw_text
            progress_info["full_transcript"] = raw_text
            # 即便后端未设置，也在进度响应中标记可预览
            progress_info["transcript_ready"] = True
        
        return progress_info

    def translate_transcript(self, task_id: str, llm_provider: Optional[str] = None, api_config: Optional[dict] = None):
        """将英文逐字稿翻译为中英对照，并生成文件。"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if api_config and hasattr(self.text_processor, 'set_runtime_config'):
            self.text_processor.set_runtime_config(api_config.get('text_processor', {}))

        if not task.transcript or not task.transcript.strip():
            raise ValueError("任务尚未生成逐字稿，无法翻译")

        task.translation_status = 'processing'
        task.translation_ready = False
        self.save_tasks_to_disk()

        try:
            provider = llm_provider or self.text_processor.get_default_provider()
            bilingual = self.text_processor.generate_bilingual_transcript(task.transcript, provider=provider)
            self._save_bilingual_transcript(task, bilingual)
            task.translation_status = 'completed'
            task.translation_ready = True
        except Exception as e:
            task.translation_status = 'failed'
            task.translation_ready = False
            task.error_message = f"翻译失败: {e}"
            raise
        finally:
            self.save_tasks_to_disk()

    def _save_bilingual_transcript(self, task: ProcessingTask, content: str):
        task_dir = os.path.join(self.output_dir, task.id)
        os.makedirs(task_dir, exist_ok=True)
        if task.video_info and task.video_info.title:
            safe_base = self._sanitize_filename(task.video_info.title)
        else:
            safe_base = f"video_{task.id[:8]}"
        out_path = os.path.join(task_dir, f"transcript_bilingual_{safe_base}.md")
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                # 只写正文，不写任何标题，避免模型/文件头部混入额外说明
                f.write(content.strip() + "\n")
        except Exception as e:
            self.logger.warning(f"保存对照逐字稿失败: {e}")
    
    def load_tasks_from_disk(self):
        """从磁盘加载任务数据"""
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)
                with self._lock:
                    # 过滤掉未完成的任务（只加载已完成或失败的任务）
                    completed_tasks = []
                    for task_data in tasks_data:
                        # 将未完成的任务标记为失败
                        if task_data.get('status') == 'processing':
                            task_data['status'] = 'failed'
                            task_data['error_message'] = '程序重启导致任务中断'
                            task_data['progress'] = 0
                        
                        # 判断任务类型（向后兼容：无type但带上传字段则视为上传任务）
                        is_upload = (task_data.get('type') == 'upload') or (
                            'upload_status' in task_data or 'original_filename' in task_data
                        )
                        common_kwargs = dict(
                            id=task_data['id'],
                            video_url=task_data.get('video_url', ''),
                            status=task_data.get('status', 'failed'),
                            created_at=datetime.fromisoformat(task_data['created_at']),
                            transcript=task_data.get('transcript', ''),
                            summary=task_data.get('summary', {}),
                            analysis=task_data.get('analysis', {}),
                            error_message=task_data.get('error_message', ''),
                            progress=task_data.get('progress', 0)
                        )
                        if is_upload:
                            task = UploadTask(
                                **common_kwargs,
                                file_type=task_data.get('file_type', 'audio'),
                                original_filename=task_data.get('original_filename', ''),
                                file_size=task_data.get('file_size', 0),
                                file_duration=task_data.get('file_duration', 0.0),
                                upload_time=datetime.fromisoformat(task_data['upload_time']) if task_data.get('upload_time') else None,
                                need_audio_extraction=task_data.get('need_audio_extraction', False),
                                upload_progress=task_data.get('upload_progress', 0),
                                upload_status=task_data.get('upload_status', ''),
                                upload_error_message=task_data.get('upload_error_message', '')
                            )
                            task.audio_file_path = task_data.get('audio_file_path')
                        else:
                            task = ProcessingTask(**common_kwargs)
                            task.audio_file_path = task_data.get('audio_file_path')
                        
                        # 恢复视频信息
                        if task_data.get('video_info'):
                            vi = task_data['video_info'] or {}
                            task.video_info = VideoInfo(
                                title=vi.get('title', ''),
                                url=vi.get('url', task_data.get('video_url', '')),
                                duration=vi.get('duration', 0),
                                uploader=vi.get('uploader', '')
                            )
                        
                        self.tasks[task.id] = task
                        completed_tasks.append(task_data)
                
                # 发现清理则原子覆盖写回
                if len(completed_tasks) != len(tasks_data):
                    self._atomic_write_tasks(completed_tasks)
                    self.logger.info(f"已清理未完成任务，加载 {len(self.tasks)} 个历史任务")
                else:
                    self.logger.info(f"已加载 {len(self.tasks)} 个历史任务")
        except Exception as e:
            self.logger.error(f"加载任务数据失败: {e}")
    
    def save_tasks_to_disk(self):
        """保存任务数据到磁盘"""
        try:
            with self._lock:
                tasks_data = [task.to_dict() for task in self.tasks.values()]
            self._atomic_write_tasks(tasks_data)
        except Exception as e:
            self.logger.error(f"保存任务数据失败: {e}")

    def _atomic_write_tasks(self, tasks_data: List[Dict[str, Any]]):
        """原子方式写入 tasks.json，避免并发/中断导致文件损坏"""
        directory = os.path.dirname(self.tasks_file) or '.'
        os.makedirs(directory, exist_ok=True)
        tmp_path = self.tasks_file + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(tasks_data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.tasks_file)
    
    def _smart_cleanup_temp_files(self, current_task_id: str, current_audio_path: str):
        """智能清理临时文件：委托 FileManager 递归清理超出保留限制的任务目录"""
        try:
            self.file_uploader.file_manager.cleanup_excess_tasks()
            self.logger.info(f"[{current_task_id}] 已触发历史任务清理（按最近{self.file_uploader.file_manager.max_temp_tasks}个保留）")
        except Exception as e:
            self.logger.warning(f"[{current_task_id}] 临时文件清理失败: {e}")
    
    def _is_file_related_to_task(self, file_name: str, task_id: str) -> bool:
        """判断文件是否与特定任务相关"""
        try:
            # 1. 检查文件名中是否包含任务ID
            if task_id in file_name:
                return True
            
            # 2. 检查是否是该任务的视频标题相关文件
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.video_info and task.video_info.title:
                    # 清理文件名中的特殊字符进行比较
                    clean_title = re.sub(r'[^\w\s-]', '', task.video_info.title).strip()
                    clean_filename = re.sub(r'[^\w\s-]', '', file_name).strip()
                    
                    # 检查标题是否在文件名中
                    if clean_title and clean_title in clean_filename:
                        return True
                    
                    # 检查文件名是否在标题中
                    if clean_filename and clean_filename in clean_title:
                        return True
            
            # 3. 检查是否是分段音频文件（包含 segment 关键字）
            if 'segment' in file_name.lower():
                # 尝试从分段文件名中提取原始文件名
                base_name = file_name
                if '_segment_' in file_name:
                    base_name = file_name.split('_segment_')[0]
                elif 'segment' in file_name:
                    base_name = re.sub(r'_?segment_?\d+', '', file_name)
                
                # 递归检查基础文件名是否与任务相关
                return self._is_file_related_to_task(base_name, task_id)
            
            return False
            
        except Exception as e:
            self.logger.warning(f"检查文件关联性失败 {file_name} <-> {task_id}: {e}")
            return False
    
    def _format_timestamp(self, seconds: float) -> str:
        """格式化时间戳为可读格式"""
        if not seconds or seconds <= 0:
            return "00:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
