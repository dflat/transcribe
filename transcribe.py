#!/usr/bin/env python3
import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

# Third-party imports (must be installed via pip)
try:
    import requests
    import yt_dlp
    from plyer import notification
    from slugify import slugify
except ImportError as e:
    print(f"Error: Missing dependency '{e.name}'. Please run: pip install -r requirements.txt")
    sys.exit(1)

# --- Configuration & Constants ---

DEFAULT_CONFIG = {
    "whisper_url": "http://192.168.1.212:8080/inference",
    "ollama_url": "http://192.168.1.212:11434/api/generate",
    "summarize_model": "qwen2.5",
    "output_directory": "output/",
    "downloader_args": {
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "outtmpl": "%(title)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }
}

CONFIG_FILE_NAME = "transcribe_config.json"

# System Prompt for Summarization (Ported from outline.sh)
SYSTEM_PROMPT = """You are an expert technical writer and analyst. Your task is to generate a comprehensive, structured Markdown outline based on the following transcript.

Follow these strict guidelines:
1. **Structure**: Use hierarchical headings (H1 for title, H2 for main topics, H3 for subtopics) to reflect the logical flow.
2. **Detail**: Go beyond high-level summaries. Capture specific facts, decisions, technical specifications, and key arguments.
3. **Clarity**: Use bullet points for readability. Bold key terms and entities.
4. **Action Items**: Explicitly list any action items, next steps, or open questions at the end.
5. **Context**: Preserving the context of the discussion is crucial. Do not over-generalize.
6. **Format**: Return ONLY the Markdown content. Do not include conversational filler like 'Here is the outline'."""

# --- Utilities ---

def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file or return defaults."""
    config_path = Path(CONFIG_FILE_NAME)
    config = DEFAULT_CONFIG.copy()
    
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                config.update(user_config)
            # Logging might not be setup yet, so defer logging until setup_logging
        except json.JSONDecodeError as e:
            # We will log this later if possible or just print
            print(f"Warning: Failed to parse config file: {e}. Using defaults.")
    
    return config

def notify(title: str, message: str):
    """Send a cross-platform desktop notification."""
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="Transcribe Pipeline",
            timeout=5
        )
    except Exception as e:
        logging.warning(f"Notification failed: {e}")

def check_dependencies():
    """Ensure external tools like ffmpeg are available."""
    if not shutil.which("ffmpeg"):
        logging.error("FFmpeg not found in PATH. Please install FFmpeg.")
        sys.exit(1)

# --- Pipeline Components ---

class Downloader:
    def __init__(self, config: Dict[str, Any]):
        self.ydl_opts = config.get("downloader_args", DEFAULT_CONFIG["downloader_args"])

    def download(self, url: str, output_dir: Path) -> Path:
        """Download audio from URL to the specified directory."""
        logging.info(f"Downloading audio from: {url}")
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Update output template to save directly to output_dir
        opts = self.ydl_opts.copy()
        opts['outtmpl'] = str(output_dir / opts['outtmpl'])
        opts['paths'] = {'home': str(output_dir)} # Safety for paths

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # yt-dlp might change extension (e.g., m4a -> mp3)
                # We need to find the actual file created
                base_name = Path(filename).stem
                # Look for the file with the expected base name in output_dir
                found_files = list(output_dir.glob(f"{base_name}.*"))
                if not found_files:
                    raise FileNotFoundError("Downloaded file not found.")
                
                # Sort by modification time to get the most recent one (the converted one)
                found_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                final_path = found_files[0]
                
                logging.info(f"Download complete: {final_path.name}")
                return final_path
                
        except Exception as e:
            logging.error(f"Download failed: {e}")
            raise

class Transcriber:
    def __init__(self, server_url: str):
        self.server_url = server_url

    def _convert_to_wav_16k(self, input_path: Path) -> Path:
        """Convert audio to 16kHz mono WAV for Whisper."""
        output_path = input_path.with_suffix(".wav")
        logging.info(f"Converting {input_path.name} to 16kHz WAV...")
        
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-ar", "16000", "-ac", "1", "-loglevel", "error",
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True)
        return output_path

    def transcribe(self, audio_path: Path) -> tuple[Path, Path]:
        """Transcribe audio file. Returns paths to (transcript.txt, timestamps.json)."""
        # 1. Convert
        wav_path = self._convert_to_wav_16k(audio_path)
        
        # 2. Upload to Whisper Server
        logging.info("Uploading to Whisper server...")
        try:
            with open(wav_path, 'rb') as f:
                files = {'file': (wav_path.name, f, 'audio/wav')}
                data = {'response_format': 'verbose_json', 'temperature': '0.0'}
                
                response = requests.post(self.server_url, files=files, data=data)
                response.raise_for_status()
                result = response.json()

            # 3. Save Results
            base_name = audio_path.stem
            txt_path = audio_path.parent / f"{base_name}.txt"
            json_path = audio_path.parent / f"{base_name}_timestamps.json"

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(result.get("text", "").strip())
            
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result.get("segments", []), f, indent=2, ensure_ascii=False)
            
            logging.info(f"Transcription saved to {txt_path.name}")
            return txt_path, json_path

        finally:
            # Cleanup temporary WAV file
            if wav_path.exists() and wav_path != audio_path:
                wav_path.unlink()

class Summarizer:
    def __init__(self, server_url: str, model: str):
        self.server_url = server_url
        self.model = model

    def summarize(self, transcript_path: Path, output_path: Path):
        """Generate summary from transcript using Ollama or Gemini CLI."""
        logging.info(f"Summarizing {transcript_path.name} using {self.model}...")
        
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript_text = f.read()

        if self.model.lower() == "gemini":
            self._summarize_gemini(transcript_text, output_path)
        else:
            self._summarize_ollama(transcript_text, output_path)

    def _summarize_gemini(self, transcript_text: str, output_path: Path):
        """Summarize using the Gemini CLI tool."""
        if not shutil.which("gemini"):
             raise FileNotFoundError("The 'gemini' CLI tool is required but not found in PATH.")

        cmd = ["gemini", "-p", SYSTEM_PROMPT]
        
        try:
            # Run gemini command, piping transcript to stdin
            process = subprocess.run(
                cmd,
                input=transcript_text,
                text=True,
                capture_output=True,
                check=True
            )
            
            # Write stdout to output file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(process.stdout)
                
            logging.info(f"Summary saved to {output_path.name}")
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Gemini CLI failed: {e.stderr}")
            raise RuntimeError(f"Gemini CLI failed with return code {e.returncode}") from e

    def _summarize_ollama(self, transcript_text: str, output_path: Path):
        """Summarize using the Ollama API."""
        prompt = f"""{SYSTEM_PROMPT}

Transcript:
{transcript_text}"""
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        try:
            response = requests.post(self.server_url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            summary_text = result.get("response", "")
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(summary_text)
                
            logging.info(f"Summary saved to {output_path.name}")
            
        except requests.RequestException as e:
            logging.error(f"Summarization failed: {e}")
            raise

# --- Main Logic ---

def main():
    try:
        parser = argparse.ArgumentParser(description="Download, Transcribe, and Summarize Audio.")
        parser.add_argument("input", help="URL to download or path to local audio file.")
        parser.add_argument("--no-summary", action="store_true", help="Skip summary generation.")
        parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging and download progress.")
        args = parser.parse_args()

        setup_logging(args.verbose)
        check_dependencies()
        config = load_config()

        if args.verbose:
            logging.debug("Verbose mode enabled.")
            # Enable verbose downloader output
            if "downloader_args" in config:
                config["downloader_args"]["quiet"] = False
                config["downloader_args"]["no_warnings"] = False
                config["downloader_args"]["verbose"] = True # Force yt-dlp verbose
        
        logging.info(f"Loaded configuration.")

        input_arg = args.input
        work_dir = Path.cwd()
        
        # Initialize Components
        downloader = Downloader(config)
        transcriber = Transcriber(config["whisper_url"])
        summarizer = Summarizer(config["ollama_url"], config["summarize_model"])

        # --- Step 1: Input Handling (Download or Local) ---
        temp_download_dir = None
        
        if input_arg.startswith("http://") or input_arg.startswith("https://"):
            try:
                # Use a temporary directory for the initial download to keep things clean
                temp_download_dir = Path(tempfile.mkdtemp())
                audio_path = downloader.download(input_arg, temp_download_dir)
                original_filename = audio_path.name
            except Exception as e:
                logging.error(f"Download Failed: {e}")
                notify("Download Failed", str(e))
                sys.exit(1)
        else:
            audio_path = Path(input_arg).resolve()
            if not audio_path.exists():
                logging.error(f"File not found: {audio_path}")
                sys.exit(1)
            original_filename = audio_path.name

        # --- Step 2: Workspace Creation ---
        # Create slug from filename (without extension)
        slug_base = slugify(Path(original_filename).stem)
        output_base_dir = Path(config.get("output_directory", "output/"))
        slug_dir = output_base_dir / slug_base
        
        if slug_dir.exists():
            logging.warning(f"Directory '{slug_dir.name}' already exists. Merging/Overwriting.")
        else:
            slug_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Created workspace: {slug_dir}")

        # Move/Copy audio file to workspace
        final_audio_path = slug_dir / original_filename
        
        # If downloaded, move it. If local, copy it (preserve original) or move? 
        # The shell script logic implied moving input file to workspace. 
        # Let's Move for consistency with pipeline.sh, unless it's a download from temp.
        
        if temp_download_dir:
            shutil.move(str(audio_path), str(final_audio_path))
            shutil.rmtree(temp_download_dir)
        else:
            # If local file is NOT already in the slug dir, move it there
            if audio_path.parent != slug_dir:
                shutil.move(str(audio_path), str(final_audio_path))
            else:
                final_audio_path = audio_path # Already there

        # --- Step 3: Transcription ---
        try:
            transcript_path, _ = transcriber.transcribe(final_audio_path)
        except Exception as e:
            logging.error(f"Transcription failed: {e}")
            notify("Transcription Failed", str(e))
            sys.exit(1)

        # --- Step 4: Summarization ---
        if not args.no_summary:
            summary_path = slug_dir / f"{slug_base}_summary.md"
            try:
                summarizer.summarize(transcript_path, summary_path)
                notify("Pipeline Complete", f"Processed {original_filename}")
            except Exception as e:
                logging.error(f"Summarization failed: {e}")
                notify("Summarization Failed", str(e))
                # Don't exit, we partially succeeded
        else:
            logging.info("Skipping summary generation.")
            notify("Transcription Complete", f"Transcribed {original_filename}")

        print("\n" + "="*40)
        print("SUCCESS")
        print("="*40)
        print(f"Workspace: {slug_dir}")
        print(f" - Audio:      {final_audio_path.name}")
        print(f" - Transcript: {transcript_path.name}")
        if not args.no_summary and 'summary_path' in locals():
             print(f" - Summary:    {summary_path.name}")
        print("="*40)

    except KeyboardInterrupt:
        logging.info("Process interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logging.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
