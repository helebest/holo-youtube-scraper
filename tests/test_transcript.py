"""Tests for scripts.transcript."""

from unittest.mock import MagicMock, patch

import pytest
from youtube_transcript_api._errors import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)

import scripts.transcript as transcript_mod
from scripts.models import TranscriptResult
from scripts.transcript import DEFAULT_LANGUAGES, get_transcript, get_transcripts_batch


def _make_snippet(text="test", start=0.0, duration=1.0):
    """Create a mock transcript snippet with .text, .start, .duration."""
    s = MagicMock()
    s.text = text
    s.start = start
    s.duration = duration
    return s


def _make_mock_api(language_code="en", snippets=None):
    """Build a mock YouTubeTranscriptApi instance."""
    if snippets is None:
        snippets = [_make_snippet()]

    api = MagicMock()
    transcript_obj = MagicMock()
    transcript_obj.language_code = language_code
    fetched = MagicMock()
    # Must support repeated iteration (text join + segments build)
    fetched.__iter__ = lambda self: iter(snippets)

    transcript_obj.fetch.return_value = fetched
    api.list.return_value.find_transcript.return_value = transcript_obj
    return api


class TestGetTranscript:
    def test_successful_transcript(self):
        snippets = [_make_snippet("Hello", 0.0, 1.0), _make_snippet("world", 1.0, 1.0)]
        api = _make_mock_api("en", snippets)

        result = get_transcript("abc123", languages=["en"], api=api)

        assert isinstance(result, TranscriptResult)
        assert result.ok is True
        assert result.video_id == "abc123"
        assert result.language == "en"
        assert result.text == "Hello world"
        assert len(result.segments) == 2
        assert result.error is None

    def test_transcript_error_returns_error_result(self):
        api = MagicMock()
        api.list.side_effect = Exception("No transcript available")

        result = get_transcript("no_sub_video", api=api)

        assert isinstance(result, TranscriptResult)
        assert result.ok is False
        assert result.video_id == "no_sub_video"
        assert result.text is None
        assert result.error == "No transcript available"
        assert result.error_code == "UNKNOWN_ERROR"

    def test_maps_typed_exception_to_stable_error(self):
        api = MagicMock()
        api.list.side_effect = TranscriptsDisabled("vid1")

        result = get_transcript("vid1", api=api)

        assert result.ok is False
        assert result.error_code == "TRANSCRIPTS_DISABLED"
        assert result.error == "Subtitles are disabled for this video."

    def test_maps_request_blocked_to_stable_error(self):
        api = MagicMock()
        api.list.side_effect = RequestBlocked("vid1")

        result = get_transcript("vid1", api=api)

        assert result.ok is False
        assert result.error_code == "REQUEST_BLOCKED"
        assert result.error == "Transcript requests are blocked from the current IP."

    @pytest.mark.parametrize(
        ("exc", "code"),
        [
            (NoTranscriptFound("vid1", ["en"], []), "NO_TRANSCRIPT_FOUND"),
            (VideoUnavailable("vid1"), "VIDEO_UNAVAILABLE"),
            (AgeRestricted("vid1"), "AGE_RESTRICTED"),
            (InvalidVideoId("vid1"), "INVALID_VIDEO_ID"),
            (CouldNotRetrieveTranscript("vid1"), "TRANSCRIPT_UNAVAILABLE"),
            (IpBlocked("vid1"), "REQUEST_BLOCKED"),
        ],
    )
    def test_maps_other_typed_exceptions(self, exc, code):
        api = MagicMock()
        api.list.side_effect = exc

        result = get_transcript("vid1", api=api)

        assert result.ok is False
        assert result.error_code == code

    def test_uses_default_languages(self):
        api = _make_mock_api("en")
        get_transcript("vid1", api=api)

        api.list.return_value.find_transcript.assert_called_once_with(DEFAULT_LANGUAGES)

    def test_custom_languages(self):
        api = _make_mock_api("ja")

        result = get_transcript("vid1", languages=["ja", "ko"], api=api)

        api.list.return_value.find_transcript.assert_called_once_with(["ja", "ko"])
        assert result.language == "ja"

    def test_find_transcript_failure(self):
        api = MagicMock()
        api.list.return_value.find_transcript.side_effect = Exception("No transcripts for languages")

        result = get_transcript("vid1", languages=["xx"], api=api)

        assert result.ok is False
        assert result.error == "No transcripts for languages"

    def test_segments_have_correct_structure(self):
        snippets = [_make_snippet("hi", 0.5, 1.2)]
        api = _make_mock_api("en", snippets)

        result = get_transcript("vid1", api=api)

        assert result.segments[0] == {"text": "hi", "start": 0.5, "duration": 1.2}

    def test_to_dict_on_success(self):
        api = _make_mock_api("en", [_make_snippet("hi")])

        result = get_transcript("vid1", api=api)
        d = result.to_dict()

        assert d["video_id"] == "vid1"
        assert d["text"] == "hi"
        assert d["error"] is None

    def test_to_dict_on_error(self):
        api = MagicMock()
        api.list.side_effect = Exception("fail")

        result = get_transcript("vid1", api=api)
        d = result.to_dict()

        assert d["text"] is None
        assert d["error"] == "fail"
        assert d["error_code"] == "UNKNOWN_ERROR"

    def test_request_blocked_uses_api_fallback_when_available(self):
        api = MagicMock()
        api.list.side_effect = RequestBlocked("vid1")
        fallback = TranscriptResult(video_id="vid1", language="en", text="fallback", segments=[])

        with patch("scripts.transcript._get_transcript_via_api", return_value=fallback):
            result = get_transcript("vid1", languages=["en"], api=api)

        assert result.text == "fallback"


class TestTranscriptApiFallback:
    def test_get_youtube_api_uses_api_key(self, monkeypatch):
        captured = {}

        def fake_build(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return "youtube"

        monkeypatch.setattr(transcript_mod.youtube_config, "get_api_key", lambda: "test-key")
        monkeypatch.setattr(transcript_mod, "build", fake_build)

        assert transcript_mod._get_youtube_api() == "youtube"
        assert captured["args"] == ("youtube", "v3")
        assert captured["kwargs"]["developerKey"] == "test-key"

    def test_get_youtube_transcript_api_returns_instance(self):
        api = transcript_mod._get_youtube_transcript_api()
        assert isinstance(api, transcript_mod.YouTubeTranscriptApi)

    def test_fallback_returns_none_when_no_captions(self):
        service = MagicMock()
        service.captions().list.return_value.execute.return_value = {"items": []}

        with patch("scripts.transcript._get_youtube_api", return_value=service):
            assert transcript_mod._get_transcript_via_api("vid1", ["en"]) is None

    def test_fallback_returns_none_when_language_not_found(self):
        service = MagicMock()
        service.captions().list.return_value.execute.return_value = {
            "items": [{"id": "cap1", "snippet": {"language": "ja"}}]
        }

        with patch("scripts.transcript._get_youtube_api", return_value=service):
            assert transcript_mod._get_transcript_via_api("vid1", ["en"]) is None

    def test_fallback_returns_none_when_cleaned_text_empty(self):
        service = MagicMock()
        service.captions().list.return_value.execute.return_value = {
            "items": [{"id": "cap1", "snippet": {"language": "en"}}]
        }
        service.captions().download.return_value.execute.return_value = b"00:00:00,000 --> 00:00:01,000\n\n"

        with patch("scripts.transcript._get_youtube_api", return_value=service):
            assert transcript_mod._get_transcript_via_api("vid1", ["en"]) is None

    def test_fallback_returns_successful_result(self):
        service = MagicMock()
        service.captions().list.return_value.execute.return_value = {
            "items": [{"id": "cap1", "snippet": {"language": "en"}}]
        }
        service.captions().download.return_value.execute.return_value = (
            b"00:00:00,000 --> 00:00:01,000\nHello\n\n00:00:01,000 --> 00:00:02,000\nWorld"
        )

        with patch("scripts.transcript._get_youtube_api", return_value=service):
            result = transcript_mod._get_transcript_via_api("vid1", ["en"])

        assert result is not None
        assert result.text == "Hello World"
        assert result.language == "en"

    def test_fallback_returns_none_on_exception(self):
        with patch("scripts.transcript._get_youtube_api", side_effect=RuntimeError("boom")):
            assert transcript_mod._get_transcript_via_api("vid1", ["en"]) is None

    def test_normalize_error_handles_empty_message(self):
        code, message = transcript_mod._normalize_error(Exception(""))
        assert code == "UNKNOWN_ERROR"
        assert message == "Unexpected error while fetching transcript."


class TestGetTranscriptsBatch:
    def test_batch_returns_list(self):
        results = get_transcripts_batch(["v1", "v2", "v3"])
        # Will fail to connect, but should return error results (not raise)
        assert len(results) == 3
        assert all(isinstance(r, TranscriptResult) for r in results)

    def test_batch_partial_failure(self):
        def list_side_effect(video_id):
            if video_id == "v2":
                raise Exception("No transcript")
            tl = MagicMock()
            obj = MagicMock()
            obj.language_code = "en"
            fetched = MagicMock()
            fetched.__iter__ = MagicMock(return_value=iter([_make_snippet("ok")]))
            obj.fetch.return_value = fetched
            tl.find_transcript.return_value = obj
            return tl

        api = MagicMock()
        api.list.side_effect = list_side_effect

        results = [get_transcript(vid, api=api) for vid in ["v1", "v2", "v3"]]

        assert results[0].ok is True
        assert results[0].text == "ok"
        assert results[1].ok is False
        assert results[1].error == "No transcript"
        assert results[2].ok is True

    def test_empty_batch(self):
        results = get_transcripts_batch([])
        assert results == []

    def test_batch_reuses_shared_api_instance(self):
        shared_api = MagicMock()
        with patch("scripts.transcript._get_youtube_transcript_api", return_value=shared_api), patch(
            "scripts.transcript.get_transcript",
            return_value=TranscriptResult(video_id="v1", text="ok"),
        ) as mocked_get:
            results = get_transcripts_batch(["v1", "v2"], languages=["en"])

        assert len(results) == 2
        mocked_get.assert_any_call("v1", ["en"], api=shared_api)
        mocked_get.assert_any_call("v2", ["en"], api=shared_api)
