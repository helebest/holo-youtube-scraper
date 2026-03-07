"""YouTube Data API v3 client using the quota-friendly playlistItems + videos strategy."""

import httplib2
from googleapiclient.discovery import build

from youtube_scraper.config import (
    API_REQUEST_RETRIES,
    API_REQUEST_TIMEOUT_SECONDS,
    PLAYLIST_PAGE_SIZE,
    VIDEO_BATCH_SIZE,
    DEFAULT_MAX_RESULTS,
    DEFAULT_TOP_N,
    get_api_key,
)
from youtube_scraper.models import ChannelInfo, VideoInfo


def _build_service(timeout: float = API_REQUEST_TIMEOUT_SECONDS):
    return build(
        "youtube",
        "v3",
        developerKey=get_api_key(),
        http=httplib2.Http(timeout=timeout),
        cache_discovery=False,
    )


def _execute(request, *, retries: int = API_REQUEST_RETRIES):
    """Execute a YouTube API request with retry and timeout-aware errors."""
    try:
        return request.execute(num_retries=retries)
    except TimeoutError as exc:
        raise TimeoutError(
            "YouTube API request timed out. Check your network/proxy settings and try again."
        ) from exc


def get_channel_info(
    channel_id: str,
    *,
    service=None,
    retries: int = API_REQUEST_RETRIES,
    timeout: float = API_REQUEST_TIMEOUT_SECONDS,
) -> ChannelInfo:
    """Fetch channel metadata including the uploads playlist ID."""
    service = service or _build_service(timeout=timeout)
    resp = _execute(
        service.channels().list(
            part="snippet,contentDetails,statistics",
            id=channel_id,
        ),
        retries=retries,
    )

    items = resp.get("items", [])
    if not items:
        raise ValueError(f"Channel not found: {channel_id}")

    return ChannelInfo.from_api_response(items[0])


def get_channel_videos(
    channel_id: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    *,
    service=None,
    retries: int = API_REQUEST_RETRIES,
    timeout: float = API_REQUEST_TIMEOUT_SECONDS,
) -> list[str]:
    """Get video IDs from a channel's uploads playlist via playlistItems.list."""
    svc = service or _build_service(timeout=timeout)
    info = get_channel_info(channel_id, service=svc, retries=retries, timeout=timeout)
    playlist_id = info.uploads_playlist_id

    video_ids: list[str] = []
    next_page_token = None

    while len(video_ids) < max_results:
        page_size = min(PLAYLIST_PAGE_SIZE, max_results - len(video_ids))
        resp = _execute(
            svc.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=page_size,
                pageToken=next_page_token,
            ),
            retries=retries,
        )

        for item in resp.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])

        next_page_token = resp.get("nextPageToken")
        if not next_page_token:
            break

    return video_ids[:max_results]


def get_video_details(
    video_ids: list[str],
    *,
    service=None,
    retries: int = API_REQUEST_RETRIES,
    timeout: float = API_REQUEST_TIMEOUT_SECONDS,
) -> list[VideoInfo]:
    """Batch-fetch video details (statistics, snippet) for the given video IDs."""
    if not video_ids:
        return []

    service = service or _build_service(timeout=timeout)
    results: list[VideoInfo] = []

    for i in range(0, len(video_ids), VIDEO_BATCH_SIZE):
        batch = video_ids[i : i + VIDEO_BATCH_SIZE]
        resp = _execute(
            service.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch),
            ),
            retries=retries,
        )

        for item in resp.get("items", []):
            results.append(VideoInfo.from_api_response(item))

    return results


def get_popular_videos(
    channel_id: str,
    top_n: int = DEFAULT_TOP_N,
    max_results: int = DEFAULT_MAX_RESULTS,
    *,
    service=None,
    retries: int = API_REQUEST_RETRIES,
    timeout: float = API_REQUEST_TIMEOUT_SECONDS,
) -> list[VideoInfo]:
    """Get the top N most viewed videos from a channel."""
    svc = service or _build_service(timeout=timeout)
    video_ids = get_channel_videos(
        channel_id,
        max_results=max_results,
        service=svc,
        retries=retries,
        timeout=timeout,
    )
    videos = get_video_details(video_ids, service=svc, retries=retries, timeout=timeout)
    videos.sort(key=lambda v: v.view_count, reverse=True)
    return videos[:top_n]
