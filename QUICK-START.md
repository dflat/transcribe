# Quick Start Guide

Get up and running in minutes.

## 1. Prerequisites

*   **Python 3.8+** installed.
*   **FFmpeg** installed and in your PATH.
    *   *Mac:* `brew install ffmpeg`
    *   *Linux:* `sudo apt install ffmpeg`
    *   *Windows:* Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), extract, and add `bin` folder to your System PATH.
*   **(Optional) Gemini CLI**: If using Gemini for summaries, ensure `gemini` command is in your PATH.

## 2. Setup Environment

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. Configuration

Create a file named `transcribe_config.json` in this directory.

**Minimal Example (Using Ollama):**
```json
{
  "whisper_url": "http://localhost:8080/inference",
  "ollama_url": "http://localhost:11434/api/generate",
  "summarize_model": "qwen2.5",
  "output_directory": "output/"
}
```

**Gemini Example (CLI):**
```json
{
  "whisper_url": "http://localhost:8080/inference",
  "summarize_model": "gemini",
  "output_directory": "output/"
}
```

## 4. Run

Process a YouTube video or local file:

```bash
# Video URL
python transcribe.py https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Local File
python transcribe.py my_meeting.mp3
```

**Check Output:**
Look in the `output/` directory for your transcript and summary!
