"""Tests for youtube_scraper.cli module."""

import json
from unittest.mock import patch

import pytest

from youtube_scraper.cli import main
from youtube_scraper.models import VideoInfo, TranscriptResult


def _make_video_info(**overrides) -> VideoInfo:
    defaults = dict(
        id="v1", title="Test Video", channel_title="Test Channel",
        published_at="2024-01-15T00:00:00Z", description="",
        duration="PT10M", view_count=1000, like_count=50, comment_count=10,
        url="https://www.youtube.com/watch?v=v1",
    )
    defaults.update(overrides)
    return VideoInfo(**defaults)


class TestCliPopular:
    @patch("youtube_scraper.cli.get_popular_videos")
    def test_json_output(self, mock_popular, capsys):
        mock_popular.return_value = [_make_video_info()]
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_test", "--top", "1", "--json"]):
            main()

        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["id"] == "v1"
        assert data[0]["view_count"] == 1000

    @patch("youtube_scraper.cli.get_popular_videos")
    def test_table_output(self, mock_popular, capsys):
        mock_popular.return_value = [_make_video_info()]
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_test", "--top", "1"]):
            main()

        output = capsys.readouterr().out
        assert "Test Video" in output

    @patch("youtube_scraper.cli.get_popular_videos")
    def test_default_args(self, mock_popular):
        mock_popular.return_value = []
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_abc", "--json"]):
            main()

        mock_popular.assert_called_once_with("UC_abc", top_n=10, max_results=500)

    @patch("youtube_scraper.cli.get_popular_videos")
    def test_custom_scan_arg(self, mock_popular):
        mock_popular.return_value = []
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_abc", "--scan", "100", "--json"]):
            main()

        mock_popular.assert_called_once_with("UC_abc", top_n=10, max_results=100)

    @patch("youtube_scraper.cli.get_popular_videos")
    def test_empty_results_json(self, mock_popular, capsys):
        mock_popular.return_value = []
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_abc", "--json"]):
            main()

        assert json.loads(capsys.readouterr().out) == []

    @patch("youtube_scraper.cli.get_popular_videos")
    def test_json_output_with_output_dir_keeps_stdout_machine_readable(self, mock_popular, tmp_path, capsys):
        mock_popular.return_value = [_make_video_info()]
        with patch(
            "sys.argv",
            ["youtube-scraper", "popular", "UC_test", "--json", "--output", str(tmp_path)],
        ):
            main()

        data = json.loads(capsys.readouterr().out)
        assert data[0]["id"] == "v1"
        assert len(list(tmp_path.glob("*.json"))) == 1

    @patch("youtube_scraper.cli.get_popular_videos")
    def test_output_filename_sanitizes_channel_id(self, mock_popular, tmp_path, capsys):
        mock_popular.return_value = [_make_video_info()]
        with patch(
            "sys.argv",
            ["youtube-scraper", "popular", "UC/test", "--json", "--output", str(tmp_path)],
        ):
            main()

        data = json.loads(capsys.readouterr().out)
        assert data[0]["id"] == "v1"
        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        assert "UC_test" in files[0].name

    @patch("youtube_scraper.cli.get_popular_videos")
    def test_unexpected_error_json_outputs_structured_error(self, mock_popular, capsys):
        mock_popular.side_effect = RuntimeError("boom")
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_test", "--json"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        payload = json.loads(capsys.readouterr().out)
        assert payload["error"]["type"] == "RuntimeError"
        assert payload["error"]["message"] == "boom"

    @patch("youtube_scraper.cli.get_popular_videos")
    def test_unexpected_error_plain_output_no_traceback(self, mock_popular, capsys):
        mock_popular.side_effect = RuntimeError("boom")
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_test"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        output = capsys.readouterr().out
        assert "Error: boom" in output
        assert "Traceback" not in output


class TestCliTranscript:
    @patch("youtube_scraper.cli.get_transcript")
    def test_json_output(self, mock_transcript, capsys):
        mock_transcript.return_value = TranscriptResult(
            video_id="vid1", language="en", text="Hello world",
            segments=[{"text": "Hello world", "start": 0, "duration": 1}],
        )
        with patch("sys.argv", ["youtube-scraper", "transcript", "vid1", "--json"]):
            main()

        data = json.loads(capsys.readouterr().out)
        assert data["text"] == "Hello world"

    @patch("youtube_scraper.cli.get_transcript")
    def test_error_exits_with_code_1(self, mock_transcript):
        mock_transcript.return_value = TranscriptResult(
            video_id="vid1", error="No transcript",
        )
        with patch("sys.argv", ["youtube-scraper", "transcript", "vid1"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    @patch("youtube_scraper.cli.get_transcript")
    def test_error_json_outputs_valid_json(self, mock_transcript, capsys):
        mock_transcript.return_value = TranscriptResult(
            video_id="vid1", error="No transcript",
        )
        with patch("sys.argv", ["youtube-scraper", "transcript", "vid1", "--json"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        data = json.loads(capsys.readouterr().out)
        assert data["error"] == "No transcript"
        assert data["video_id"] == "vid1"

    @patch("youtube_scraper.cli.get_transcript")
    def test_lang_option_passed(self, mock_transcript, capsys):
        mock_transcript.return_value = TranscriptResult(
            video_id="vid1", language="ja", text="test", segments=[],
        )
        with patch("sys.argv", ["youtube-scraper", "transcript", "vid1", "--lang", "ja,en", "--json"]):
            main()

        mock_transcript.assert_called_once_with("vid1", languages=["ja", "en"])

    @patch("youtube_scraper.cli.get_transcript")
    def test_lang_option_normalizes_values(self, mock_transcript, capsys):
        mock_transcript.return_value = TranscriptResult(
            video_id="vid1", language="ja", text="test", segments=[],
        )
        with patch(
            "sys.argv",
            ["youtube-scraper", "transcript", "vid1", "--lang", " ja, , en , ", "--json"],
        ):
            main()

        mock_transcript.assert_called_once_with("vid1", languages=["ja", "en"])

    @patch("youtube_scraper.cli.get_transcript")
    def test_plain_text_output(self, mock_transcript, capsys):
        mock_transcript.return_value = TranscriptResult(
            video_id="vid1", language="en", text="Some transcript text", segments=[],
        )
        with patch("sys.argv", ["youtube-scraper", "transcript", "vid1"]):
            main()

        output = capsys.readouterr().out
        assert "Some transcript text" in output
        assert "Language" in output


class TestCliFull:
    @patch("youtube_scraper.cli.get_transcripts_batch")
    @patch("youtube_scraper.cli.get_popular_videos")
    def test_json_output_merges_transcripts(self, mock_popular, mock_transcripts, capsys):
        mock_popular.return_value = [_make_video_info()]
        mock_transcripts.return_value = [
            TranscriptResult(video_id="v1", language="en", text="Transcript text here", segments=[]),
        ]
        with patch("sys.argv", ["youtube-scraper", "full", "UC_test", "--top", "1", "--json"]):
            main()

        data = json.loads(capsys.readouterr().out)
        assert data[0]["transcript"] == "Transcript text here"
        assert data[0]["transcript_language"] == "en"
        # VideoInfo fields should also be present
        assert data[0]["id"] == "v1"
        assert data[0]["view_count"] == 1000

    @patch("youtube_scraper.cli.get_transcripts_batch")
    @patch("youtube_scraper.cli.get_popular_videos")
    def test_json_with_transcript_error(self, mock_popular, mock_transcripts, capsys):
        mock_popular.return_value = [_make_video_info()]
        mock_transcripts.return_value = [
            TranscriptResult(video_id="v1", error="Subtitles disabled"),
        ]
        with patch("sys.argv", ["youtube-scraper", "full", "UC_test", "--top", "1", "--json"]):
            main()

        data = json.loads(capsys.readouterr().out)
        assert data[0]["transcript"] is None
        assert data[0]["transcript_error"] == "Subtitles disabled"

    @patch("youtube_scraper.cli.get_transcripts_batch")
    @patch("youtube_scraper.cli.get_popular_videos")
    def test_lang_option_normalizes_values(self, mock_popular, mock_transcripts, capsys):
        mock_popular.return_value = [_make_video_info()]
        mock_transcripts.return_value = [
            TranscriptResult(video_id="v1", language="ja", text="ok", segments=[]),
        ]
        with patch(
            "sys.argv",
            ["youtube-scraper", "full", "UC_test", "--lang", " ja, , en , ", "--json"],
        ):
            main()

        mock_transcripts.assert_called_once_with(["v1"], languages=["ja", "en"])

    @patch("youtube_scraper.cli.get_popular_videos")
    def test_unexpected_error_json_outputs_structured_error(self, mock_popular, capsys):
        mock_popular.side_effect = ValueError("Channel not found: UC_bad")
        with patch("sys.argv", ["youtube-scraper", "full", "UC_bad", "--json"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        payload = json.loads(capsys.readouterr().out)
        assert payload["error"]["type"] == "ValueError"
        assert payload["error"]["message"] == "Channel not found: UC_bad"


class TestCliArgParsing:
    def test_no_command_exits(self):
        with patch("sys.argv", ["youtube-scraper"]):
            with pytest.raises(SystemExit):
                main()

    def test_help_exits(self):
        with patch("sys.argv", ["youtube-scraper", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_top_must_be_positive(self):
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_test", "--top", "0"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

    def test_scan_must_be_positive(self):
        with patch("sys.argv", ["youtube-scraper", "popular", "UC_test", "--scan", "-1"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
