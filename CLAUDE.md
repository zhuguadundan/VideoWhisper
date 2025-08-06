# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Application
```bash
python run.py
```
The Flask web app will start on http://localhost:5000

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Testing
```bash
# Simple test
python test_simple.py

# Complete integration test
python test_complete.py

# Basic functionality test
python test.py
```

### FFmpeg Installation
- **Windows**: Use the provided PowerShell scripts: `install-ffmpeg.ps1` or `install-ffmpeg-en.ps1`
- **Linux/Mac**: Install via package manager (apt, brew)

## Architecture Overview

This is a video-to-text processing system built with Flask that handles:

1. **Video Download & Processing Pipeline**: 
   - Video URL input → yt-dlp download → FFmpeg audio extraction → Speech-to-text → AI text processing
   - Located in `app/services/video_processor.py`

2. **Service Layer Structure**:
   - `video_downloader.py`: Handles video downloads using yt-dlp
   - `audio_extractor.py`: Extracts audio using FFmpeg
   - `speech_to_text.py`: Converts speech to text using SiliconFlow API
   - `text_processor.py`: Processes text using OpenAI/Gemini APIs

3. **Flask Application Structure**:
   - `app/__init__.py`: App factory pattern
   - `app/main.py`: Main blueprint with API routes
   - `app/config/settings.py`: Configuration management
   - `app/models/data_models.py`: Data classes for task management

4. **API Configuration**:
   - Configuration stored in `config.yaml`
   - Supports multiple AI providers: SiliconFlow (speech), OpenAI/Gemini (text processing)
   - Tasks are processed asynchronously using threading

5. **File Organization**:
   - `temp/`: Temporary files during processing
   - `output/<task_id>/`: Final outputs (transcript.txt, summary.md, data.json)
   - `web/`: Static assets and HTML templates

## Key API Endpoints

- `POST /api/process`: Create new video processing task
- `GET /api/progress/<task_id>`: Get processing progress
- `GET /api/result/<task_id>`: Get final results
- `GET /api/download/<task_id>/<file_type>`: Download result files
- `GET /api/tasks`: List all tasks

## Configuration Notes

- API keys are stored in `config.yaml` (not environment variables)
- The system supports Chinese language content (comments and UI are in Chinese)
- Task processing is handled via background threads with progress tracking
- Video info extraction includes title, uploader, and duration metadata

## Dependencies

- **Core**: Flask, yt-dlp, ffmpeg-python
- **AI APIs**: openai, google-generativeai
- **Utilities**: pyyaml, python-dotenv, dataclasses-json