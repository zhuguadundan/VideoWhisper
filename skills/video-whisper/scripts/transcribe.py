#!/usr/bin/env python3
"""
video-whisper transcribe.py
CLI tool: video/audio URL or local file -> transcript + summary

Usage:
    python transcribe.py <url_or_file> [options]

Examples:
    python transcribe.py "https://www.youtube.com/watch?v=xxx"
    python transcribe.py "https://www.bilibili.com/video/BVxxx"
    python transcribe.py ./my_video.mp4
    python transcribe.py ./podcast.mp3 --no-summary
    python transcribe.py "https://..." --output ./results --api-key sk-xxx

Environment:
    SILICONFLOW_API_KEY  - SiliconFlow API key (required)

Output:
    <output_dir>/<title>_transcript.md   - Full transcript
    <output_dir>/<title>_summary.md      - AI summary (unless --no-summary)
"""

import argparse
import importlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("video-whisper")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_filename(name: str, max_len: int = 80) -> str:
    """Sanitize a string for use as filename."""
    s = re.sub(r'[<>:"|?*\\\\/]', "_", name)
    s = s.strip(" .")
    if len(s) > max_len:
        s = s[:max_len]
    return s or "untitled"


def _clean_url(url: str) -> str:
    """Strip tracking parameters from URL for cleaner display and processing."""
    try:
        parsed = urlparse(url)
        # Keep only scheme, netloc, path (drop query & fragment for B站/YT tracking params)
        clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        return clean
    except Exception:
        return url


def _find_ffmpeg() -> Optional[str]:
    """Find ffmpeg binary."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    if os.name == "nt":
        for p in [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        ]:
            if os.path.exists(p):
                return p
    else:
        for p in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
            if os.path.exists(p):
                return p
    return None


def _format_duration(seconds: float) -> str:
    """Format seconds to HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# SenseVoice inserts emoji tokens (🎼😊😡 etc.) as audio event markers — strip them.
_SENSEVOICE_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001F9FF"   # Misc Symbols, Emoticons, etc.
    r"\U00002702-\U000027B0"
    r"\U0000FE00-\U0000FE0F"
    r"\U0000200D"
    r"\U000020E3"
    r"\U00002600-\U000026FF"
    r"]+",
    flags=re.UNICODE,
)


def _clean_transcript(text: str) -> str:
    """Remove SenseVoice emoji noise and normalize whitespace."""
    text = _SENSEVOICE_EMOJI_RE.sub("", text)
    # Collapse multiple spaces / blank lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Step 1: Download audio (for URLs)
# ---------------------------------------------------------------------------
def download_audio(url: str, temp_dir: str, cookies_str: Optional[str] = None) -> Dict[str, Any]:
    """Download audio from URL using yt-dlp. Returns dict with path, title, duration, uploader."""
    yt_dlp = importlib.import_module("yt_dlp")

    outtmpl = os.path.join(temp_dir, "%(title)s.%(ext)s")
    opts: Dict[str, Any] = {
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
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "restrictfilenames": True,
    }

    ffmpeg_path = _find_ffmpeg()
    if ffmpeg_path:
        opts["ffmpeg_location"] = os.path.dirname(ffmpeg_path)

    # Handle cookies
    cookie_file = None
    if cookies_str:
        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        tf.write("# Netscape HTTP Cookie File\n")
        domain = ".youtube.com"
        url_lower = url.lower()
        if "bilibili.com" in url_lower or "b23.tv" in url_lower:
            domain = ".bilibili.com"
        for pair in cookies_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                name, value = pair.split("=", 1)
                name, value = name.strip(), value.strip()
                if name:
                    tf.write(f"{domain}\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
        tf.close()
        opts["cookiefile"] = tf.name
        cookie_file = tf.name

    log.info("Downloading audio from: %s", _clean_url(url))
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info and "entries" in info:
                info = info["entries"][0]

            downloaded = info.get("_filename") or ydl.prepare_filename(info)
            title = (info or {}).get("title", "Untitled")
            duration = (info or {}).get("duration", 0)
            uploader = (info or {}).get("uploader") or (info or {}).get("channel", "")
    finally:
        if cookie_file and os.path.exists(cookie_file):
            os.unlink(cookie_file)

    # Find the mp3 output
    base = os.path.splitext(downloaded)[0]
    for candidate in [f"{base}.mp3", downloaded]:
        if os.path.exists(candidate):
            log.info("Audio downloaded: %s (duration: %s)", title, _format_duration(duration or 0))
            return {
                "path": candidate,
                "title": title,
                "duration": duration or 0,
                "uploader": uploader,
            }

    # Fallback: find any mp3 in temp_dir
    mp3s = list(Path(temp_dir).glob("*.mp3"))
    if mp3s:
        return {"path": str(mp3s[0]), "title": title, "duration": duration or 0, "uploader": uploader}

    raise RuntimeError(f"Download succeeded but output file not found. Expected: {base}.mp3")


# ---------------------------------------------------------------------------
# Step 2: Extract audio from local video (if needed)
# ---------------------------------------------------------------------------
def extract_audio(video_path: str, temp_dir: str) -> str:
    """Extract audio from a local video file using ffmpeg-python. Returns wav path."""
    ffmpeg = importlib.import_module("ffmpeg")

    base = _safe_filename(Path(video_path).stem)
    output_path = os.path.join(temp_dir, f"{base}.wav")

    log.info("Extracting audio from: %s", video_path)
    (
        ffmpeg.input(video_path)
        .output(output_path, acodec="pcm_s16le", ar=16000, ac=1)
        .run(overwrite_output=True, quiet=True)
    )
    log.info("Audio extracted: %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Step 3: Split audio into segments
# ---------------------------------------------------------------------------
def split_audio(audio_path: str, temp_dir: str, segment_seconds: int = 300) -> List[Dict[str, Any]]:
    """Split audio into segments for transcription. Returns list of segment dicts."""
    ffmpeg = importlib.import_module("ffmpeg")

    # Get duration
    probe = ffmpeg.probe(audio_path)
    duration = 0.0
    fmt = probe.get("format", {})
    if "duration" in fmt and fmt["duration"]:
        duration = float(fmt["duration"])
    else:
        for s in probe.get("streams", []):
            if s.get("codec_type") == "audio" and s.get("duration"):
                duration = float(s["duration"])
                break

    if duration <= 0:
        log.warning("Could not determine audio duration, treating as single segment")
        return [{"path": audio_path, "start": 0, "end": 0, "index": 0}]

    log.info("Audio duration: %s", _format_duration(duration))

    if duration <= segment_seconds:
        # Short audio: convert to wav if needed, return as single segment
        if not audio_path.endswith(".wav"):
            base = _safe_filename(Path(audio_path).stem)
            wav_path = os.path.join(temp_dir, f"{base}_full.wav")
            (
                ffmpeg.input(audio_path)
                .output(wav_path, acodec="pcm_s16le", ar=16000, ac=1)
                .run(overwrite_output=True, quiet=True)
            )
            return [{"path": wav_path, "start": 0, "end": duration, "index": 0}]
        return [{"path": audio_path, "start": 0, "end": duration, "index": 0}]

    # Long audio: split into segments
    segments = []
    base = _safe_filename(Path(audio_path).stem)
    current = 0.0
    idx = 0

    while current < duration:
        end = min(current + segment_seconds, duration)
        seg_path = os.path.join(temp_dir, f"{base}_seg{idx:03d}.wav")

        (
            ffmpeg.input(audio_path, ss=current, t=end - current)
            .output(seg_path, acodec="pcm_s16le", ar=16000, ac=1)
            .run(overwrite_output=True, quiet=True)
        )

        segments.append({"path": seg_path, "start": current, "end": end, "index": idx})
        current = end
        idx += 1

    log.info("Split into %d segments", len(segments))
    return segments


# ---------------------------------------------------------------------------
# Step 4: Transcribe audio segments via SiliconFlow API
# ---------------------------------------------------------------------------
def transcribe_segments(
    segments: List[Dict[str, Any]],
    api_key: str,
    base_url: str = "https://api.siliconflow.cn/v1",
    model: str = "FunAudioLLM/SenseVoiceSmall",
    max_retries: int = 3,
) -> str:
    """Transcribe audio segments using SiliconFlow speech-to-text API. Returns full text."""
    import requests

    texts = []
    total = len(segments)

    for seg in segments:
        seg_path = seg["path"]
        seg_idx = seg["index"]
        log.info("Transcribing segment %d/%d ...", seg_idx + 1, total)

        text = ""
        for attempt in range(max_retries):
            try:
                headers = {"Authorization": f"Bearer {api_key}"}
                with open(seg_path, "rb") as f:
                    files = {"file": ("audio.wav", f, "audio/wav")}
                    data = {"model": model}
                    resp = requests.post(
                        f"{base_url.rstrip('/')}/audio/transcriptions",
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=300,
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    text = result.get("text", "").strip()

                if text and len(text) >= 3:
                    break
                else:
                    log.warning("Segment %d: empty/short result, retry %d/%d", seg_idx + 1, attempt + 1, max_retries)
                    time.sleep(2)
            except Exception as e:
                log.warning("Segment %d: API error (%s), retry %d/%d", seg_idx + 1, e, attempt + 1, max_retries)
                time.sleep(2)

        if text:
            texts.append(text)
            log.info("Segment %d/%d done (%d chars)", seg_idx + 1, total, len(text))
        else:
            log.error("Segment %d/%d: transcription failed after %d retries", seg_idx + 1, total, max_retries)
            texts.append(f"[Segment {seg_idx + 1} transcription failed]")

    return "\n\n".join(texts)


# ---------------------------------------------------------------------------
# Step 5: Generate summary via LLM (SiliconFlow OpenAI-compatible API)
# ---------------------------------------------------------------------------
def generate_summary(
    transcript: str,
    api_key: str,
    base_url: str = "https://api.siliconflow.cn/v1",
    model: str = "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    title: str = "",
) -> str:
    """Generate a summary of the transcript using SiliconFlow LLM."""
    openai_mod = importlib.import_module("openai")

    client = openai_mod.OpenAI(api_key=api_key, base_url=base_url)

    prompt = """请为以下视频逐字稿生成一份详细的总结报告，使用 Markdown 格式：

## 主要内容概述
（用2-3段话概括主要内容）

## 关键要点
（列出3-5个关键要点，使用项目符号）

## 重要细节
（补充重要的细节信息）

## 结论或建议
（如果适用，提供结论或建议）

请直接输出总结，不要添加额外说明。"""

    # Handle long transcripts by truncating (LLM context limit)
    max_chars = 48000
    text_to_send = transcript
    if len(transcript) > max_chars:
        log.warning("Transcript too long (%d chars), truncating to %d for summary", len(transcript), max_chars)
        text_to_send = transcript[:max_chars] + "\n\n[... 文本过长已截断 ...]"

    if title:
        text_to_send = f"视频标题: {title}\n\n{text_to_send}"

    log.info("Generating summary (%d chars input)...", len(text_to_send))

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text_to_send},
                ],
                temperature=0.3,
                max_tokens=8000,
            )
            result = resp.choices[0].message.content.strip()
            log.info("Summary generated (%d chars)", len(result))
            return result
        except Exception as e:
            log.warning("Summary generation failed (%s), retry %d/%d", e, attempt + 1, max_retries)
            time.sleep(2)

    return "[Summary generation failed after retries]"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def is_url(s: str) -> bool:
    """Check if string looks like a URL."""
    return s.startswith("http://") or s.startswith("https://")


def is_audio_file(path: str) -> bool:
    """Check if file is an audio format that can be directly transcribed."""
    ext = Path(path).suffix.lower()
    return ext in {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".wma"}


def is_video_file(path: str) -> bool:
    """Check if file is a video format that needs audio extraction."""
    ext = Path(path).suffix.lower()
    return ext in {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".ts"}


def run_pipeline(
    source: str,
    output_dir: str,
    api_key: str,
    stt_base_url: str = "https://api.siliconflow.cn/v1",
    stt_model: str = "FunAudioLLM/SenseVoiceSmall",
    llm_base_url: str = "https://api.siliconflow.cn/v1",
    llm_model: str = "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    segment_seconds: int = 300,
    no_summary: bool = False,
    cookies: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full pipeline: source -> transcript (+ optional summary).

    Returns dict with keys: transcript_path, summary_path (if generated),
    title, duration, char_count, elapsed_seconds
    """
    t0 = time.time()
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix="vw_")

    try:
        title = ""
        uploader = ""
        duration = 0
        audio_path = ""

        # --- Determine source type and get audio ---
        if is_url(source):
            info = download_audio(source, temp_dir, cookies_str=cookies)
            audio_path = info["path"]
            title = info["title"]
            uploader = info.get("uploader", "")
            duration = info.get("duration", 0)
        elif os.path.isfile(source):
            if is_audio_file(source):
                audio_path = source
                title = Path(source).stem
            elif is_video_file(source):
                audio_path = extract_audio(source, temp_dir)
                title = Path(source).stem
            else:
                raise ValueError(f"Unsupported file format: {Path(source).suffix}")
        else:
            raise FileNotFoundError(f"Source not found: {source}")

        # --- Split audio ---
        segments = split_audio(audio_path, temp_dir, segment_seconds)

        # --- Transcribe ---
        raw_transcript = transcribe_segments(
            segments,
            api_key=api_key,
            base_url=stt_base_url,
            model=stt_model,
        )

        if not raw_transcript.strip():
            raise RuntimeError("Transcription produced empty result")

        # --- Clean transcript (remove SenseVoice emoji noise) ---
        transcript = _clean_transcript(raw_transcript)

        # --- Build output filenames based on title ---
        safe_title = _safe_filename(title)
        transcript_filename = f"{safe_title}_transcript.md"
        transcript_path = os.path.join(output_dir, transcript_filename)

        # --- Build header ---
        clean_source = _clean_url(source) if is_url(source) else source
        header = f"# {title}\n\n"
        if uploader:
            header += f"**作者/频道**: {uploader}\n"
        if duration:
            header += f"**时长**: {_format_duration(duration)}\n"
        header += f"**来源**: {clean_source}\n\n---\n\n"

        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(header + transcript)
        log.info("Transcript saved: %s", transcript_path)

        elapsed = time.time() - t0
        result: Dict[str, Any] = {
            "transcript_path": transcript_path,
            "title": title,
            "duration": duration,
            "char_count": len(transcript),
            "elapsed_seconds": round(elapsed, 1),
        }

        # --- Generate summary ---
        if not no_summary:
            summary = generate_summary(
                transcript,
                api_key=api_key,
                base_url=llm_base_url,
                model=llm_model,
                title=title,
            )
            summary_filename = f"{safe_title}_summary.md"
            summary_path = os.path.join(output_dir, summary_filename)
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(f"# {title} - 总结\n\n{summary}")
            log.info("Summary saved: %s", summary_path)
            result["summary_path"] = summary_path
            result["elapsed_seconds"] = round(time.time() - t0, 1)

        return result

    finally:
        # Cleanup temp files
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="video-whisper: Video/Audio -> Transcript + Summary",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python transcribe.py "https://www.youtube.com/watch?v=xxx"
  python transcribe.py "https://www.bilibili.com/video/BVxxx"
  python transcribe.py ./video.mp4
  python transcribe.py ./podcast.mp3 --no-summary
  python transcribe.py "https://..." --output ./results
  python transcribe.py "https://..." --api-key sk-xxx
  python transcribe.py "https://..." --llm-model "deepseek-ai/DeepSeek-V3"
        """,
    )
    parser.add_argument("source", help="Video/audio URL or local file path")
    parser.add_argument("--output", "-o", default="./output", help="Output directory (default: ./output)")
    parser.add_argument("--api-key", help="SiliconFlow API key (or set SILICONFLOW_API_KEY env)")
    parser.add_argument("--stt-base-url", default="https://api.siliconflow.cn/v1", help="STT API base URL")
    parser.add_argument("--stt-model", default="FunAudioLLM/SenseVoiceSmall", help="STT model name")
    parser.add_argument("--llm-base-url", default="https://api.siliconflow.cn/v1", help="LLM API base URL")
    parser.add_argument("--llm-model", default="Qwen/Qwen3-Coder-30B-A3B-Instruct", help="LLM model for summary")
    parser.add_argument("--segment-seconds", type=int, default=300, help="Audio segment length in seconds (default: 300)")
    parser.add_argument("--no-summary", action="store_true", help="Skip summary generation")
    parser.add_argument("--cookies", help="Site cookies string (for YouTube/Bilibili)")
    parser.add_argument("--json", action="store_true", help="Output result as JSON (for agent integration)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Resolve API key
    api_key = args.api_key or os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] SiliconFlow API key required.")
        print("  Set via: --api-key sk-xxx")
        print("  Or env:  SILICONFLOW_API_KEY=sk-xxx")
        sys.exit(1)

    try:
        result = run_pipeline(
            source=args.source,
            output_dir=args.output,
            api_key=api_key,
            stt_base_url=args.stt_base_url,
            stt_model=args.stt_model,
            llm_base_url=args.llm_base_url,
            llm_model=args.llm_model,
            segment_seconds=args.segment_seconds,
            no_summary=args.no_summary,
            cookies=args.cookies,
        )

        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print()
            print("=" * 50)
            print(f"  Title:      {result['title']}")
            print(f"  Duration:   {_format_duration(result.get('duration', 0))}")
            print(f"  Characters: {result['char_count']}")
            print(f"  Time taken: {result['elapsed_seconds']}s")
            print(f"  Transcript: {result['transcript_path']}")
            if "summary_path" in result:
                print(f"  Summary:    {result['summary_path']}")
            print("=" * 50)

    except KeyboardInterrupt:
        print("\n[CANCELLED] Interrupted by user")
        sys.exit(130)
    except Exception as e:
        log.error("Pipeline failed: %s", e)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
