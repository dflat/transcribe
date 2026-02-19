# Transcribe (Cross-Platform Python Version)

This directory contains `transcribe.py`, a unified Python script that handles the entire audio-to-summary pipeline. It is designed to run on **Linux, Windows, and macOS**, replacing the earlier collection of shell and Rust scripts.

## Features

- **Unified Workflow:** Handles downloading (via `yt-dlp`), transcription (Whisper), and summarization (Ollama) in a single process.
- **Cross-Platform:** Uses standard Python libraries and cross-platform tools (`ffmpeg`, `plyer`) instead of OS-specific shell commands.
- **Configurable:** Uses `transcribe_config.json` for easy customization.
- **Robust:** Includes error handling, logging, and desktop notifications.

## Requirements

1.  **Python 3.8+**
2.  **FFmpeg:** Must be installed and available in your system's PATH.
    *   *Windows:* Download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add `bin` folder to PATH.
    *   *Linux:* `sudo apt install ffmpeg`
    *   *macOS:* `brew install ffmpeg`
3.  **Python Packages:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Basic Command

```bash
python transcribe.py [URL | FILE]
```

### Options

*   `--no-summary`: Skip the summarization step (transcription only).

### Examples

**1. Process a YouTube Video:**
```bash
python transcribe.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
```
*   Downloads the audio to a temporary folder.
*   Creates a workspace directory (e.g., `rick-roll`).
*   Moves the audio there.
*   Converts and transcribes via local Whisper server.
*   Summarizes via local Ollama server.

**2. Process a Local File:**
```bash
python transcribe.py meeting.m4a
```
*   Moves `meeting.m4a` to a new directory `meeting`.
*   Transcribes and summarizes.

**3. Transcription Only:**
```bash
python transcribe.py --no-summary interview.wav
```

## Configuration (`transcribe_config.json`)

The script looks for `transcribe_config.json` in the current directory.

```json
{
    "whisper_url": "http://192.168.1.212:8080/inference",
    "ollama_url": "http://192.168.1.212:11434/api/generate",
    "summarize_model": "qwen2.5",
    "downloader_args": { ... }
}
```
