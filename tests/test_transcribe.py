import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import sys
import os
from pathlib import Path

# Add parent directory to path to import transcribe
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import transcribe
from transcribe import load_config, Downloader, Transcriber, Summarizer, DEFAULT_CONFIG

class TestConfiguration(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data='{"output_directory": "custom_output/"}')
    @patch("pathlib.Path.exists", return_value=True)
    def test_load_config_custom(self, mock_exists, mock_file):
        config = load_config()
        self.assertEqual(config["output_directory"], "custom_output/")
        self.assertEqual(config["whisper_url"], DEFAULT_CONFIG["whisper_url"])

    @patch("pathlib.Path.exists", return_value=False)
    def test_load_config_defaults(self, mock_exists):
        config = load_config()
        self.assertEqual(config, DEFAULT_CONFIG)

    @patch("builtins.open", new_callable=mock_open, read_data='{"output_directory": "fallback_output/"}')
    @patch("pathlib.Path.exists")
    def test_load_config_fallback(self, mock_exists, mock_file):
        # First path (cwd) doesn't exist, second (home) does
        # Note: Path.exists might be called more times depending on implementation details of Path
        # So using side_effect with a list might be brittle if Path() constructor checks existence or something
        # Better to check the path argument if possible, or assume the order of checks in load_config
        
        def side_effect(self):
            if str(self) == str(Path.cwd() / transcribe.CONFIG_FILE_NAME):
                return False
            if str(self) == str(Path.home() / ".config" / "transcribe" / transcribe.CONFIG_FILE_NAME):
                return True
            return False
            
        # Using a simple side_effect list assumes exact call order and count
        mock_exists.side_effect = [False, True] 
        
        config = load_config()
        self.assertEqual(config["output_directory"], "fallback_output/")

    def test_setup_logging_verbose(self):
        with patch("logging.basicConfig") as mock_logging:
            transcribe.setup_logging(verbose=True)
            mock_logging.assert_called_with(
                level=transcribe.logging.DEBUG,
                format="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S"
            )

class TestDownloader(unittest.TestCase):
    def setUp(self):
        self.config = DEFAULT_CONFIG.copy()
        self.downloader = Downloader(self.config)

    @patch("transcribe.yt_dlp.YoutubeDL")
    def test_download_success(self, mock_ydl_class):
        # Setup mock behavior
        mock_ydl_instance = mock_ydl_class.return_value
        mock_ydl_instance.__enter__.return_value = mock_ydl_instance
        
        # Mock extract_info and prepare_filename
        mock_info = {"title": "Test Video", "ext": "mp3"}
        mock_ydl_instance.extract_info.return_value = mock_info
        mock_ydl_instance.prepare_filename.return_value = "Test Video.mp3"

        # Mock Path.glob to find the downloaded file
        mock_output_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.name = "Test Video.mp3"
        mock_file.stat.return_value.st_mtime = 1000
        
        # Simulate finding the file
        mock_output_dir.glob.return_value = [mock_file]
        
        # Execute
        result = self.downloader.download("http://example.com/video", mock_output_dir)
        
        # Verify
        self.assertEqual(result, mock_file)
        mock_output_dir.mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_ydl_class.assert_called()

    @patch("transcribe.yt_dlp.YoutubeDL")
    def test_download_file_not_found(self, mock_ydl_class):
        mock_ydl_instance = mock_ydl_class.return_value
        mock_ydl_instance.__enter__.return_value = mock_ydl_instance
        mock_ydl_instance.extract_info.return_value = {}
        mock_ydl_instance.prepare_filename.return_value = "missing.mp3"

        mock_output_dir = MagicMock(spec=Path)
        mock_output_dir.glob.return_value = []  # No file found

        with self.assertRaises(FileNotFoundError):
            self.downloader.download("http://example.com/video", mock_output_dir)


class TestTranscriber(unittest.TestCase):
    def setUp(self):
        self.transcriber = Transcriber("http://fake-whisper:8080")
        self.audio_path = Path("/tmp/test/audio.mp3")

    @patch("subprocess.run")
    @patch("requests.post")
    @patch("builtins.open", new_callable=mock_open)
    def test_transcribe_success(self, mock_file, mock_post, mock_subprocess):
        # Mock FFmpeg success
        mock_subprocess.return_value.returncode = 0
        
        # Mock Requests success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "Hello world",
            "segments": [{"start": 0, "end": 1, "text": "Hello world"}]
        }
        mock_post.return_value = mock_response

        # Execute
        txt_path, json_path = self.transcriber.transcribe(self.audio_path)

        # Verify FFmpeg call
        expected_wav = self.audio_path.with_suffix(".wav")
        mock_subprocess.assert_called_with([
            "ffmpeg", "-y", "-i", str(self.audio_path),
            "-ar", "16000", "-ac", "1", "-loglevel", "error",
            str(expected_wav)
        ], check=True)

        # Verify API call
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args[0][0], "http://fake-whisper:8080")

        # Verify file writes (2 calls: text and json)
        # Note: 'open' is also called to read the wav file, so check write calls specifically
        handle = mock_file()
        self.assertTrue(handle.write.called)
        
        # Check expected return paths
        self.assertEqual(txt_path, self.audio_path.parent / "audio.txt")
        self.assertEqual(json_path, self.audio_path.parent / "audio_timestamps.json")


class TestSummarizer(unittest.TestCase):
    def setUp(self):
        self.summarizer = Summarizer("http://fake-ollama:11434", "qwen2.5")
        self.transcript_path = Path("/tmp/test/transcript.txt")
        self.output_path = Path("/tmp/test/summary.md")

    @patch("requests.post")
    @patch("builtins.open", new_callable=mock_open, read_data="This is the transcript.")
    def test_summarize_success(self, mock_file, mock_post):
        # Mock Requests success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "# Summary\n\n- Point 1"}
        mock_post.return_value = mock_response

        # Execute
        self.summarizer.summarize(self.transcript_path, self.output_path)

        # Verify
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['model'], "qwen2.5")
        self.assertIn("This is the transcript.", payload['prompt'])

        # Verify write
        handle = mock_file()
        handle.write.assert_called_with("# Summary\n\n- Point 1")

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("builtins.open", new_callable=mock_open, read_data="Transcript text")
    def test_summarize_gemini_success(self, mock_file, mock_which, mock_subprocess):
        # Setup
        summarizer = Summarizer("http://unused", "gemini")
        mock_which.return_value = "/usr/bin/gemini"
        
        mock_process = MagicMock()
        mock_process.stdout = "# Gemini Summary"
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        # Execute
        summarizer.summarize(Path("transcript.txt"), Path("summary.md"))
        
        # Verify
        mock_which.assert_called_with("gemini")
        mock_subprocess.assert_called_once()
        args, kwargs = mock_subprocess.call_args
        self.assertEqual(args[0], ["gemini", "-p", transcribe.SYSTEM_PROMPT])
        self.assertEqual(kwargs['input'], "Transcript text")
        self.assertEqual(kwargs['encoding'], "utf-8")
        
        # Verify write
        handle = mock_file()
        handle.write.assert_called_with("# Gemini Summary")

if __name__ == "__main__":
    unittest.main()
