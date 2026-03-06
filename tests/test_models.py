"""Tests for youtube_scraper.models module."""

from youtube_scraper.models import (
    ChannelInfo,
    VideoInfo,
    TranscriptResult,
    VideoWithTranscript,
)


class TestChannelInfo:
    def test_from_api_response(self):
        item = {
            "id": "UC_abc",
            "snippet": {"title": "Chan", "description": "Desc"},
            "contentDetails": {"relatedPlaylists": {"uploads": "UU_abc"}},
            "statistics": {"subscriberCount": "1000", "videoCount": "50"},
        }
        ch = ChannelInfo.from_api_response(item)
        assert ch.id == "UC_abc"
        assert ch.title == "Chan"
        assert ch.subscriber_count == 1000

    def test_from_api_response_missing_stats(self):
        item = {
            "id": "UC_x",
            "snippet": {"title": "X"},
            "contentDetails": {"relatedPlaylists": {"uploads": "UU_x"}},
            "statistics": {},
        }
        ch = ChannelInfo.from_api_response(item)
        assert ch.subscriber_count == 0
        assert ch.video_count == 0
        assert ch.description == ""

    def test_to_dict(self):
        ch = ChannelInfo(id="UC_1", title="T", description="D",
                         subscriber_count=100, video_count=10,
                         uploads_playlist_id="UU_1")
        d = ch.to_dict()
        assert d == {
            "id": "UC_1", "title": "T", "description": "D",
            "subscriber_count": 100, "video_count": 10,
            "uploads_playlist_id": "UU_1",
        }


class TestVideoInfo:
    def test_from_api_response(self):
        item = {
            "id": "v1",
            "snippet": {
                "title": "Title",
                "channelTitle": "Chan",
                "publishedAt": "2024-01-01T00:00:00Z",
                "description": "Desc",
            },
            "contentDetails": {"duration": "PT5M"},
            "statistics": {"viewCount": "999", "likeCount": "10", "commentCount": "5"},
        }
        v = VideoInfo.from_api_response(item)
        assert v.id == "v1"
        assert v.view_count == 999
        assert v.url == "https://www.youtube.com/watch?v=v1"

    def test_from_api_response_missing_fields(self):
        item = {
            "id": "v2",
            "snippet": {"title": "T", "publishedAt": "2024-01-01T00:00:00Z"},
            "statistics": {},
        }
        v = VideoInfo.from_api_response(item)
        assert v.channel_title == ""
        assert v.duration == ""
        assert v.view_count == 0

    def test_to_dict(self):
        v = VideoInfo(id="v1", title="T", channel_title="C",
                      published_at="2024-01-01", description="",
                      duration="PT5M", view_count=1, like_count=0,
                      comment_count=0, url="https://youtube.com/watch?v=v1")
        d = v.to_dict()
        assert d["id"] == "v1"
        assert isinstance(d, dict)


class TestTranscriptResult:
    def test_ok_when_successful(self):
        t = TranscriptResult(video_id="v1", language="en", text="hello", segments=[])
        assert t.ok is True

    def test_not_ok_when_error(self):
        t = TranscriptResult(video_id="v1", error="fail")
        assert t.ok is False

    def test_not_ok_when_no_text(self):
        t = TranscriptResult(video_id="v1")
        assert t.ok is False

    def test_to_dict(self):
        t = TranscriptResult(video_id="v1", language="en", text="hi", segments=[])
        d = t.to_dict()
        assert d["video_id"] == "v1"
        assert d["error"] is None
        assert d["error_code"] is None

    def test_error_code_roundtrip(self):
        t = TranscriptResult(video_id="v1", error="fail", error_code="UNKNOWN_ERROR")
        d = t.to_dict()
        assert d["error_code"] == "UNKNOWN_ERROR"


class TestVideoWithTranscript:
    def test_to_dict_merges_fields(self):
        v = VideoInfo(id="v1", title="T", channel_title="C",
                      published_at="2024-01-01", description="",
                      duration="PT5M", view_count=100, like_count=5,
                      comment_count=0, url="https://youtube.com/watch?v=v1")
        t = TranscriptResult(video_id="v1", language="en", text="hello", segments=[])
        vt = VideoWithTranscript(video=v, transcript=t)

        d = vt.to_dict()
        # Should have video fields at top level
        assert d["id"] == "v1"
        assert d["view_count"] == 100
        # Plus transcript fields
        assert d["transcript"] == "hello"
        assert d["transcript_language"] == "en"
        assert d["transcript_error"] is None

    def test_to_dict_with_error(self):
        v = VideoInfo(id="v1", title="T", channel_title="C",
                      published_at="2024-01-01", description="",
                      duration="PT5M", view_count=100, like_count=5,
                      comment_count=0, url="https://youtube.com/watch?v=v1")
        t = TranscriptResult(video_id="v1", error="disabled")
        vt = VideoWithTranscript(video=v, transcript=t)

        d = vt.to_dict()
        assert d["transcript"] is None
        assert d["transcript_error"] == "disabled"
