"""Transcript extraction using youtube-transcript-api (no API key needed)."""

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

from youtube_scraper.models import TranscriptResult


DEFAULT_LANGUAGES = ["zh-Hans", "zh", "en", "ja"]


def _get_api():
    return YouTubeTranscriptApi()


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
    return "UNKNOWN_ERROR", str(exc) or "Unexpected error while fetching transcript."


def get_transcript(
    video_id: str,
    languages: list[str] | None = None,
    *,
    api=None,
) -> TranscriptResult:
    """Fetch transcript for a single video.

    Uses list + find_transcript + fetch (single HTTP flow).
    """
    langs = languages or DEFAULT_LANGUAGES
    api = api or _get_api()
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
    api = _get_api()
    return [get_transcript(vid, languages, api=api) for vid in video_ids]
