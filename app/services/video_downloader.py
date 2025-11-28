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
from typing import Any, Dict, Optional

from app.config.settings import Config
from app.services.file_manager import FileManager
from app.utils.helpers import sanitize_filename as utils_sanitize_filename

logger = logging.getLogger(__name__)


class VideoDownloader:
    """Lightweight audio-only downloader based on yt_dlp."""

    def __init__(self):
        cfg = Config.load_config()
        self.config = cfg
        self.temp_dir = Config.resolve_path((cfg.get("system") or {}).get("temp_dir", "temp"))
        self.file_manager = FileManager()
        os.makedirs(self.temp_dir, exist_ok=True)

    # --- helpers ---
    def _sanitize_filename(self, filename: str) -> str:
        return utils_sanitize_filename(filename, default_name="audio_file", max_length=100)

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
            for path in ("/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"):
                if os.path.exists(path):
                    return path
        logger.warning("FFmpeg not found; ensure it is installed and on PATH")
        return None

    def _build_base_opts(self, cookies_str: Optional[str] = None) -> Dict[str, Any]:
        # Minimal, safe defaults; enable ffmpeg audio extraction
        opts: Dict[str, Any] = {
            "quiet": (self.config.get("downloader", {}).get("general", {}).get("quiet", False)),
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
            # Write a temporary netscape cookie file
            import tempfile

            tf = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
            tf.write("# Netscape HTTP Cookie File\n")
            for pair in cookies_str.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    name, value = pair.split("=", 1)
                    tf.write(f".youtube.com\tTRUE\t/\tFALSE\t0\t{name.strip()}\t{value.strip()}\n")
            tf.close()
            opts["cookiefile"] = tf.name
            opts["_temp_cookiefile"] = tf.name
        return opts

    # --- public API ---
    def get_video_info(self, url: str, cookies_str: str = None) -> Dict[str, Any]:
        """Extract basic video info without downloading the media."""
        import importlib

        ydlp = importlib.import_module("yt_dlp")
        opts = self._build_base_opts(cookies_str)
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
        cookies_str: str = None,
    ) -> str:
        """Download best available audio and return file path."""
        import importlib

        ydlp = importlib.import_module("yt_dlp")
        # Build output template
        out_dir = output_path or self.temp_dir
        os.makedirs(out_dir, exist_ok=True)
        safe_task = re.sub(r"[^A-Za-z0-9_-]+", "_", task_id)
        outtmpl = os.path.join(out_dir, f"%(title)s_{safe_task}.%(ext)s")

        opts = self._build_base_opts(cookies_str)
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
        base = os.path.splitext(downloaded)[0]
        candidates = [f"{base}.mp3", downloaded]
        final_path = None
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


