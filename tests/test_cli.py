"""Tests for scripts.main."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.config import API_REQUEST_RETRIES, API_REQUEST_TIMEOUT_SECONDS
from scripts.main import main, resolve_video_reference
from scripts.models import TranscriptResult, VideoInfo


def _make_video_info(**overrides) -> VideoInfo:
    defaults = dict(
        id="v1",
        title="Test Video",
        channel_title="Test Channel",
        published_at="2024-01-15T00:00:00Z",
        description="",
        duration="PT10M",
        view_count=1000,
        like_count=50,
        comment_count=10,
        url="https://www.youtube.com/watch?v=v1",
    )
    defaults.update(overrides)
    return VideoInfo(**defaults)


class TestCliEnvelopePopular:
    @patch("scripts.main.get_popular_videos")
    def test_success_envelope(self, mock_popular, capsys):
        mock_popular.return_value = [_make_video_info()]
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_TEST", "--top", "1"]):
            main()

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["command"] == "popular"
        assert payload["input"]["channel_id"] == "UC_TEST"
        assert payload["input"]["top"] == 1
        assert payload["result"][0]["id"] == "v1"
        assert payload["meta"]["count"] == 1
        assert "generated_at" in payload["meta"]

    @patch("scripts.main.get_popular_videos")
    def test_output_metadata_and_file(self, mock_popular, tmp_path, capsys):
        mock_popular.return_value = [_make_video_info()]
        with patch(
            "sys.argv",
            ["youtube-scraper", "popular", "UC/test", "--output", str(tmp_path)],
        ):
            main()

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["meta"]["saved_to"]
        assert len(list(tmp_path.glob("*.json"))) == 1

    @patch("scripts.main.get_popular_videos")
    def test_unexpected_error_envelope(self, mock_popular, capsys):
        mock_popular.side_effect = RuntimeError("boom")
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_TEST"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["command"] == "popular"
        assert payload["error"]["type"] == "RuntimeError"
        assert payload["error"]["code"] == "UNEXPECTED_ERROR"
        assert payload["error"]["message"] == "boom"

    @patch("scripts.main.get_popular_videos")
    def test_default_and_custom_network_args(self, mock_popular, capsys):
        mock_popular.return_value = []
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_A"]):
            main()
        json.loads(capsys.readouterr().out)
        mock_popular.assert_called_once_with(
            "UC_A",
            top_n=10,
            max_results=500,
            retries=API_REQUEST_RETRIES,
            timeout=API_REQUEST_TIMEOUT_SECONDS,
        )

        mock_popular.reset_mock()
        mock_popular.return_value = []
        with patch(
            "sys.argv",
            ["youtube-scraper", "popular", "UC_B", "--timeout", "12.5", "--retries", "5"],
        ):
            main()
        json.loads(capsys.readouterr().out)
        mock_popular.assert_called_once_with(
            "UC_B",
            top_n=10,
            max_results=500,
            retries=5,
            timeout=12.5,
        )


class TestCliEnvelopeTranscript:
    @patch("scripts.main.get_transcript")
    def test_success_envelope(self, mock_transcript, capsys):
        mock_transcript.return_value = TranscriptResult(
            video_id="vid1",
            language="en",
            text="hello",
            segments=[{"text": "hello", "start": 0, "duration": 1}],
        )
        with patch("sys.argv", ["youtube-scraper", "transcript", "vid1", "--lang", "en,ja"]):
            main()

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["command"] == "transcript"
        assert payload["input"]["video_ref"] == "vid1"
        assert payload["input"]["video_id"] == "vid1"
        assert payload["input"]["languages"] == ["en", "ja"]
        assert payload["result"]["text"] == "hello"
        mock_transcript.assert_called_once_with("vid1", languages=["en", "ja"])

    @patch("scripts.main.get_transcript")
    def test_accepts_youtube_url(self, mock_transcript, capsys):
        mock_transcript.return_value = TranscriptResult(
            video_id="abc123def45",
            language="en",
            text="hello",
            segments=[],
        )
        with patch(
            "sys.argv",
            [
                "youtube-scraper",
                "transcript",
                "https://www.youtube.com/watch?v=abc123def45",
                "--lang",
                "en",
            ],
        ):
            main()

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["input"]["video_ref"] == "https://www.youtube.com/watch?v=abc123def45"
        assert payload["input"]["video_id"] == "abc123def45"
        mock_transcript.assert_called_once_with("abc123def45", languages=["en"])

    @patch("scripts.main.get_transcript")
    def test_transcript_output_writes_txt(self, mock_transcript, tmp_path, capsys):
        mock_transcript.return_value = TranscriptResult(
            video_id="abc123def45",
            language="en",
            text="hello world",
            segments=[],
        )
        with patch("sys.argv", ["youtube-scraper", "transcript", "abc123def45", "--output", str(tmp_path)]):
            main()

        payload = json.loads(capsys.readouterr().out)
        saved_to = payload["meta"]["saved_to"]
        assert saved_to.endswith(".txt")
        assert Path(saved_to).read_text(encoding="utf-8") == "hello world"
        assert len(list(tmp_path.glob("*.txt"))) == 1

    def test_resolve_video_reference_variants(self):
        assert resolve_video_reference("abc123def45") == "abc123def45"
        assert (
            resolve_video_reference("https://youtu.be/abc123def45?t=12")
            == "abc123def45"
        )
        assert (
            resolve_video_reference("https://www.youtube.com/shorts/abc123def45")
            == "abc123def45"
        )

    def test_invalid_video_reference_is_argument_error(self, capsys):
        with patch("sys.argv", ["youtube-scraper", "transcript", "https://www.youtube.com/channel/UC_TEST"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "INVALID_ARGUMENTS"

    @patch("scripts.main.get_transcript")
    def test_transcript_missing_envelope(self, mock_transcript, capsys):
        mock_transcript.return_value = TranscriptResult(video_id="vid1", error="No transcript")
        with patch("sys.argv", ["youtube-scraper", "transcript", "vid1"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["command"] == "transcript"
        assert payload["error"]["code"] == "TRANSCRIPT_UNAVAILABLE"
        assert payload["error"]["message"] == "No transcript"


class TestCliEnvelopeFull:
    @patch("scripts.main.get_transcripts_batch")
    @patch("scripts.main.get_popular_videos")
    def test_success_envelope(self, mock_popular, mock_transcripts, capsys):
        mock_popular.return_value = [_make_video_info()]
        mock_transcripts.return_value = [
            TranscriptResult(video_id="v1", language="en", text="Transcript text", segments=[])
        ]
        with patch("sys.argv", ["youtube-scraper", "full", "UC_TEST", "--top", "1"]):
            main()

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["command"] == "full"
        assert payload["input"]["channel_id"] == "UC_TEST"
        assert payload["result"][0]["id"] == "v1"
        assert payload["result"][0]["transcript"] == "Transcript text"
        assert payload["meta"]["count"] == 1

    @patch("scripts.main.get_popular_videos")
    def test_unexpected_error_envelope(self, mock_popular, capsys):
        mock_popular.side_effect = ValueError("bad channel")
        with patch("sys.argv", ["youtube-scraper", "full", "UC_BAD"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["command"] == "full"
        assert payload["error"]["type"] == "ValueError"
        assert payload["error"]["message"] == "bad channel"


class TestCliArgParsing:
    def test_no_command_is_json_error(self, capsys):
        with patch("sys.argv", ["youtube-scraper"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "INVALID_ARGUMENTS"

    def test_invalid_positive_number_is_json_error(self, capsys):
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_TEST", "--top", "0"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "INVALID_ARGUMENTS"

    def test_unknown_command_is_json_error(self, capsys):
        with patch("sys.argv", ["youtube-scraper", "nope"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "INVALID_ARGUMENTS"

    def test_help_uses_placeholders(self, capsys):
        with patch("sys.argv", ["youtube-scraper", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        output = capsys.readouterr().out
        assert "<CHANNEL_ID>" in output
        assert "<VIDEO_ID_OR_URL>" in output
