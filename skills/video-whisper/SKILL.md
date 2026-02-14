---
name: video-whisper
description: Transcribe video/audio to text and generate AI summaries. Use when the user wants to convert a video URL (YouTube, Bilibili, etc.) or local video/audio file into a text transcript, get a summary, or extract spoken content. Supports any yt-dlp compatible platform. Requires SiliconFlow API key, ffmpeg, and yt-dlp. Works on Windows and Linux.
---

# Video Whisper

Transcribe video/audio → text transcript + AI summary using SiliconFlow API.

## Prerequisites

- **Python >= 3.10**
- **ffmpeg** (audio extraction/splitting)
- **yt-dlp** (video/audio download)
- **SiliconFlow API key** (speech-to-text + LLM summary)

Run setup to auto-install dependencies:

```bash
python scripts/setup.py
```

## API Key

Set `SILICONFLOW_API_KEY` environment variable, or pass `--api-key` to the script.

Register at https://cloud.siliconflow.cn/ to get a key (new accounts get ¥14 free credit).

## Usage

```bash
python scripts/transcribe.py <source> [options]

  --output, -o DIR          Output directory (default: ./output)
  --api-key KEY             SiliconFlow API key
  --stt-model MODEL         STT model (default: FunAudioLLM/SenseVoiceSmall)
  --llm-model MODEL         LLM model for summary (default: Qwen/Qwen3-Coder-30B-A3B-Instruct)
  --segment-seconds N       Audio segment length (default: 300)
  --no-summary              Skip summary generation
  --cookies STR             Site cookies for YouTube/Bilibili
  --json                    Output result as JSON (for agent parsing)
  --verbose, -v             Verbose logging
```

### Output files

```
output/
├── <title>_transcript.md    # Full transcript with metadata header
└── <title>_summary.md       # AI-generated summary (unless --no-summary)
```

## Agent Integration

### Running the script

1. Resolve `scripts/` path relative to this skill's directory
2. Ensure `SILICONFLOW_API_KEY` is set (or pass `--api-key`)
3. Run with `--json` for machine-readable output:
   ```
   python <skill_dir>/scripts/transcribe.py "<url>" --output <workspace>/output/video-whisper --json --no-summary
   ```
4. JSON output contains: `transcript_path`, `title`, `duration`, `char_count`, `elapsed_seconds`

### Delivering results to user

After transcription, decide how to deliver based on `char_count`:

- **Short transcript (≤ 1500 chars)**: Paste the full text directly in chat
- **Long transcript (> 1500 chars)**: Send the `.md` file via `message` tool (`path=<transcript_path>`), with a brief summary or the first few lines as chat text

For long videos (>30min), warn the user it may take several minutes before starting.

## Pipeline

1. **Download** audio from URL via yt-dlp (or use local file directly)
2. **Extract** audio from video via ffmpeg (if local video file)
3. **Split** long audio into 5-minute segments
4. **Transcribe** each segment via SiliconFlow SenseVoice API
5. **Clean** transcript (remove SenseVoice emoji markers)
6. **Summarize** full transcript via SiliconFlow LLM (optional)

## Notes

- SenseVoice model inserts emoji tokens (🎼😊😡) as audio event markers — the script auto-strips them
- Output filenames are based on video title, so multiple transcriptions won't overwrite each other
- URL tracking parameters (spm_id_from, vd_source, etc.) are auto-stripped from display

## Configuration Reference

See [references/config-example.yaml](references/config-example.yaml) for all available settings.
