"""Transcript extraction using youtube-transcript-api with YouTube Data API v3 fallback."""

from youtube_transcript_api import YouTubeTranscriptApi
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

from googleapiclient.discovery import build

from youtube_scraper.client import sanitize_error_message
from youtube_scraper import config as youtube_config
from youtube_scraper.models import TranscriptResult


DEFAULT_LANGUAGES = ["zh-Hans", "zh", "en", "ja"]

# YouTube Data API service name and version
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


def _get_youtube_api():
    """Get YouTube Data API v3 client."""
    api_key = youtube_config.get_api_key()
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=api_key)


def _get_youtube_transcript_api():
    """Get youtube-transcript-api instance."""
    return YouTubeTranscriptApi()


def _get_transcript_via_api(video_id: str, languages: list[str]) -> TranscriptResult | None:
    """Fallback: Get transcript via YouTube Data API v3 captions endpoint."""
    try:
        youtube = _get_youtube_api()

        # List available captions
        captions_response = youtube.captions().list(
            part="snippet",
            videoId=video_id
        ).execute()

        captions = captions_response.get("items", [])
        if not captions:
            return None

        # Find a caption in preferred languages
        selected_caption = None
        for lang in languages:
            for caption in captions:
                snippet = caption.get("snippet", {})
                if snippet.get("language") == lang:
                    selected_caption = caption
                    break
            if selected_caption:
                break

        if not selected_caption:
            return None

        caption_id = selected_caption["id"]

        # Download the caption
        download_response = youtube.captions().download(
            id=caption_id,
            tlang=languages[0] if languages else "en"
        ).execute()

        # Parse SRT/timestamps to simple text
        # YouTube API returns SBV or SRT format
        text = download_response.decode("utf-8") if isinstance(download_response, bytes) else download_response

        # Simple extraction: remove timestamps
        import re
        # Remove timestamp lines (00:00:00,000 --> 00:00:01,000)
        cleaned_text = re.sub(r'\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}\r?\n?', '', text)
        cleaned_text = re.sub(r'\r?\n\r?\n', ' ', cleaned_text)
        cleaned_text = cleaned_text.strip()

        if not cleaned_text:
            return None

        return TranscriptResult(
            video_id=video_id,
            language=selected_caption["snippet"]["language"],
            text=cleaned_text,
            segments=[],
        )

    except Exception as e:
        # Fallback failed too
        return None


def _normalize_error(exc: Exception) -> tuple[str, str]:
    """Map transcript exceptions to stable error codes and short messages."""
    if isinstance(exc, TranscriptsDisabled):
        return "TRANSCRIPTS_DISABLED", "Subtitles are disabled for this video."
    if isinstance(exc, NoTranscriptFound):
        return "NO_TRANSCRIPT_FOUND", "No transcript available for the requested languages."
    if isinstance(exc, VideoUnavailable):
        return "VIDEO_UNAVAILABLE", "Video is unavailable."
    if isinstance(exc, AgeRestricted):
        return "AGE_RESTRICTED", "Video is age-restricted and transcript requires authentication."
    if isinstance(exc, (RequestBlocked, IpBlocked)):
        return "REQUEST_BLOCKED", "Transcript requests are blocked from the current IP."
    if isinstance(exc, InvalidVideoId):
        return "INVALID_VIDEO_ID", "Invalid YouTube video ID."
    if isinstance(exc, CouldNotRetrieveTranscript):
        return "TRANSCRIPT_UNAVAILABLE", "Could not retrieve transcript for this video."
    raw = str(exc)
    return "UNKNOWN_ERROR", sanitize_error_message(raw) if raw else "Unexpected error while fetching transcript."


def get_transcript(
    video_id: str,
    languages: list[str] | None = None,
    *,
    api=None,
) -> TranscriptResult:
    """Fetch transcript for a single video.

    First tries youtube-transcript-api. If blocked by IP, falls back to YouTube Data API v3.
    """
    langs = languages or DEFAULT_LANGUAGES
    api = api or _get_youtube_transcript_api()

    # First try youtube-transcript-api
    try:
        transcript_list = api.list(video_id)
        transcript_obj = transcript_list.find_transcript(langs)
        fetched = transcript_obj.fetch()
        full_text = " ".join(snippet.text for snippet in fetched)
        segments = [
            {"text": s.text, "start": s.start, "duration": s.duration}
            for s in fetched
        ]
        return TranscriptResult(
            video_id=video_id,
            language=transcript_obj.language_code,
            text=full_text,
            segments=segments,
        )
    except Exception as e:
        error_code, error_message = _normalize_error(e)

        # If blocked by IP, try fallback to YouTube Data API v3
        if error_code in ("REQUEST_BLOCKED", "IP_BLOCKED"):
            fallback_result = _get_transcript_via_api(video_id, langs)
            if fallback_result:
                return fallback_result
            # Fallback also failed, return original error

        return TranscriptResult(
            video_id=video_id,
            error=error_message,
            error_code=error_code,
        )


def get_transcripts_batch(
    video_ids: list[str],
    languages: list[str] | None = None,
) -> list[TranscriptResult]:
    """Fetch transcripts for multiple videos."""
    api = _get_youtube_transcript_api()
    return [get_transcript(vid, languages, api=api) for vid in video_ids]
