"""YouTube Scraper - Fetch popular videos and transcripts from YouTube channels.

Public API for programmatic / LLM skill use:

    from youtube_scraper import get_popular_videos, get_transcript

    videos = get_popular_videos("UC...", top_n=5)
    for v in videos:
        print(v.title, v.view_count)

    transcript = get_transcript("dQw4w9WgXcQ")
    if transcript.ok:
        print(transcript.text)
"""

from youtube_scraper.client import (
    get_channel_info,
    get_channel_videos,
    get_popular_videos,
    get_video_details,
)
from youtube_scraper.models import (
    ChannelInfo,
    TranscriptResult,
    VideoInfo,
    VideoWithTranscript,
)
from youtube_scraper.transcript import get_transcript, get_transcripts_batch

__all__ = [
    # Core functions
    "get_channel_info",
    "get_channel_videos",
    "get_popular_videos",
    "get_video_details",
    "get_transcript",
    "get_transcripts_batch",
    # Data models
    "ChannelInfo",
    "VideoInfo",
    "TranscriptResult",
    "VideoWithTranscript",
]
