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
# Simple test - validates basic system components
python test_simple.py

# Complete integration test - full pipeline testing
python test_complete.py

# Basic functionality test - core feature validation
python test.py
```

### FFmpeg Installation
- **Windows**: Use provided PowerShell scripts: `install-ffmpeg.ps1` or `install-ffmpeg-en.ps1`
- **Linux/Mac**: Install via package manager (apt, brew, etc.)

## Architecture Overview

**VideoWhisper** is a video-to-text processing system with asynchronous task management built on Flask. The system processes videos through a multi-stage pipeline with real-time progress tracking.

### Core Processing Pipeline
Video URL → yt-dlp download → FFmpeg audio extraction → SiliconFlow speech-to-text → OpenAI/Gemini text processing → Structured output

### Key Architectural Components

**1. Task Management System** (`app/services/video_processor.py`)
- UUID-based task identification and tracking
- Asynchronous processing using Python threading (not async/await)
- Progress tracking (0-100%) with real-time updates via polling
- Task persistence to disk with JSON serialization
- Automatic cleanup of temporary files on completion/failure

**2. Service Layer** (Multi-provider pattern)
- `video_downloader.py`: yt-dlp wrapper with platform-specific configurations (YouTube, Douyin/TikTok with cookie support)
- `audio_extractor.py`: FFmpeg integration with audio segmentation (5-minute chunks for long content)
- `speech_to_text.py`: SiliconFlow API client with batch processing and timestamp alignment
- `text_processor.py`: Multi-provider AI integration (OpenAI/Gemini) with structured prompt templates

**3. Data Models** (`app/models/data_models.py`)
- `ProcessingTask`: Task state management (pending → processing → completed/failed)
- `VideoInfo`: Video metadata extraction (title, uploader, duration)
- `TranscriptionResult`: Speech recognition results with confidence scores
- All models use dataclass with JSON serialization support

**4. Configuration System** (`app/config/settings.py`)
- YAML-based configuration from `config.yaml` (not environment variables)
- Multi-provider API key management
- Platform-specific downloader settings (cookies, headers)
- System limits (file size, processing timeout)

**5. Web Interface** (`web/`)
- Bootstrap 5 responsive UI with custom CSS styling
- Real-time progress updates via JavaScript polling (no WebSocket)
- Settings page for API configuration management
- File download interface for all output formats

## Key API Endpoints

### Core Processing
- `POST /api/process`: Create new video processing task (returns task_id)
- `GET /api/progress/<task_id>`: Real-time progress tracking (0-100%)
- `GET /api/result/<task_id>`: Retrieve completed processing results
- `GET /api/download/<task_id>/<file_type>`: Download result files (txt, md, json)

### Management
- `GET /api/tasks`: List all historical tasks with metadata
- `POST /api/test-connection`: Test API connectivity for configured providers

### File Management (v2.1.0)
- `GET /api/files`: List all files in output and temp directories
- `GET /api/files/download/<file_id>`: Download any file by ID
- `POST /api/files/delete`: Delete multiple files by ID
- `POST /api/files/delete-task/<task_id>`: Delete all files for a specific task

### Settings Management (v2.1.0)
- `GET /api/settings`: Get current configuration
- `POST /api/settings`: Update configuration

## Output File Structure

Each task generates files in `/output/<task_id>/`:
- `transcript.txt`: Clean, formatted transcript
- `transcript_with_timestamps.txt`: Timestamped version
- `summary.md`: Structured analysis report with metadata
- `data.json`: Complete processing data including confidence scores

## Platform-Specific Features

**YouTube Support**: Direct public video processing
**Douyin/TikTok Support**: Requires cookies.txt file in project root for authentication

## Configuration Management

### API Keys (stored in `config.yaml`)
```yaml
apis:
  siliconflow:    # Speech recognition (required)
  openai:         # Text processing option 1
  gemini:         # Text processing option 2
```

### System Settings
- Chinese language interface and error messages
- Configurable file size limits and processing timeouts
- Automatic task history retention

## Development Notes

- **Asynchronous Pattern**: Uses threading, not async/await
- **Error Handling**: Comprehensive Chinese error messages throughout
- **Testing Strategy**: Three-tier testing (simple → complete → basic)
- **File Management**: Automatic cleanup with configurable retention
- **Progress Tracking**: Polling-based (not real-time WebSocket)

## Dependencies

**Core Framework**: Flask 2.3.3, yt-dlp, ffmpeg-python
**AI Services**: openai 1.99.1, google-generativeai 0.3.0
**Data Processing**: pyyaml, dataclasses-json, python-dotenv