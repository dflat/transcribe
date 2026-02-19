# Developer Guide: Transcribe Pipeline

This document provides a technical overview of the `transcribe.py` script, its architecture, and instructions for running the test suite.

## Architecture Overview

The `transcribe.py` script is a linear pipeline designed to process audio input (URL or local file) and generate a structured summary. It follows a **Research -> Strategy -> Execution** pattern, but implemented as a sequential flow of specialized components.

### Core Components

The script is organized into three main classes, each responsible for a distinct stage of the pipeline:

1.  **`Downloader`**:
    *   **Responsibility**: Handles fetching audio from external URLs using `yt-dlp`.
    *   **Key Method**: `download(url, output_dir)`
    *   **Behavior**: Downloads audio to a temporary or specified directory, ensuring the file is available for the next stage. It handles filename extraction and error checking.

2.  **`Transcriber`**:
    *   **Responsibility**: Converts audio to a suitable format and interfaces with the Whisper inference server.
    *   **Key Method**: `transcribe(audio_path)`
    *   **Internal Step**: `_convert_to_wav_16k(input_path)` uses `ffmpeg` to convert any audio input to 16kHz mono WAV, which is the required format for the Whisper model.
    *   **Output**: Saves the raw transcript to a `.txt` file and segment timestamps to a `.json` file.

3.  **`Summarizer`**:
    *   **Responsibility**: Sends the transcript to an Ollama inference server to generate a Markdown summary.
    *   **Key Method**: `summarize(transcript_path, output_path)`
    *   **Behavior**: Constructs a prompt using a predefined `SYSTEM_PROMPT` and the transcript text, then saves the resulting Markdown to a file.

### Data Flow

1.  **Initialization**: Config is loaded, logging is set up, and dependencies (`ffmpeg`) are checked.
2.  **Input Handling**:
    *   **URL**: Downloaded to a temporary location first.
    *   **File**: Path resolved locally.
3.  **Workspace Creation**: A unique directory (slugified name) is created in the `output_directory` (default: `output/`). The audio file is moved here.
4.  **Processing**:
    *   `Downloader` -> `Audio File`
    *   `Transcriber` -> `Audio File` -> `Transcript (.txt)` & `Timestamps (.json)`
    *   `Summarizer` -> `Transcript` -> `Summary (.md)`

## Configuration

Configuration is managed via `transcribe_config.json`. The `load_config()` function reads this file and overlays it on top of `DEFAULT_CONFIG`.

*   **`whisper_url`**: Endpoint for the Whisper server.
*   **`ollama_url`**: Endpoint for the Ollama server.
*   **`output_directory`**: Base path for all output workspaces.
*   **`downloader_args`**: Dictionary of options passed directly to `yt-dlp`.

## Development Setup

### Prerequisites

*   Python 3.8+
*   `ffmpeg` (must be in system PATH)

### Environment Setup

1.  **Create a Virtual Environment**:
    ```bash
    python3 -m venv .venv
    ```

2.  **Activate the Environment**:
    *   Linux/macOS:
        ```bash
        source .venv/bin/activate
        ```
    *   Windows:
        ```bash
        .venv\Scripts\activate
        ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Running Tests

The project includes a `unittest` suite located in `tests/test_transcribe.py`. These tests verify the core logic of the components by mocking external interactions (network requests, file system, subprocesses).

### How to Run

Ensure your virtual environment is activated, then run:

```bash
python3 -m unittest tests/test_transcribe.py
```

### Test Coverage

*   **`TestConfiguration`**: Verifies that config files are loaded correctly and defaults are respected.
*   **`TestDownloader`**: Mocks `yt-dlp` to simulate successful and failed downloads without actually connecting to the internet.
*   **`TestTranscriber`**: Mocks `subprocess.run` (for `ffmpeg`) and `requests.post` (for Whisper) to verify that the transcription flow works and files are written to the correct locations.
*   **`TestSummarizer`**: Mocks `requests.post` (for Ollama) to verify prompt construction and file writing.

### Note on Mocking

Since `transcribe.py` relies heavily on external side effects (calling APIs, running shell commands, writing files), the tests use `unittest.mock` extensively. This allows us to test the *logic* of the script (e.g., "did we call the API with the right URL?", "did we handle the 404 error?") without requiring actual servers to be running.
