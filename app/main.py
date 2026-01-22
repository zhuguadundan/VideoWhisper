from flask import Blueprint, render_template, request, jsonify, send_file, current_app
import threading
import os
import shutil
import glob
from datetime import datetime
from app.services.video_processor import VideoProcessor
from app.services.video_downloader import VideoDownloader
from app.services.speech_to_text import SpeechToText
from app.services.text_processor import TextProcessor
from app.services.file_uploader import FileUploader
from app.models.data_models import UploadTask
from app.utils.error_handler import api_error_handler, safe_json_response
from app.utils.auth import admin_protected
from app.utils.provider_tester import (
    test_siliconflow as _pt_test_siliconflow,
    test_openai_compatible as _pt_test_openai,
    test_gemini as _pt_test_gemini,
)
import logging
import ipaddress
from urllib.parse import urlparse
from app.config.settings import Config
from app.utils.api_guard import (
    is_safe_base_url,
    validate_runtime_api_config,
    get_security_policy,
)
from app.utils.path_safety import safe_join
from app.services.file_manager import FileManager

# 统一由 app.utils.api_guard 提供策略与校验

try:
    import openai
except ImportError:
    openai = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

main_bp = Blueprint("main", __name__)
video_processor = VideoProcessor()
video_downloader = VideoDownloader()
file_uploader = FileUploader()


@main_bp.route("/")
def index():
    """主页"""
    return render_template("index.html")


@main_bp.route("/settings")
def settings():
    """设置页面"""
    return render_template("settings.html")


# 静默处理 Chrome DevTools 探测请求，避免404噪音日志
@main_bp.route("/.well-known/appspecific/com.chrome.devtools.json", methods=["GET"])
def chrome_devtools_probe():
    # 返回204以表明无内容，此请求与业务无关
    return ("", 204)


@main_bp.route("/api/health", methods=["GET"])
def health_check():
    """健康检查端点"""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": f"v{os.environ.get('APP_VERSION', '0.0.0')}",
            "features": [
                "audio_only_download",
                "automatic_temp_cleanup",
                "docker_optimized",
                "youtube_cookies_support",
            ],
        }
    )


@main_bp.route("/api/providers", methods=["GET"])
@api_error_handler
def get_available_providers():
    """获取可用的AI服务提供商"""
    providers = video_processor.text_processor.get_available_providers()
    default_provider = (
        video_processor.text_processor.get_default_provider() if providers else None
    )

    return safe_json_response(
        success=True, data={"providers": providers, "default": default_provider}
    )


@main_bp.route("/api/video-info", methods=["POST"])
@api_error_handler
def get_video_info():
    """获取视频基本信息（仅用于显示）"""
    # 使用 silent 模式避免 Flask 在 Content-Type 非 JSON 时抛出 415，统一转为参数错误
    data = request.get_json(silent=True) or {}
    if not data:
        raise ValueError("请求数据不能为空")

    video_url = data.get("video_url", "").strip()
    if not video_url:
        raise ValueError("请提供视频URL")

    # SSRF 防护：处理前先校验视频URL
    allowed_hosts, allow_http, allow_private, enforce_whitelist = get_security_policy()
    if not is_safe_base_url(
        video_url,
        allowed_hosts=allowed_hosts,
        allow_http=allow_http,
        allow_private=allow_private,
        enforce_whitelist=enforce_whitelist,
    ):
        # 不安全 URL 作为参数错误交给统一错误处理，返回 400
        raise ValueError("不安全的视频URL，必须为HTTPS且非内网/本地地址")

    info = video_downloader.get_video_info(video_url)
    return safe_json_response(success=True, data=info, message="视频信息获取成功")


@main_bp.route("/api/upload", methods=["POST"])
@api_error_handler
def upload_file():
    """文件上传端点"""
    try:
        # 检查是否有文件
        if "file" not in request.files:
            return safe_json_response(success=False, error="请选择要上传的文件")

        file = request.files["file"]
        # Werkzeug FileStorage.filename may be None
        if not file.filename:
            return safe_json_response(success=False, error="请选择要上传的文件")

        # 获取文件信息
        # After the guard above, filename is present.
        original_filename = str(file.filename)

        # 计算文件大小和读取内容
        file.stream.seek(0, 2)  # 移动到文件末尾
        file_size = file.stream.tell()
        file.stream.seek(0)  # 回到文件开头

        # 获取MIME类型
        mime_type = file.mimetype or "application/octet-stream"

        logging.info(
            f"文件上传请求: filename={original_filename}, size={file_size}, mime_type={mime_type}"
        )

        # 验证文件
        try:
            file_info = file_uploader._get_file_info(original_filename, file_size)
            is_valid, message = file_uploader._validate_file(
                original_filename, file_size, mime_type
            )
            if not is_valid:
                return safe_json_response(success=False, error=message)
        except Exception as e:
            return safe_json_response(success=False, error=f"文件验证失败: {str(e)}")

        # 创建上传任务
        try:
            task_id = video_processor.create_upload_task(
                original_filename=original_filename,
                file_size=file_size,
                file_type=file_info["file_type"],
                mime_type=mime_type,
            )
        except Exception as e:
            return safe_json_response(
                success=False, error=f"创建上传任务失败: {str(e)}"
            )

        # 保存文件
        try:
            upload_result = file_uploader.save_uploaded_file(
                file_obj=file, original_filename=original_filename, file_size=file_size
            )

            if not upload_result["success"]:
                # 标记任务为失败
                video_processor.fail_upload_task(task_id, upload_result["error"])
                return safe_json_response(success=False, error=upload_result["error"])

            # 完成上传任务
            video_processor.complete_upload_task(
                task_id=task_id,
                file_path=upload_result["file_path"],
                file_duration=upload_result.get("file_duration", 0),
            )

            return safe_json_response(
                success=True,
                data={
                    "task_id": task_id,
                    "file_info": {
                        "original_filename": original_filename,
                        "file_size": file_size,
                        "file_type": file_info["file_type"],
                        "mime_type": mime_type,
                        "need_audio_extraction": file_info["need_audio_extraction"],
                    },
                },
                message="文件上传成功",
            )

        except Exception as e:
            # 标记任务为失败
            video_processor.fail_upload_task(task_id, str(e))
            return safe_json_response(success=False, error=f"文件上传失败: {str(e)}")

    except Exception as e:
        logging.error(f"文件上传端点异常: {str(e)}")
        return safe_json_response(success=False, error=f"服务器错误: {str(e)}")


@main_bp.route("/api/upload/<task_id>/progress", methods=["GET"])
@api_error_handler
def get_upload_progress(task_id):
    """获取上传进度"""
    try:
        task = video_processor.get_task(task_id)
        if not task:
            return safe_json_response(success=False, error="任务不存在")

        if not isinstance(task, UploadTask):
            return safe_json_response(success=False, error="不是上传任务")

        return safe_json_response(
            success=True,
            data={
                "task_id": task_id,
                "upload_progress": task.upload_progress,
                "upload_status": task.upload_status,
                "upload_error_message": task.upload_error_message,
                "file_size": task.file_size,
                "file_type": task.file_type,
                "original_filename": task.original_filename,
            },
        )

    except Exception as e:
        logging.error(f"获取上传进度异常: {str(e)}")
        return safe_json_response(success=False, error=f"服务器错误: {str(e)}")


@main_bp.route("/api/process-upload", methods=["POST"])
@api_error_handler
def process_upload():
    """处理上传的文件"""
    data = request.get_json()
    if not data:
        raise ValueError("请求数据不能为空")

    task_id = data.get("task_id", "").strip()
    if not task_id:
        raise ValueError("请提供任务ID")

    llm_provider = data.get("llm_provider", "openai")
    api_config = data.get("api_config", {})
    # 校验运行时配置中的 base_url，沿用与测试接口一致的安全策略
    try:
        if api_config:
            validate_runtime_api_config(api_config)
    except Exception as e:
        raise ValueError(str(e))

    logging.info(f"process_upload请求: task_id={task_id}, llm_provider={llm_provider}")

    # 获取任务
    task = video_processor.get_task(task_id)
    if not task:
        logging.error(f"任务不存在: {task_id}")
        raise ValueError("任务不存在")

    logging.info(
        f"获取到任务: id={task.id}, type={type(task)}, upload_status={getattr(task, 'upload_status', None)}"
    )

    if not isinstance(task, UploadTask):
        logging.error(f"不是上传任务: task_id={task_id}, task_type={type(task)}")
        raise ValueError("不是上传任务")

    try:
        upload_status = task.upload_status
        logging.info(f"任务上传状态: {upload_status}")
    except AttributeError as e:
        logging.error(f"UploadTask缺少upload_status属性: task_id={task_id}, error={e}")
        logging.error(f"UploadTask对象内容: {vars(task)}")
        raise ValueError(f"任务状态不完整，upload_status属性缺失: {e}")

    if upload_status != "completed":
        logging.error(
            f"文件上传未完成: task_id={task_id}, upload_status={upload_status}"
        )
        raise ValueError("文件上传未完成，请等待上传完成后再处理")

    logging.info(
        f"开始处理上传文件任务: {task_id}, 文件: {task.original_filename}, audio_file_path={task.audio_file_path}"
    )

    # 创建处理函数
    def safe_process_upload():
        try:
            logging.info(f"启动处理上传文件线程: {task_id}")
            video_processor.process_upload(task_id, llm_provider, api_config)
            logging.info(f"上传文件任务 {task_id} 处理完成")
        except Exception as e:
            logging.exception(f"上传文件处理线程异常 [{task_id}]: {e}")
            # 确保任务状态被正确更新
            task = video_processor.get_task(task_id)
            if task:
                task.status = "failed"
                task.error_message = f"处理异常: {str(e)}"
                video_processor.save_tasks_to_disk()

    # 在后台线程中处理文件
    thread = threading.Thread(target=safe_process_upload)
    thread.daemon = True
    thread.start()
    logging.info(f"已启动处理线程: {task_id}")

    return safe_json_response(
        success=True, data={"task_id": task_id}, message="任务已创建，开始处理..."
    )


@main_bp.route("/api/upload/config", methods=["GET"])
@api_error_handler
def get_upload_config():
    """获取上传配置信息"""
    try:
        config = file_uploader.get_upload_config()
        return safe_json_response(success=True, data=config, message="获取上传配置成功")
    except Exception as e:
        logging.error(f"获取上传配置异常: {str(e)}")
        return safe_json_response(success=False, error=f"获取上传配置失败: {str(e)}")


@main_bp.route("/api/process", methods=["POST"])
@api_error_handler
def process_video():
    """处理视频请求 - 简化版，仅音频下载"""
    # 使用 silent 模式统一处理缺少/错误的 JSON 请求体
    data = request.get_json(silent=True) or {}
    if not data:
        raise ValueError("请求数据不能为空")

    video_url = data.get("video_url", "").strip()
    if not video_url:
        raise ValueError("请提供视频URL")

    llm_provider = data.get("llm_provider", "openai")
    api_config = data.get("api_config", {})
    # 校验运行时配置中的 base_url，沿用与测试接口一致的安全策略
    try:
        if api_config:
            validate_runtime_api_config(api_config)
    except Exception as e:
        raise ValueError(str(e))
    youtube_cookies = data.get("youtube_cookies", "")  # 获取 YouTube cookies

    # SSRF 防护：处理前先校验视频URL
    allowed_hosts, allow_http, allow_private, enforce_whitelist = get_security_policy()
    if not is_safe_base_url(
        video_url,
        allowed_hosts=allowed_hosts,
        allow_http=allow_http,
        allow_private=allow_private,
        enforce_whitelist=enforce_whitelist,
    ):
        # 不安全 URL 作为参数错误交给统一错误处理
        raise ValueError("不安全的视频URL，必须为HTTPS且非内网/本地地址")

    # 创建任务（支持 cookies 参数）
    task_id = video_processor.create_task(video_url, youtube_cookies)
    logging.info(f"创建新任务: {task_id}, URL: {video_url} (仅音频模式)")
    if youtube_cookies:
        logging.info(f"任务 {task_id} 使用了 YouTube cookies")

    # 创建带异常处理的处理函数
    def safe_process_video():
        try:
            video_processor.process_video(task_id, llm_provider, api_config)
            logging.info(f"任务 {task_id} 处理完成")
        except Exception as e:
            # 确保任务状态被正确更新
            task = video_processor.get_task(task_id)
            if task:
                task.status = "failed"
                task.error_message = f"处理异常: {str(e)}"
                video_processor.save_tasks_to_disk()
            logging.exception(f"视频处理线程异常 [{task_id}]: {e}")

    # 在后台线程中处理视频
    thread = threading.Thread(target=safe_process_video)
    thread.daemon = True
    thread.start()

    return safe_json_response(
        success=True, data={"task_id": task_id}, message="任务已创建，开始处理..."
    )


@main_bp.route("/api/progress/<task_id>")
@api_error_handler
def get_progress(task_id):
    """获取处理进度"""
    progress = video_processor.get_task_progress(task_id)
    try:
        # 仅在调试级别记录详细进度，避免生产环境日志过多
        logging.debug(
            f"progress[{task_id}]: status={progress.get('status')} "
            f"stage={progress.get('progress_stage')} detail={progress.get('progress_detail')}"
        )
    except Exception:
        pass
    if "error" in progress:
        return safe_json_response(success=False, error=progress["error"])

    return safe_json_response(success=True, data=progress)


@main_bp.route("/api/translate", methods=["POST"])
@api_error_handler
def translate_bilingual():
    """生成中英对照逐字稿（句对句：上中文、下英文）"""
    data = request.get_json()
    if not data:
        raise ValueError("请求数据不能为空")

    task_id = data.get("task_id", "").strip()
    if not task_id:
        raise ValueError("请提供任务ID")

    llm_provider = data.get("llm_provider")
    api_config = data.get("api_config", {})

    def safe_translate():
        try:
            video_processor.translate_transcript(task_id, llm_provider, api_config)
            logging.info(f"翻译完成（中英对照）: {task_id}")
        except Exception as e:
            logging.exception(f"翻译线程异常 [{task_id}]: {e}")

    t = threading.Thread(target=safe_translate, daemon=True)
    t.start()
    return safe_json_response(
        success=True, data={"task_id": task_id}, message="已开始生成中英对照逐字稿"
    )


@main_bp.route("/api/result/<task_id>")
@api_error_handler
def get_result(task_id):
    """获取处理结果"""
    task = video_processor.get_task(task_id)
    if not task:
        raise ValueError("任务不存在")

    if task.status != "completed":
        raise ValueError(f"任务未完成，当前状态: {task.status}")

    # 如果已生成对照逐字稿，优先返回对照版用于前端展示/导入
    transcript_text = task.transcript
    try:
        if getattr(task, "translation_ready", False):
            # 读取对照版文件内容作为展示
            task_dir = os.path.join(video_processor.output_dir, task_id)
            bilingual_files = glob.glob(
                os.path.join(task_dir, "transcript_bilingual_*.md")
            )
            if bilingual_files:
                with open(bilingual_files[0], "r", encoding="utf-8") as f:
                    transcript_text = f.read()
    except Exception:
        pass

    result_data = {
        "video_info": {
            "title": task.video_info.title if task.video_info else "",
            "uploader": task.video_info.uploader if task.video_info else "",
            "duration": task.video_info.duration if task.video_info else 0,
            "url": task.video_url,
        },
        "transcript": transcript_text,
        "summary": task.summary,
        "analysis": task.analysis,
    }

    return safe_json_response(success=True, data=result_data)


@main_bp.route("/api/download/<task_id>/<file_type>")
def download_file(task_id, file_type):
    """下载结果文件（transcript/summary/analysis 等）"""
    try:
        task = video_processor.get_task(task_id)
        if not task or task.status != "completed":
            return jsonify({"success": False, "message": "任务不存在或未完成"}), 200

        if file_type not in ("transcript", "summary", "analysis", "data"):
            return jsonify({"success": False, "message": "不支持的文件类型"}), 200

        task_dir = os.path.join(video_processor.output_dir, task_id)
        if not os.path.exists(task_dir):
            return jsonify({"success": False, "message": "任务目录不存在"}), 200

        # transcript：优先 bilingual
        if file_type == "transcript":
            bilingual_files = glob.glob(
                os.path.join(task_dir, "transcript_bilingual_*.md")
            )
            if bilingual_files:
                return send_file(bilingual_files[0], as_attachment=True)
            transcript_files = glob.glob(os.path.join(task_dir, "transcript_*.md"))
            if transcript_files:
                return send_file(transcript_files[0], as_attachment=True)
            return jsonify({"success": False, "message": "未找到逐字稿文件"}), 200

        # summary/analysis/data
        pattern_map = {
            "summary": "summary_*.md",
            "analysis": "analysis_*.md",
            "data": "data_*.json",
        }
        files = glob.glob(os.path.join(task_dir, pattern_map[file_type]))
        if not files:
            return jsonify({"success": False, "message": "未找到文件"}), 200
        return send_file(files[0], as_attachment=True)

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 200


@main_bp.route("/api/downloads/formats", methods=["POST"])
@api_error_handler
def get_download_formats():
    """Probe yt-dlp formats and return aggregated quality tiers (height upper-bound).

    This endpoint MUST be metadata-only and MUST NOT download any media.

    Payload:
      {"url": "https://...", "youtube_cookies": "...", "bilibili_cookies": "..."}

    Response:
      { success: true, data: { qualities: [{height,label,format,exts}], default_format } }
    """

    import re

    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        raise ValueError("缺少 url")

    youtube_cookies = (data.get("youtube_cookies") or "").strip() or None
    bilibili_cookies = (data.get("bilibili_cookies") or "").strip() or None

    # SSRF/安全校验：复用现有 guard
    allowed_hosts, allow_http, allow_private, enforce_whitelist = get_security_policy()
    if not is_safe_base_url(
        url,
        allowed_hosts=allowed_hosts,
        allow_http=allow_http,
        allow_private=allow_private,
        enforce_whitelist=enforce_whitelist,
    ):
        raise ValueError("URL 不安全或不允许访问")

    # Choose site cookies based on URL
    cookies_str = youtube_cookies
    cookies_domain = ".youtube.com"
    url_l = url.lower()
    if "bilibili.com" in url_l or "b23.tv" in url_l:
        cookies_str = bilibili_cookies or cookies_str
        cookies_domain = ".bilibili.com"

    info = video_downloader.get_video_info(
        url,
        cookies_str=cookies_str,
        cookies_domain=cookies_domain,
        include_formats=True,
    )

    formats = (info or {}).get("formats") or []

    # Aggregate by height (quality tiers)
    heights = set()
    exts_by_height = {}
    for f in formats:
        try:
            h = f.get("height")
            if not isinstance(h, int) or h <= 0:
                note = (f.get("format_note") or "").strip()
                m = re.search(r"(\d{3,4})p", note)
                if m:
                    h = int(m.group(1))
                else:
                    continue

            heights.add(h)
            ext = f.get("ext")
            if ext:
                exts_by_height.setdefault(h, set()).add(str(ext))
        except Exception:
            continue

    def _label(h: int) -> str:
        if h >= 2160:
            return f"{h}p (4K)"
        if h >= 1440:
            return f"{h}p (2K)"
        return f"{h}p"

    qualities = []
    for h in sorted(heights, reverse=True):
        # Upper-bound selector: <=h, prefer separate video+audio, fallback to single best
        fmt = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
        qualities.append(
            {
                "height": h,
                "label": _label(h),
                "format": fmt,
                "exts": sorted(list(exts_by_height.get(h, set()))),
            }
        )

    return safe_json_response(
        success=True,
        data={
            "qualities": qualities,
            "default_format": "bestvideo+bestaudio/best",
        },
        message="清晰度获取成功",
    )


@main_bp.route("/api/downloads/<task_id>/file")
def download_video_file(task_id: str):
    """下载视频文件（下载任务产物）

    Note: must work under both HTTP and HTTPS entrances.
    We return a relative-path response (no absolute URLs) and stream the file.
    """
    task = video_processor.get_task(task_id)
    file_path = getattr(task, "video_file_path", None) if task else None
    if not task or task.status != "completed" or not file_path:
        return jsonify({"success": False, "message": "任务不存在或未完成"}), 404

    # Enforce file stays within output/<task_id>/
    from app.utils.path_safety import safe_join

    task_dir = os.path.join(video_processor.output_dir, task_id)
    try:
        # Use basename to avoid client-controlled subpaths
        candidate = safe_join(task_dir, os.path.basename(file_path))
    except ValueError:
        return jsonify({"success": False, "message": "非法文件路径"}), 400

    if not os.path.exists(candidate):
        return jsonify({"success": False, "message": "文件不存在"}), 404

    download_name = os.path.basename(candidate)

    # Support HTTP Range requests for resumable downloads (works for both HTTP/HTTPS)
    # Example: Range: bytes=0-1023
    range_header = request.headers.get("Range")
    if not range_header:
        resp = send_file(candidate, as_attachment=True, download_name=download_name)
        try:
            resp.headers["Accept-Ranges"] = "bytes"
        except Exception:
            pass
        return resp

    try:
        import re

        m = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if not m:
            resp = send_file(candidate, as_attachment=True, download_name=download_name)
            resp.headers["Accept-Ranges"] = "bytes"
            return resp

        size = os.path.getsize(candidate)
        start_s, end_s = m.group(1), m.group(2)
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else size - 1

        # Validate/normalize range
        if start < 0:
            start = 0
        if end >= size:
            end = size - 1
        if start > end or start >= size:
            return (
                "",
                416,
                {
                    "Content-Range": f"bytes */{size}",
                    "Accept-Ranges": "bytes",
                },
            )

        length = end - start + 1

        def _iter_file(
            path: str, offset: int, count: int, chunk_size: int = 1024 * 1024
        ):
            with open(path, "rb") as f:
                f.seek(offset)
                remaining = count
                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        from flask import Response

        import mimetypes

        mime, _ = mimetypes.guess_type(candidate)
        if not mime:
            mime = "application/octet-stream"

        resp = Response(
            _iter_file(candidate, start, length),
            status=206,
            mimetype=mime,
            direct_passthrough=True,
        )
        resp.headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Content-Length"] = str(length)
        resp.headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
        return resp

    except Exception:
        # Fallback: if parsing/streaming fails, still allow full download
        resp = send_file(candidate, as_attachment=True, download_name=download_name)
        try:
            resp.headers["Accept-Ranges"] = "bytes"
        except Exception:
            pass
        return resp


@main_bp.route("/api/downloads", methods=["POST"])
@api_error_handler
def create_download_task():
    """创建下载任务（下载视频到 output/，允许按清晰度上限选择格式）"""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        raise ValueError("缺少 url")

    youtube_cookies = (data.get("youtube_cookies") or "").strip() or None
    bilibili_cookies = (data.get("bilibili_cookies") or "").strip() or None
    download_format = (data.get("format") or "").strip() or None

    allowed_hosts, allow_http, allow_private, enforce_whitelist = get_security_policy()
    if not is_safe_base_url(
        url,
        allowed_hosts=allowed_hosts,
        allow_http=allow_http,
        allow_private=allow_private,
        enforce_whitelist=enforce_whitelist,
    ):
        raise ValueError("URL 不安全或不允许访问")

    task_id = video_processor.create_task(
        url,
        youtube_cookies=youtube_cookies,
        bilibili_cookies=bilibili_cookies,
    )

    try:
        task = video_processor.get_task(task_id)
        if task and download_format:
            setattr(task, "download_format", download_format)
            video_processor.save_tasks_to_disk()
    except Exception:
        pass

    t = threading.Thread(
        target=video_processor.download_video_only,
        args=(task_id,),
        daemon=True,
    )
    t.start()

    return safe_json_response(
        success=True, data={"task_id": task_id, "status": "pending"}
    )


@main_bp.route("/api/downloads/test-cookies", methods=["POST"])
def test_download_cookies():
    """Test site cookies by probing yt-dlp formats.

    This endpoint accepts cookies from frontend and performs a metadata-only probe.
    It MUST respect SSRF/security policy and MUST NOT log cookies.

    Safeguards:
    - Small concurrency limit
    - Hard timeout

    Payload:
      {
        "site": "bilibili",
        "url": "https://www.bilibili.com/video/BV...",
        "cookies": "SESSDATA=...; bili_jct=...; ..."
      }

    Returns:
      {
        success: bool,
        data: {
          site: str,
          ok: bool,
          premium_access: bool,
          reason: str,
          formats_hint: {...}
        }
      }
    """

    import threading

    if not hasattr(test_download_cookies, "_sema"):
        # allow only one probe at a time
        test_download_cookies._sema = threading.BoundedSemaphore(1)  # type: ignore[attr-defined]

    def _redact_sensitive(obj):
        """Best-effort redaction for logs/errors.

        This is intentionally conservative and only used for server-side logging.
        """
        try:
            if isinstance(obj, dict):
                out = {}
                for k, v in obj.items():
                    lk = str(k).lower()
                    if lk in (
                        "cookies",
                        "cookie",
                        "authorization",
                        "api_key",
                        "apikey",
                        "token",
                    ):
                        out[k] = "***"
                    else:
                        out[k] = _redact_sensitive(v)
                return out
            if isinstance(obj, list):
                return [_redact_sensitive(x) for x in obj]
            return obj
        except Exception:
            return "***"

    # Concurrency + timeout guard
    if not test_download_cookies._sema.acquire(timeout=1):  # type: ignore[attr-defined]
        return jsonify(
            {"success": False, "message": "测试请求过于频繁，请稍后重试"}
        ), 429

    site = "bilibili"
    url = ""

    try:
        data = request.get_json(silent=True) or {}
        site = (data.get("site") or "").strip().lower()
        url = (data.get("url") or "").strip()
        cookies = (data.get("cookies") or "").strip()

        if site not in ("bilibili",):
            return jsonify({"success": False, "message": "unsupported site"}), 400
        if not url:
            return jsonify({"success": False, "message": "missing url"}), 400
        if not cookies:
            return jsonify({"success": False, "message": "missing cookies"}), 400

        # SSRF/安全校验：仅允许 Bilibili 域名（开源自部署默认更安全）
        import urllib.parse
        import ipaddress

        try:
            parsed = urllib.parse.urlparse(url)
        except Exception:
            return jsonify({"success": False, "message": "URL 不合法"}), 400

        if parsed.scheme not in ("http", "https"):
            return jsonify({"success": False, "message": "仅支持 http/https"}), 400

        host = (parsed.hostname or "").lower()
        if not host:
            return jsonify({"success": False, "message": "URL 缺少主机名"}), 400

        # Block direct IPs
        try:
            ipaddress.ip_address(host)
            return jsonify({"success": False, "message": "不允许使用 IP 地址"}), 400
        except Exception:
            pass

        allowed_suffixes = ("bilibili.com", "b23.tv")
        if not any(host == s or host.endswith("." + s) for s in allowed_suffixes):
            return jsonify(
                {"success": False, "message": "仅允许 Bilibili 域名用于测试"}
            ), 400

        # Hard timeout for probe
        import concurrent.futures

        def _probe():
            cookies_domain = ".bilibili.com"
            info = video_processor.video_downloader.get_video_info(
                url, cookies_str=cookies, cookies_domain=cookies_domain
            )
            formats = info.get("formats") or []

            def _is_premium_fmt(f: dict) -> bool:
                fid = str(f.get("format_id") or "")
                note = str(f.get("format_note") or "")
                fps = f.get("fps")
                height = f.get("height")
                proto = str(f.get("protocol") or "")
                if proto == "mhtml":
                    return False
                if "1080" in note and ("60" in note or (fps and fps >= 50)):
                    return True
                if (
                    (height and height >= 1440)
                    or "4k" in note.lower()
                    or "hdr" in note.lower()
                ):
                    return True
                if "dolby" in note.lower() or "hires" in note.lower():
                    return True
                if fid and ("1080" in fid and ("60" in fid or "hdr" in fid.lower())):
                    return True
                return False

            premium = any(_is_premium_fmt(f) for f in formats)
            has_1080p60 = any(
                (
                    "1080" in str(f.get("format_note") or "")
                    and (
                        "60" in str(f.get("format_note") or "")
                        or (f.get("fps") and f.get("fps") >= 50)
                    )
                )
                for f in formats
            )

            return {
                "premium": bool(premium),
                "format_count": len(formats),
                "has_1080p60": bool(has_1080p60),
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_probe)
            try:
                result = fut.result(timeout=20)
            except concurrent.futures.TimeoutError:
                return jsonify(
                    {
                        "success": True,
                        "data": {
                            "site": site,
                            "ok": False,
                            "premium_access": False,
                            "reason": "测试超时（可能触发风控/限流或网络不稳定），请稍后重试",
                        },
                    }
                )

        return jsonify(
            {
                "success": True,
                "data": {
                    "site": site,
                    "ok": True,
                    "premium_access": bool(result["premium"]),
                    "reason": "ok"
                    if result["premium"]
                    else "cookies accepted but no premium formats detected (may not be VIP or video has no premium variants)",
                    "formats_hint": {
                        "format_count": result["format_count"],
                        "has_1080p60": result["has_1080p60"],
                    },
                },
            }
        )

    except Exception as e:
        # Do not leak cookies in logs or response.
        try:
            current_app.logger.warning(
                "[test-cookies] probe failed: %s",
                _redact_sensitive({"site": site, "url": url, "error": str(e)}),
            )
        except Exception:
            pass

        return jsonify(
            {
                "success": True,
                "data": {
                    "site": site,
                    "ok": False,
                    "premium_access": False,
                    "reason": "验证失败，请检查 cookies 是否有效，或稍后重试（可能触发风控/限流）",
                },
            }
        )

    finally:
        try:
            test_download_cookies._sema.release()  # type: ignore[attr-defined]
        except Exception:
            pass


@main_bp.route("/api/tasks")
def list_tasks():
    """获取所有任务列表"""
    try:
        tasks_data = []
        for task_id, task in video_processor.tasks.items():
            tasks_data.append(
                {
                    "id": task.id,
                    "video_url": task.video_url,
                    "status": task.status,
                    "progress": task.progress,
                    "title": task.video_info.title if task.video_info else "",
                    "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "error_message": task.error_message,
                }
            )

        # 按创建时间倒序排列
        tasks_data.sort(key=lambda x: x["created_at"], reverse=True)

        return jsonify({"success": True, "data": tasks_data})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@main_bp.route("/files")
def files_management():
    """文件管理页面"""
    return render_template("files.html")


@main_bp.route("/api/files")
def list_files():
    """获取所有文件列表"""
    try:
        files_data = []

        # 扫描输出目录
        output_dir = video_processor.output_dir
        temp_dir = video_processor.temp_dir

        if os.path.exists(output_dir):
            for task_id in os.listdir(output_dir):
                task_path = os.path.join(output_dir, task_id)
                if os.path.isdir(task_path):
                    # 获取任务信息
                    task = video_processor.get_task(task_id)
                    task_title = (
                        task.video_info.title
                        if task and task.video_info
                        else task_id[:8]
                    )

                    # 扫描任务目录下的所有文件
                    for file_name in os.listdir(task_path):
                        file_path = os.path.join(task_path, file_name)
                        if os.path.isfile(file_path):
                            file_stats = os.stat(file_path)
                            file_size = file_stats.st_size
                            modified_time = datetime.fromtimestamp(file_stats.st_mtime)

                            # 确定文件类型和描述
                            file_type, description, download_type = get_file_info(
                                file_name
                            )

                            files_data.append(
                                {
                                    "id": f"{task_id}/{file_name}",
                                    "task_id": task_id,
                                    "file_name": file_name,
                                    "file_type": file_type,
                                    "description": description,
                                    "download_type": download_type,
                                    "task_title": task_title,
                                    "size": file_size,
                                    "size_human": format_file_size(file_size),
                                    "modified_time": modified_time.strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                    # 避免暴露服务器绝对路径
                                    "file_path": f"{task_id}/{file_name}",
                                }
                            )

        # 扫描临时目录的视频和音频文件
        if os.path.exists(temp_dir):
            for file_name in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file_name)
                if os.path.isfile(file_path):
                    file_stats = os.stat(file_path)
                    file_size = file_stats.st_size
                    modified_time = datetime.fromtimestamp(file_stats.st_mtime)

                    file_type, description, download_type = get_file_info(file_name)

                    files_data.append(
                        {
                            "id": f"temp/{file_name}",
                            "task_id": "temp",
                            "file_name": file_name,
                            "file_type": file_type,
                            "description": description,
                            "download_type": download_type,
                            "task_title": "临时文件",
                            "size": file_size,
                            "size_human": format_file_size(file_size),
                            "modified_time": modified_time.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "file_path": f"temp/{file_name}",
                        }
                    )

        # 按修改时间倒序排列
        files_data.sort(key=lambda x: x["modified_time"], reverse=True)

        return jsonify({"success": True, "data": files_data})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@main_bp.route("/api/files/download/<path:file_id>")
def download_managed_file(file_id):
    """下载指定文件"""
    try:
        # 解析文件ID
        if "/" not in file_id:
            return jsonify({"success": False, "message": "无效的文件ID"})

        parts = file_id.split("/")
        if len(parts) < 2:
            return jsonify({"success": False, "message": "无效的文件ID格式"})

        task_id = parts[0]
        file_name = "/".join(parts[1:])

        # 构造文件路径（统一路径安全校验）
        base_dir = (
            video_processor.temp_dir
            if task_id == "temp"
            else os.path.join(video_processor.output_dir, task_id)
        )
        try:
            candidate = safe_join(base_dir, file_name)
        except ValueError:
            return jsonify({"success": False, "message": "非法的文件路径"}), 400

        if not os.path.exists(candidate):
            return jsonify({"success": False, "message": "文件不存在"})

        return send_file(
            candidate, as_attachment=True, download_name=os.path.basename(file_name)
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@main_bp.route("/api/files/delete", methods=["POST"])
@admin_protected
def delete_files():
    """删除指定文件"""
    try:
        data = request.get_json()
        logging.info(f"Delete request received with data: {data}")
        file_ids = data.get("file_ids", [])

        if not file_ids:
            logging.warning("No file_ids provided in delete request")
            return jsonify({"success": False, "message": "未指定要删除的文件"})

        deleted_count = 0
        errors = []

        for file_id in file_ids:
            try:
                logging.info(f"Processing delete for file_id: {file_id}")
                # 解析文件ID
                if "/" not in file_id:
                    errors.append(f"{file_id}: 无效的文件ID")
                    continue

                parts = file_id.split("/")
                if len(parts) < 2:
                    errors.append(f"{file_id}: 无效的文件ID格式")
                    continue

                task_id = parts[0]
                file_name = "/".join(parts[1:])

                # 统一路径安全校验
                base_dir = (
                    video_processor.temp_dir
                    if task_id == "temp"
                    else os.path.join(video_processor.output_dir, task_id)
                )
                try:
                    file_path = safe_join(base_dir, file_name)
                except ValueError as _e:
                    errors.append(f"{file_id}: 非法的文件路径")
                    logging.warning(f"Illegal path exception: {_e}")
                    continue

                logging.info(f"Attempting to delete file: {file_path}")

                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
                    logging.info(f"Successfully deleted: {file_path}")
                else:
                    errors.append(f"{file_name}: 文件不存在")
                    logging.warning(f"File not found: {file_path}")

            except Exception as e:
                errors.append(f"{file_id}: {str(e)}")
                logging.error(f"Error deleting file {file_id}: {str(e)}")

        result = {
            "success": True,
            "message": f"成功删除 {deleted_count} 个文件",
            "deleted_count": deleted_count,
            "errors": errors,
        }

        logging.info(f"Delete operation completed: {result}")
        return jsonify(result)

    except Exception as e:
        logging.error(f"Delete operation failed: {str(e)}")
        return jsonify({"success": False, "message": str(e)})


@main_bp.route("/api/files/delete-task/<task_id>", methods=["POST"])
@admin_protected
def delete_task_files(task_id):
    """删除整个任务的所有文件"""
    try:
        if task_id == "temp":
            # 清空临时目录
            temp_dir = video_processor.temp_dir
            if os.path.exists(temp_dir):
                for file_name in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file_name)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                return jsonify({"success": True, "message": "临时文件已清空"})
            else:
                return jsonify({"success": False, "message": "临时目录不存在"})
        else:
            # 使用 FileManager 的带护栏删除
            fm = FileManager()
            ok = fm.delete_output_task_dir(task_id)
            if ok:
                # 同步内存任务
                if task_id in video_processor.tasks:
                    del video_processor.tasks[task_id]
                    try:
                        video_processor.save_tasks_to_disk()
                    except Exception:
                        pass
                return jsonify(
                    {"success": True, "message": f"任务 {task_id} 的所有文件已删除"}
                )
            return jsonify({"success": False, "message": "任务目录不存在"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


def get_file_info(file_name):
    """获取文件类型信息"""
    file_name_lower = file_name.lower()

    if file_name_lower.endswith(".txt"):
        if "transcript" in file_name_lower:
            if "timestamp" in file_name_lower:
                return "transcript", "带时间戳的逐字稿", "transcript"
            else:
                return "transcript", "逐字稿", "transcript"
        else:
            return "text", "文本文件", "text"
    elif file_name_lower.endswith(".md"):
        return "summary", "总结报告", "summary"
    elif file_name_lower.endswith(".json"):
        return "data", "数据文件", "data"
    elif file_name_lower.endswith((".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv")):
        return "video", "视频文件", "video"
    elif file_name_lower.endswith((".mp3", ".wav", ".aac", ".m4a", ".ogg")):
        return "audio", "音频文件", "audio"
    elif file_name_lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp")):
        return "image", "图片文件", "image"
    else:
        return "other", "其他文件", "other"


def format_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes == 0:
        return "0B"

    import math

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


@main_bp.route("/api/test-connection", methods=["POST"])
@api_error_handler
@admin_protected
def test_api_connection():
    """测试API连接"""
    data = request.get_json()
    if not data:
        raise ValueError("请求数据不能为空")

    provider = data.get("provider")
    config = data.get("config", {})

    logging.info(
        f"测试API连接 - 提供商: {provider}, 配置keys: {list(config.keys()) if config else 'None'}"
    )

    if not provider:
        raise ValueError("未指定服务提供商")

    if provider == "siliconflow":
        return test_siliconflow_connection(config)
    elif provider == "text_processor":
        return test_text_processor_connection(config)
    elif provider == "openai":
        return test_openai_connection(config)
    elif provider == "gemini":
        return test_gemini_connection(config)
    else:
        raise ValueError(f"不支持的服务提供商: {provider}")


def test_siliconflow_connection(config):
    """测试硅基流动API连接"""
    if not config.get("api_key"):
        raise ValueError("API Key未提供")

    base_url = config.get("base_url") or "https://api.siliconflow.cn/v1"
    allowed_hosts, allow_http, allow_private, enforce_whitelist = get_security_policy()
    if not is_safe_base_url(
        base_url,
        allowed_hosts=allowed_hosts,
        allow_http=allow_http,
        allow_private=allow_private,
        enforce_whitelist=enforce_whitelist,
    ):
        raise ValueError("不安全的Base URL，必须为HTTPS且非内网/本地地址")
    ok, msg = _pt_test_siliconflow(config["api_key"], base_url, config.get("model"))
    if ok:
        return safe_json_response(success=True, message=msg)
    raise ConnectionError(msg)


def test_text_processor_connection(config):
    """测试文本处理器连接"""
    actual_provider = config.get("actual_provider")
    logging.info(f"测试文本处理器连接 - actual_provider: {actual_provider}")

    if actual_provider == "siliconflow":
        return test_siliconflow_text_processor(config)
    elif actual_provider == "custom":
        return test_openai_connection(config, is_text_processor=True)
    elif actual_provider == "openai":
        return test_openai_connection(config, is_text_processor=True)
    elif actual_provider == "gemini":
        return test_gemini_connection(config, is_text_processor=True)
    else:
        raise ValueError(f"不支持的文本处理提供商: {actual_provider}")


def test_siliconflow_text_processor(config):
    """测试硅基流动作为文本处理器"""
    if not config.get("api_key"):
        raise ValueError("API Key未提供")

    base_url = config.get("base_url") or "https://api.siliconflow.cn/v1"
    allowed_hosts, allow_http, allow_private, enforce_whitelist = get_security_policy()
    if not is_safe_base_url(
        base_url,
        allowed_hosts=allowed_hosts,
        allow_http=allow_http,
        allow_private=allow_private,
        enforce_whitelist=enforce_whitelist,
    ):
        raise ValueError("不安全的Base URL，必须为HTTPS且非内网/本地地址")
    ok, msg = _pt_test_siliconflow(
        config["api_key"],
        base_url,
        config.get("model", "Qwen/Qwen3-Coder-30B-A3B-Instruct"),
    )
    if ok:
        return safe_json_response(
            success=True,
            message=f"硅基流动文本处理API连接成功，模型: {config.get('model', 'Qwen/Qwen3-Coder-30B-A3B-Instruct')}",
        )
    raise ConnectionError(msg)


def test_openai_connection(config, is_text_processor=False):
    """测试OpenAI连接（包括自定义兼容OpenAI的API），使用模型列表，不消耗token"""
    if not openai:
        raise ImportError("OpenAI库未安装，请先安装: pip install openai")

    if not config.get("api_key"):
        raise ValueError("API Key未提供")

    # 对于自定义提供商，Base URL是必需的
    if is_text_processor and config.get("actual_provider") == "custom":
        if not config.get("base_url"):
            raise ValueError("自定义提供商需要提供Base URL")

    try:
        allowed_hosts, allow_http, allow_private, enforce_whitelist = (
            get_security_policy()
        )
        if config.get("base_url") and not is_safe_base_url(
            config.get("base_url"),
            allowed_hosts=allowed_hosts,
            allow_http=allow_http,
            allow_private=allow_private,
            enforce_whitelist=enforce_whitelist,
        ):
            raise ValueError("不安全的Base URL，必须为HTTPS且非内网/本地地址")
        ok, _ = _pt_test_openai(
            config.get("api_key"), config.get("base_url"), config.get("model")
        )
        if not ok:
            raise ConnectionError("模型列表为空，请检查API密钥或Base URL")
        # 根据是否为自定义提供商显示不同的成功消息
        if is_text_processor and config.get("actual_provider") == "custom":
            service_type = "自定义文本处理"
            model_info = config.get("model", "未知")
        else:
            service_type = "文本处理" if is_text_processor else ""
            model_info = config.get("model", "未知")
        return safe_json_response(
            success=True,
            message=f"OpenAI {service_type}API连接成功，模型: {model_info} (通过模型列表测试)",
        )
    except Exception as e:
        # 提供更详细的错误信息
        error_msg = str(e)
        if "unauthorized" in error_msg.lower() or "401" in error_msg:
            error_msg = "API密钥无效或权限不足"
        elif "not found" in error_msg.lower() or "404" in error_msg:
            error_msg = "API端点不存在，请检查Base URL是否正确"
        elif "connection" in error_msg.lower():
            error_msg = "网络连接失败，请检查Base URL是否可访问"

        raise ConnectionError(f"连接测试失败: {error_msg}")


def test_gemini_connection(config, is_text_processor=False):
    """测试Gemini连接"""
    if not genai:
        raise ImportError("Gemini库未安装，请先安装: pip install google-generativeai")

    if not config.get("api_key"):
        raise ValueError("API Key未提供")

    genai.configure(api_key=config.get("api_key"))

    if config.get("base_url"):
        # 基本校验 base_url
        allowed_hosts, allow_http, allow_private, enforce_whitelist = (
            get_security_policy()
        )
        if not is_safe_base_url(
            config.get("base_url"),
            allowed_hosts=allowed_hosts,
            allow_http=allow_http,
            allow_private=allow_private,
            enforce_whitelist=enforce_whitelist,
        ):
            raise ValueError("不安全的Base URL，必须为HTTPS且非内网/本地地址")

    ok, _ = _pt_test_gemini(
        config.get("api_key"), config.get("base_url"), config.get("model", "gemini-pro")
    )

    service_type = "文本处理" if is_text_processor else ""
    return safe_json_response(
        success=True,
        message=f"Gemini {service_type}API连接成功，模型: {config.get('model', 'gemini-pro')}",
    )


@main_bp.route("/api/stop-all-tasks", methods=["POST"])
@api_error_handler
@admin_protected
def stop_all_tasks():
    """停止所有正在处理的任务"""
    try:
        # 标记并收集需要停止的任务
        processing_tasks = video_processor.cancel_all_processing()
        if not processing_tasks:
            return safe_json_response(
                success=True,
                message="当前没有正在处理的任务",
                data={"stopped_tasks": []},
            )

        # 停止所有正在处理的任务
        stopped_count = 0
        for task_id in processing_tasks:
            task = video_processor.get_task(task_id)
            if task and task.status == "processing":
                task.status = "failed"
                task.error_message = "用户手动停止任务"
                task.progress = 0
                task.progress_stage = "已停止"
                task.progress_detail = "任务已被用户手动停止"
                stopped_count += 1
                logging.info(f"手动停止任务: {task_id}")

        # 保存任务状态
        video_processor.save_tasks_to_disk()

        return safe_json_response(
            success=True,
            message=f"成功停止 {stopped_count} 个任务",
            data={"stopped_tasks": processing_tasks, "stopped_count": stopped_count},
        )

    except Exception as e:
        logging.error(f"停止所有任务失败: {e}")
        raise Exception(f"停止任务失败: {str(e)}")


@main_bp.route("/api/tasks/delete/<task_id>", methods=["POST", "DELETE"])
@api_error_handler
@admin_protected
def delete_task_record(task_id):
    """删除处理历史记录（并尽量清理相关文件）
    - 不依赖输出目录是否存在；哪怕目录已清理，也会删除内存记录
    - 同时尝试清理 temp 中的临时文件与历史登记
    """
    try:
        fm = FileManager()
        # 尝试删除输出目录（如果存在）
        ok_output = fm.delete_output_task_dir(task_id)
        # 清理临时目录/登记（容错）
        try:
            fm.cleanup_task_files(task_id)
        except Exception:
            pass

        # 删除内存任务记录
        if task_id in video_processor.tasks:
            del video_processor.tasks[task_id]
            try:
                video_processor.save_tasks_to_disk()
            except Exception:
                pass

        # 统一返回成功，提示是否清理了输出目录
        if ok_output:
            return safe_json_response(
                success=True, message=f"任务 {task_id} 记录已删除，相关文件已清理"
            )
        else:
            return safe_json_response(
                success=True,
                message=f"任务 {task_id} 记录已删除（未找到输出目录，可能已被清理）",
            )
    except Exception as e:
        return safe_json_response(success=False, message=str(e))


@main_bp.route("/api/webhook/test", methods=["POST"])
@api_error_handler
@admin_protected
def test_webhook_notification():
    """测试 webhook 通知配置。

    请求体示例：{"webhook": { ... 与 config.yaml.webhook 相同结构 ... }}
    仅用于发送一条测试通知，不依赖现有任务。
    """
    data = request.get_json(silent=True) or {}
    webhook_cfg = data.get("webhook") or {}

    if not webhook_cfg.get("enabled"):
        raise ValueError("请先在设置中启用 webhook 通知")

    # Best-effort validation to avoid non-http(s) schemes.
    # Compatibility-first: we do NOT block private/http webhook targets by default.
    # Strict mode (optional): ENFORCE_WEBHOOK_URL_SAFETY=true (or config security.enforce_webhook_url_safety=true)
    # will apply the repo's security policy to webhook targets.
    def _env_bool(name: str, default: bool = False) -> bool:
        v = os.environ.get(name)
        if v is None:
            return default
        return str(v).strip().lower() in ("1", "true", "yes", "on")

    strict = False
    try:
        strict = _env_bool("ENFORCE_WEBHOOK_URL_SAFETY", False)
        if not strict:
            sec = (Config.get_config() or {}).get("security") or {}
            strict = bool(sec.get("enforce_webhook_url_safety", False))
    except Exception:
        strict = _env_bool("ENFORCE_WEBHOOK_URL_SAFETY", False)

    def _ensure_webhook_url_safe(url: str, label: str) -> None:
        if not url:
            return
        if strict:
            _allowed_hosts, allow_http, allow_private, _enforce_whitelist = (
                get_security_policy()
            )
        else:
            allow_http, allow_private = True, True
        if not is_safe_base_url(
            url,
            allowed_hosts=[],
            allow_http=allow_http,
            allow_private=allow_private,
            enforce_whitelist=False,
        ):
            raise ValueError(
                f"不安全的 {label} URL（仅支持 http/https，且需符合安全策略）"
            )

    bark_cfg = webhook_cfg.get("bark") or {}
    wecom_cfg = webhook_cfg.get("wecom") or {}
    _ensure_webhook_url_safe(str(bark_cfg.get("server") or ""), "Bark server")
    _ensure_webhook_url_safe(str(wecom_cfg.get("webhook_url") or ""), "WeCom webhook")

    # 构造一个虚拟任务对象，复用现有通知逻辑
    class DummyTask:
        def __init__(self) -> None:
            self.id = "test-webhook"
            self.status = "completed"
            self.video_url = ""
            self.original_filename = "Webhook 测试通知"
            self.video_info = None

    try:
        base_cfg = (Config.get_config() or {}).get("webhook") or {}
    except Exception:
        base_cfg = {}

    from app.utils.webhook_notifier import send_task_completed_webhooks

    send_task_completed_webhooks(
        DummyTask(), base_config=base_cfg, runtime_config=webhook_cfg
    )

    return safe_json_response(
        success=True,
        message="已发送测试 webhook 通知（如配置正确，几秒内应在 Bark / 企业微信收到消息）",
    )
