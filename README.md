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
3.  **Python Environment:**
    It is recommended to use a virtual environment:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Linux/macOS
    # .venv\Scripts\activate   # On Windows
    pip install -r requirements.txt
    ```

## Usage

### Basic Command

```bash
python transcribe.py [URL | FILE]
```

### Output

By default, all processed files (audio, transcript, and summary) are stored in a subdirectory of the `output/` folder, named after the input file (slugified). You can change this base directory in `config.json`.

**Note:** Filenames are automatically sanitized (non-ASCII characters removed/transliterated, spaces replaced with hyphens) to ensure cross-platform compatibility.

### Options

*   `--no-summary`: Skip the summarization step (transcription only).
*   `-x`, `--delete-audio`: Automatically delete the audio file from the workspace after processing is complete.
*   `-v`, `--verbose`: Enable verbose logging and download progress.

### Examples

**1. Process a YouTube Video:**
```bash
python transcribe.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
```
*   Downloads the audio.
*   Creates a workspace directory in `output/` (e.g., `output/rick-roll/`).
*   Moves the audio there.
*   Converts and transcribes via local Whisper server.
*   Summarizes via local Ollama server.

**2. Process a Local File:**
```bash
python transcribe.py meeting.m4a
```
*   Moves `meeting.m4a` to `output/meeting/`.
*   Transcribes and summarizes.

**3. Transcription Only:**
```bash
python transcribe.py --no-summary interview.wav
```

## Configuration (`config.json`)

The script looks for `config.json` in the following locations, in order:

1.  The current directory (`./config.json`)
2.  The user's config directory (`~/.config/transcribe/config.json` on Linux/macOS)

```json
{
    "whisper_url": "http://192.168.1.212:8080/inference",
    "ollama_url": "http://192.168.1.212:11434/api/generate",
    "summarize_model": "qwen2.5",
    "output_directory": "output/",
    "downloader_args": { ... }
}
```

### Gemini CLI Support

To use the Google Gemini CLI instead of a local Ollama server for summarization:
1.  Ensure the `gemini` command-line tool is installed and in your PATH.
2.  Set `"summarize_model": "gemini"` in your `config.json`.
    *   The script will pipe the transcript to `gemini -p <SYSTEM_PROMPT>`.
