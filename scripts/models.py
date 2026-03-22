"""Data models for YouTube scraper.

These dataclasses define the schema for all API return values,
making them self-documenting for LLM tool/skill integration.
"""

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ChannelInfo:
    """YouTube channel metadata."""
    id: str
    title: str
    description: str
    subscriber_count: int
    video_count: int
    uploads_playlist_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_api_response(cls, item: dict) -> "ChannelInfo":
        """Parse from a YouTube channels.list API response item."""
        snippet = item["snippet"]
        stats = item.get("statistics", {})
        return cls(
            id=item["id"],
            title=snippet["title"],
            description=snippet.get("description", ""),
            subscriber_count=int(stats.get("subscriberCount", 0)),
            video_count=int(stats.get("videoCount", 0)),
            uploads_playlist_id=item["contentDetails"]["relatedPlaylists"]["uploads"],
        )


@dataclass
class VideoInfo:
    """YouTube video metadata with statistics."""
    id: str
    title: str
    channel_title: str
    published_at: str
    description: str
    duration: str
    view_count: int
    like_count: int
    comment_count: int
    url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_api_response(cls, item: dict) -> "VideoInfo":
        """Parse from a YouTube videos.list API response item."""
        snippet = item["snippet"]
        stats = item.get("statistics", {})
        return cls(
            id=item["id"],
            title=snippet["title"],
            channel_title=snippet.get("channelTitle", ""),
            published_at=snippet["publishedAt"],
            description=snippet.get("description", ""),
            duration=item.get("contentDetails", {}).get("duration", ""),
            view_count=int(stats.get("viewCount", 0)),
            like_count=int(stats.get("likeCount", 0)),
            comment_count=int(stats.get("commentCount", 0)),
            url=f"https://www.youtube.com/watch?v={item['id']}",
        )


@dataclass
class TranscriptResult:
    """Result of a transcript fetch attempt."""
    video_id: str
    language: str | None = None
    text: str | None = None
    segments: list[dict] | None = None
    error: str | None = None
    error_code: str | None = None

    @property
    def ok(self) -> bool:
        """Whether the transcript was fetched successfully."""
        return self.error is None and self.text is not None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VideoWithTranscript:
    """Combined video info and transcript, used by the `full` command."""
    video: VideoInfo
    transcript: TranscriptResult

    def to_dict(self) -> dict[str, Any]:
        d = self.video.to_dict()
        d["transcript"] = self.transcript.text
        d["transcript_language"] = self.transcript.language
        d["transcript_error"] = self.transcript.error
        return d
