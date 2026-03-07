"""Tests for youtube_scraper.client module."""

import pytest

from youtube_scraper.client import (
    get_channel_info,
    get_channel_videos,
    get_video_details,
    get_popular_videos,
)
from youtube_scraper.config import API_REQUEST_RETRIES
from youtube_scraper.models import ChannelInfo, VideoInfo
from tests.conftest import (
    make_channel_response,
    make_playlist_items_response,
    make_video_details_response,
    build_mock_service,
)


class TestGetChannelInfo:
    def test_returns_channel_info_dataclass(self):
        service = build_mock_service(
            channel_response=make_channel_response(
                channel_id="UC_abc",
                title="My Channel",
                uploads_playlist_id="UU_abc",
                subscriber_count="50000",
                video_count="200",
            )
        )
        result = get_channel_info("UC_abc", service=service)

        assert isinstance(result, ChannelInfo)
        assert result.id == "UC_abc"
        assert result.title == "My Channel"
        assert result.uploads_playlist_id == "UU_abc"
        assert result.subscriber_count == 50000
        assert result.video_count == 200

    def test_raises_for_unknown_channel(self):
        service = build_mock_service(channel_response={"items": []})

        with pytest.raises(ValueError, match="Channel not found"):
            get_channel_info("UC_nonexistent", service=service)

    def test_handles_missing_optional_fields(self):
        resp = {
            "items": [{
                "id": "UC_x",
                "snippet": {"title": "X"},
                "contentDetails": {"relatedPlaylists": {"uploads": "UU_x"}},
                "statistics": {},
            }],
        }
        service = build_mock_service(channel_response=resp)
        result = get_channel_info("UC_x", service=service)

        assert result.subscriber_count == 0
        assert result.video_count == 0
        assert result.description == ""

    def test_to_dict_roundtrip(self):
        service = build_mock_service(
            channel_response=make_channel_response(channel_id="UC_rt")
        )
        result = get_channel_info("UC_rt", service=service)
        d = result.to_dict()

        assert d["id"] == "UC_rt"
        assert isinstance(d, dict)


class TestGetChannelVideos:
    def test_single_page(self):
        service = build_mock_service(
            channel_response=make_channel_response(),
            playlist_responses=[
                make_playlist_items_response(["v1", "v2", "v3"]),
            ],
        )
        result = get_channel_videos("UC_test", max_results=50, service=service)
        assert result == ["v1", "v2", "v3"]

    def test_multiple_pages(self):
        service = build_mock_service(
            channel_response=make_channel_response(),
            playlist_responses=[
                make_playlist_items_response(["v1", "v2"], next_page_token="page2"),
                make_playlist_items_response(["v3", "v4"]),
            ],
        )
        result = get_channel_videos("UC_test", max_results=50, service=service)
        assert result == ["v1", "v2", "v3", "v4"]

    def test_respects_max_results_truncates(self):
        service = build_mock_service(
            channel_response=make_channel_response(),
            playlist_responses=[
                make_playlist_items_response(["v1", "v2", "v3"]),
            ],
        )
        result = get_channel_videos("UC_test", max_results=2, service=service)
        assert len(result) == 2
        assert result == ["v1", "v2"]

    def test_max_results_across_pages(self):
        service = build_mock_service(
            channel_response=make_channel_response(),
            playlist_responses=[
                make_playlist_items_response(["v1", "v2"], next_page_token="p2"),
                make_playlist_items_response(["v3", "v4"]),
            ],
        )
        result = get_channel_videos("UC_test", max_results=3, service=service)
        assert result == ["v1", "v2", "v3"]

    def test_empty_playlist(self):
        service = build_mock_service(
            channel_response=make_channel_response(),
            playlist_responses=[
                make_playlist_items_response([]),
            ],
        )
        result = get_channel_videos("UC_test", max_results=50, service=service)
        assert result == []


class TestGetVideoDetails:
    def test_returns_video_info_dataclasses(self):
        videos = [
            {"id": "v1", "title": "Video One", "view_count": 1000, "like_count": 50},
            {"id": "v2", "title": "Video Two", "view_count": 2000, "like_count": 100},
        ]
        service = build_mock_service(
            video_responses=[make_video_details_response(videos)],
        )
        result = get_video_details(["v1", "v2"], service=service)

        assert len(result) == 2
        assert all(isinstance(v, VideoInfo) for v in result)
        assert result[0].id == "v1"
        assert result[0].title == "Video One"
        assert result[0].view_count == 1000
        assert result[0].url == "https://www.youtube.com/watch?v=v1"

    def test_empty_list_returns_empty(self):
        result = get_video_details([])
        assert result == []

    def test_single_batch_boundary(self):
        ids = [f"v{i}" for i in range(50)]
        videos = [{"id": f"v{i}", "title": f"V{i}", "view_count": i, "like_count": 0}
                  for i in range(50)]
        service = build_mock_service(
            video_responses=[make_video_details_response(videos)],
        )
        result = get_video_details(ids, service=service)
        assert len(result) == 50

    def test_batches_large_requests(self):
        ids = [f"v{i}" for i in range(60)]
        batch1 = [{"id": f"v{i}", "title": f"V{i}", "view_count": i, "like_count": 0}
                  for i in range(50)]
        batch2 = [{"id": f"v{i}", "title": f"V{i}", "view_count": i, "like_count": 0}
                  for i in range(50, 60)]
        service = build_mock_service(
            video_responses=[
                make_video_details_response(batch1),
                make_video_details_response(batch2),
            ],
        )
        result = get_video_details(ids, service=service)
        assert len(result) == 60

    def test_handles_missing_statistics(self):
        resp = {
            "items": [{
                "id": "v1",
                "snippet": {
                    "title": "No Stats",
                    "publishedAt": "2024-01-01T00:00:00Z",
                },
                "contentDetails": {},
                "statistics": {},
            }],
        }
        service = build_mock_service(video_responses=[resp])
        result = get_video_details(["v1"], service=service)

        assert result[0].view_count == 0
        assert result[0].like_count == 0
        assert result[0].comment_count == 0

    def test_to_dict(self):
        videos = [{"id": "v1", "title": "T", "view_count": 1, "like_count": 0}]
        service = build_mock_service(
            video_responses=[make_video_details_response(videos)],
        )
        result = get_video_details(["v1"], service=service)
        d = result[0].to_dict()
        assert d["id"] == "v1"
        assert isinstance(d["view_count"], int)


class TestGetPopularVideos:
    def test_returns_sorted_by_views_descending(self):
        videos = [
            {"id": "v1", "title": "Low", "view_count": 100, "like_count": 5},
            {"id": "v2", "title": "High", "view_count": 9999, "like_count": 500},
            {"id": "v3", "title": "Mid", "view_count": 1000, "like_count": 50},
        ]
        service = build_mock_service(
            channel_response=make_channel_response(),
            playlist_responses=[
                make_playlist_items_response(["v1", "v2", "v3"]),
            ],
            video_responses=[make_video_details_response(videos)],
        )
        result = get_popular_videos("UC_test", top_n=3, max_results=50, service=service)

        assert [v.id for v in result] == ["v2", "v3", "v1"]
        assert result[0].view_count == 9999

    def test_top_n_limits_output(self):
        videos = [
            {"id": f"v{i}", "title": f"V{i}", "view_count": i * 100, "like_count": 0}
            for i in range(5)
        ]
        service = build_mock_service(
            channel_response=make_channel_response(),
            playlist_responses=[
                make_playlist_items_response([f"v{i}" for i in range(5)]),
            ],
            video_responses=[make_video_details_response(videos)],
        )
        result = get_popular_videos("UC_test", top_n=2, max_results=50, service=service)

        assert len(result) == 2
        assert result[0].id == "v4"
        assert result[1].id == "v3"

    def test_top_n_greater_than_available(self):
        videos = [
            {"id": "v1", "title": "A", "view_count": 100, "like_count": 0},
            {"id": "v2", "title": "B", "view_count": 200, "like_count": 0},
        ]
        service = build_mock_service(
            channel_response=make_channel_response(),
            playlist_responses=[
                make_playlist_items_response(["v1", "v2"]),
            ],
            video_responses=[make_video_details_response(videos)],
        )
        result = get_popular_videos("UC_test", top_n=10, max_results=50, service=service)

        assert len(result) == 2
        assert result[0].id == "v2"

    def test_returns_video_info_instances(self):
        videos = [{"id": "v1", "title": "X", "view_count": 1, "like_count": 0}]
        service = build_mock_service(
            channel_response=make_channel_response(),
            playlist_responses=[make_playlist_items_response(["v1"])],
            video_responses=[make_video_details_response(videos)],
        )
        result = get_popular_videos("UC_test", top_n=1, max_results=50, service=service)
        assert isinstance(result[0], VideoInfo)

class TestRequestReliability:
    def test_execute_uses_default_retries(self):
        service = build_mock_service(channel_response=make_channel_response())

        get_channel_info("UC_retry", service=service)

        service.channels().list.return_value.execute.assert_called_once_with(
            num_retries=API_REQUEST_RETRIES
        )

    def test_timeout_error_has_actionable_message(self):
        service = build_mock_service()
        service.channels().list.return_value.execute.side_effect = TimeoutError("raw timeout")

        with pytest.raises(TimeoutError, match="network/proxy"):
            get_channel_info("UC_timeout", service=service)

