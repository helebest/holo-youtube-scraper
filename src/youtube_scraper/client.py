"""YouTube Data API v3 client using the quota-friendly playlistItems + videos strategy."""

from googleapiclient.discovery import build

from youtube_scraper.config import (
    PLAYLIST_PAGE_SIZE,
    VIDEO_BATCH_SIZE,
    DEFAULT_MAX_RESULTS,
    DEFAULT_TOP_N,
    get_api_key,
)
from youtube_scraper.models import ChannelInfo, VideoInfo


def _build_service():
    return build("youtube", "v3", developerKey=get_api_key())


def get_channel_info(channel_id: str, *, service=None) -> ChannelInfo:
    """Fetch channel metadata including the uploads playlist ID."""
    service = service or _build_service()
    resp = service.channels().list(
        part="snippet,contentDetails,statistics",
        id=channel_id,
    ).execute()

    items = resp.get("items", [])
    if not items:
        raise ValueError(f"Channel not found: {channel_id}")

    return ChannelInfo.from_api_response(items[0])


def get_channel_videos(
    channel_id: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    *,
    service=None,
) -> list[str]:
    """Get video IDs from a channel's uploads playlist via playlistItems.list."""
    svc = service or _build_service()
    info = get_channel_info(channel_id, service=svc)
    playlist_id = info.uploads_playlist_id

    video_ids: list[str] = []
    next_page_token = None

    while len(video_ids) < max_results:
        page_size = min(PLAYLIST_PAGE_SIZE, max_results - len(video_ids))
        resp = svc.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=page_size,
            pageToken=next_page_token,
        ).execute()

        for item in resp.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])

        next_page_token = resp.get("nextPageToken")
        if not next_page_token:
            break

    return video_ids[:max_results]


def get_video_details(video_ids: list[str], *, service=None) -> list[VideoInfo]:
    """Batch-fetch video details (statistics, snippet) for the given video IDs."""
    if not video_ids:
        return []

    service = service or _build_service()
    results: list[VideoInfo] = []

    for i in range(0, len(video_ids), VIDEO_BATCH_SIZE):
        batch = video_ids[i : i + VIDEO_BATCH_SIZE]
        resp = service.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(batch),
        ).execute()

        for item in resp.get("items", []):
            results.append(VideoInfo.from_api_response(item))

    return results


def get_popular_videos(
    channel_id: str,
    top_n: int = DEFAULT_TOP_N,
    max_results: int = DEFAULT_MAX_RESULTS,
    *,
    service=None,
) -> list[VideoInfo]:
    """Get the top N most viewed videos from a channel."""
    svc = service or _build_service()
    video_ids = get_channel_videos(channel_id, max_results=max_results, service=svc)
    videos = get_video_details(video_ids, service=svc)
    videos.sort(key=lambda v: v.view_count, reverse=True)
    return videos[:top_n]
