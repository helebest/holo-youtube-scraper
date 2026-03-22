"""Shared test fixtures for YouTube scraper tests."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    """Ensure YOUTUBE_API_KEY is always set in tests to prevent real API calls."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-api-key-fake")


@pytest.fixture(autouse=True)
def _reset_dotenv_state():
    """Reset the _dotenv_loaded flag so each test starts clean."""
    import scripts.config as cfg

    cfg._dotenv_loaded = False
    yield
    cfg._dotenv_loaded = False


def make_channel_response(
    channel_id: str = "UC_test123",
    title: str = "Test Channel",
    uploads_playlist_id: str = "UU_test123",
    subscriber_count: str = "100000",
    video_count: str = "500",
) -> dict:
    """Build a mock channels.list API response."""
    return {
        "items": [{
            "id": channel_id,
            "snippet": {
                "title": title,
                "description": "A test channel",
            },
            "contentDetails": {
                "relatedPlaylists": {"uploads": uploads_playlist_id},
            },
            "statistics": {
                "subscriberCount": subscriber_count,
                "videoCount": video_count,
            },
        }],
    }


def make_playlist_items_response(
    video_ids: list[str],
    next_page_token: str | None = None,
) -> dict:
    """Build a mock playlistItems.list API response."""
    return {
        "items": [
            {"contentDetails": {"videoId": vid}} for vid in video_ids
        ],
        "nextPageToken": next_page_token,
    }


def make_video_details_response(videos: list[dict]) -> dict:
    """Build a mock videos.list API response.

    Each video dict should have: id, title, view_count, like_count.
    Optional: published_at, description, channel_title, comment_count, duration.
    """
    items = []
    for v in videos:
        items.append({
            "id": v["id"],
            "snippet": {
                "title": v["title"],
                "channelTitle": v.get("channel_title", "Test Channel"),
                "publishedAt": v.get("published_at", "2024-01-15T00:00:00Z"),
                "description": v.get("description", ""),
            },
            "contentDetails": {
                "duration": v.get("duration", "PT10M30S"),
            },
            "statistics": {
                "viewCount": str(v["view_count"]),
                "likeCount": str(v["like_count"]),
                "commentCount": str(v.get("comment_count", 0)),
            },
        })
    return {"items": items}


def build_mock_service(
    channel_response: dict | None = None,
    playlist_responses: list[dict] | None = None,
    video_responses: list[dict] | None = None,
) -> MagicMock:
    """Build a fully mocked YouTube API service object."""
    service = MagicMock()

    if channel_response is not None:
        service.channels().list.return_value.execute.return_value = channel_response

    if playlist_responses is not None:
        service.playlistItems().list.return_value.execute.side_effect = playlist_responses

    if video_responses is not None:
        service.videos().list.return_value.execute.side_effect = video_responses

    return service
