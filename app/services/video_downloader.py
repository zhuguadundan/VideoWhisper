"""Video downloader utilities (yt_dlp lazy-loaded).

Public API used by the app:
- VideoDownloader.get_video_info(url, cookies_str=None) -> Dict
- VideoDownloader.download_audio_only(url, task_id, output_path=None, cookies_str=None) -> str

Design goals:
- Avoid heavy imports at module import time (lazy import yt_dlp)
- Keep source ASCII-clean to avoid encoding issues
- Keep signatures and behavior stable (Never break userspace)
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Protocol, TypedDict

from app.config.settings import Config

import threading
import time

# Global: limit concurrent downloads to protect CPU/network.
_DOWNLOAD_SEMAPHORE = threading.BoundedSemaphore(2)

from app.services.file_manager import FileManager


class DownloadProgress(TypedDict, total=False):
    status: str
    downloaded_bytes: int
    total_bytes: int
    total_bytes_estimate: int
    eta: int
    speed: float


ProgressCallback = Callable[[DownloadProgress], None]


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


from app.utils.helpers import sanitize_filename as utils_sanitize_filename
from app.utils.path_safety import is_within


class DownloadCancelled(RuntimeError):
    pass


logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        val = os.environ.get(name)
        if val is None or str(val).strip() == "":
            return default
        return int(val)
    except Exception:
        return default


def _build_timestamp_suffix(dt: Optional[datetime] = None) -> str:
    # Local time, stable, filesystem-friendly
    dt = dt or datetime.now()
    return dt.strftime("%Y%m%d_%H%M%S")


class VideoDownloader:
    """Lightweight downloader based on yt_dlp."""

    def __init__(self):
        cfg = Config.load_config()
        self.config = cfg
        self.temp_dir = Config.resolve_path(
            (cfg.get("system") or {}).get("temp_dir", "temp")
        )
        self.file_manager = FileManager()
        os.makedirs(self.temp_dir, exist_ok=True)

    # --- helpers ---
    def _sanitize_filename(self, filename: str) -> str:
        return utils_sanitize_filename(filename, default_name="file", max_length=100)

    def _get_ffmpeg_path(self) -> Optional[str]:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return ffmpeg_path
        # Common fallbacks
        if os.name == "nt":
            for path in (
                r"C:\\ffmpeg\\bin\\ffmpeg.exe",
                r"C:\\ffmpeg\\ffmpeg.exe",
                r"C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
                r"C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
            ):
                if os.path.exists(path):
                    return path
        else:
            for path in (
                "/usr/bin/ffmpeg",
                "/usr/local/bin/ffmpeg",
                "/opt/homebrew/bin/ffmpeg",
            ):
                if os.path.exists(path):
                    return path
        logger.warning("FFmpeg not found; ensure it is installed and on PATH")
        return None

    def _build_base_opts(
        self,
        cookies_str: Optional[str] = None,
        *,
        cookies_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Minimal, safe defaults; enable ffmpeg audio extraction
        opts: Dict[str, Any] = {
            "quiet": (
                self.config.get("downloader", {}).get("general", {}).get("quiet", False)
            ),
            "no_warnings": False,
            "outtmpl": os.path.join(self.temp_dir, "%(title)s.%(ext)s"),
            "restrictfilenames": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "geo_bypass": True,
        }
        ffmpeg_path = self._get_ffmpeg_path()
        if ffmpeg_path:
            opts["ffmpeg_location"] = os.path.dirname(ffmpeg_path)

        if cookies_str:
            # Write a temporary netscape cookie file.
            # NOTE: cookies are provided by frontend and should NOT be logged.
            # Domain must match target site (e.g. .youtube.com / .bilibili.com).
            import tempfile

            dom = (cookies_domain or "").strip()
            if not dom:
                dom = ".youtube.com"
            if not dom.startswith("."):
                dom = f".{dom}"

            tf = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            )
            tf.write("# Netscape HTTP Cookie File\n")
            for pair in cookies_str.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    name, value = pair.split("=", 1)
                    name = name.strip()
                    value = value.strip()
                    if not name:
                        continue
                    tf.write(f"{dom}\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
            tf.close()
            opts["cookiefile"] = tf.name
            opts["_temp_cookiefile"] = tf.name

        return opts

    # --- public API ---
    def get_video_info(
        self,
        url: str,
        cookies_str: Optional[str] = None,
        *,
        cookies_domain: Optional[str] = None,
        include_formats: bool = False,
    ) -> Dict[str, Any]:
        """Extract basic video info without downloading the media.

        include_formats:
          - False (default): return a small, stable payload used by the UI.
          - True: include a sanitized subset of formats for quality selection.
        """
        import importlib

        ydlp = importlib.import_module("yt_dlp")
        opts = self._build_base_opts(cookies_str, cookies_domain=cookies_domain)
        res: Dict[str, Any] = {}
        with ydlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Flatten playlist entries
            if info and isinstance(info, dict) and "entries" in info:
                info = info["entries"][0]

            res = {
                "id": (info or {}).get("id"),
                "title": (info or {}).get("title") or "Untitled",
                "uploader": (info or {}).get("uploader") or (info or {}).get("channel"),
                "duration": (info or {}).get("duration"),
                "webpage_url": (info or {}).get("webpage_url") or url,
                "url": (info or {}).get("webpage_url") or url,
                "ext": (info or {}).get("ext"),
            }

            if include_formats:
                formats = []
                for f in (info or {}).get("formats") or []:
                    if not isinstance(f, dict):
                        continue
                    formats.append(
                        {
                            "format_id": f.get("format_id"),
                            "ext": f.get("ext"),
                            "acodec": f.get("acodec"),
                            "vcodec": f.get("vcodec"),
                            "height": f.get("height"),
                            "width": f.get("width"),
                            "fps": f.get("fps"),
                            "tbr": f.get("tbr"),
                            "filesize": f.get("filesize"),
                            "filesize_approx": f.get("filesize_approx"),
                            "format_note": f.get("format_note"),
                        }
                    )
                res["formats"] = formats
                # Helpful metadata for quality-tier UI
                res["_has_formats"] = True

            # Always avoid downloading from info-probe endpoints
            res["_probe_only"] = True
        # Cleanup temp cookie file
        try:
            tmp = opts.get("_temp_cookiefile")
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass
        return res

    def download_audio_only(
        self,
        url: str,
        task_id: str,
        output_path: Optional[str] = None,
        cookies_str: Optional[str] = None,
        cookies_domain: Optional[str] = None,
    ) -> str:
        """Download best available audio and return file path.

        NOTE: Kept for backward compatibility with existing processing pipeline.
        """

        import importlib

        ydlp = importlib.import_module("yt_dlp")
        # Build output template
        out_dir = output_path if output_path is not None else self.temp_dir
        os.makedirs(out_dir, exist_ok=True)
        safe_task = re.sub(r"[^A-Za-z0-9_-]+", "_", task_id)
        outtmpl = os.path.join(out_dir, f"%(title)s_{safe_task}.%(ext)s")

        opts = self._build_base_opts(cookies_str, cookies_domain=cookies_domain)
        opts.update(
            {
                "outtmpl": outtmpl,
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "prefer_ffmpeg": True,
            }
        )

        # Download
        downloaded: Optional[str] = None
        with ydlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info and "_filename" in info:
                downloaded = info["_filename"]
            else:
                downloaded = ydl.prepare_filename(info)

        # Postprocessed file may have .mp3 extension
        if not downloaded:
            raise RuntimeError("yt-dlp did not return a downloaded filename")

        base = os.path.splitext(downloaded)[0]
        candidates = [f"{base}.mp3", downloaded]
        final_path: Optional[str] = None
        for p in candidates:
            if p and os.path.exists(p):
                final_path = p
                break
        if not final_path:
            # Fallback: search in out_dir
            mp3s = list(Path(out_dir).glob("*.mp3"))
            final_path = str(mp3s[0]) if mp3s else downloaded

        # Cleanup temp cookie file
        try:
            tmp = opts.get("_temp_cookiefile")
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass

        return final_path

    def download_video(
        self,
        url: str,
        *,
        output_dir: str,
        task_id: str,
        cookies_str: Optional[str] = None,
        cookies_domain: Optional[str] = None,
        format_selector: Optional[str] = None,
        progress_cb: Optional[ProgressCallback] = None,
        no_progress_timeout_sec: int = 120,
    ) -> str:
        """Download video into output_dir and return final path.

        - If format_selector is provided, yt-dlp will use it (e.g. "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best").
        - Otherwise, defaults to bestvideo+bestaudio/best.
        - Allows mkv/webm depending on source availability.
        - Applies global concurrency limit (2) via semaphore.
        - Aborts if no progress callback observed within no_progress_timeout_sec.
        - Enforces max file size via env var VW_DOWNLOAD_MAX_BYTES (default 5GB).

        Note: output_dir should be a server-controlled directory (e.g. output/<task_id>/)
        rather than a user-supplied path, to keep behavior stable across Windows/Docker.

        cookies_domain: optional cookie domain used when cookies_str is provided.
        """

        import importlib

        ydlp = importlib.import_module("yt_dlp")

        os.makedirs(output_dir, exist_ok=True)

        # Ensure output_dir is within repo output directory (defense-in-depth).
        repo_output_dir = Config.resolve_path(
            (self.config.get("system") or {}).get("output_dir", "output")
        )
        if not is_within(repo_output_dir, output_dir):
            raise ValueError("output_dir must be within configured output directory")

        max_bytes = _env_int("VW_DOWNLOAD_MAX_BYTES", 5 * 1024 * 1024 * 1024)
        last_progress_ts = time.time()
        last_pct: Optional[int] = None

        def _progress_hook(d: Dict[str, Any]) -> None:
            nonlocal last_progress_ts, last_pct
            status = str(d.get("status") or "")

            downloaded = _safe_int(d.get("downloaded_bytes"))
            total = _safe_int(d.get("total_bytes"))
            total_est = _safe_int(d.get("total_bytes_estimate"))
            eta = _safe_int(d.get("eta"))
            speed = _safe_float(d.get("speed"))

            # Enforce max bytes (prefer known total, but also guard downloaded bytes)
            total_any = total if total is not None else total_est
            if total_any is not None and total_any > max_bytes:
                raise DownloadCancelled(f"File too large (> {max_bytes} bytes)")
            if downloaded is not None and downloaded > max_bytes:
                raise DownloadCancelled(
                    f"Downloaded bytes exceeded limit (> {max_bytes} bytes)"
                )

            if status in ("downloading", "finished"):
                last_progress_ts = time.time()

            if total_any and downloaded is not None and total_any > 0:
                pct = int(downloaded * 100 / total_any)
                last_pct = pct
            else:
                pct = last_pct

            if progress_cb:
                payload: DownloadProgress = {"status": status}
                if downloaded is not None:
                    payload["downloaded_bytes"] = downloaded
                if total is not None:
                    payload["total_bytes"] = total
                if total_est is not None:
                    payload["total_bytes_estimate"] = total_est
                if eta is not None:
                    payload["eta"] = eta
                if speed is not None:
                    payload["speed"] = speed
                progress_cb(payload)

            # No-progress timeout: if we are stuck for too long while downloading
            if (
                status == "downloading"
                and (time.time() - last_progress_ts) > no_progress_timeout_sec
            ):
                raise DownloadCancelled("No progress for too long")

        # Use a temp template first, then rename/move to final output.
        safe_task = re.sub(r"[^A-Za-z0-9_-]+", "_", task_id)
        tmp_outtmpl = os.path.join(self.temp_dir, f"%(title)s_{safe_task}.%(ext)s")

        opts = self._build_base_opts(cookies_str, cookies_domain=cookies_domain)
        fmt = (format_selector or "").strip() or "bestvideo+bestaudio/best"

        opts.update(
            {
                "outtmpl": tmp_outtmpl,
                "format": fmt,
                "prefer_ffmpeg": True,
                "progress_hooks": [_progress_hook],
            }
        )

        downloaded_path: Optional[str] = None
        _DOWNLOAD_SEMAPHORE.acquire()
        try:
            with ydlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info and "_filename" in info:
                    downloaded_path = info["_filename"]
                else:
                    downloaded_path = ydl.prepare_filename(info)
        finally:
            _DOWNLOAD_SEMAPHORE.release()
            # Cleanup temp cookie file
            try:
                tmp = opts.get("_temp_cookiefile")
                if tmp and os.path.exists(tmp):
                    os.unlink(tmp)
            except Exception:
                pass

        if not downloaded_path or not os.path.exists(downloaded_path):
            raise RuntimeError("Download failed: output file not found")

        # Final filename: {title}_{timestamp}.{ext}
        title = Path(downloaded_path).stem
        ext = Path(downloaded_path).suffix.lstrip(".") or "mp4"
        safe_title = self._sanitize_filename(title)
        ts = _build_timestamp_suffix()
        final_name = f"{safe_title}_{ts}.{ext}"
        final_path = os.path.join(output_dir, final_name)

        # Ensure final path stays within output_dir
        if not is_within(output_dir, final_path):
            raise ValueError("Invalid output path")

        # Move to final destination
        os.replace(downloaded_path, final_path)
        return final_path
