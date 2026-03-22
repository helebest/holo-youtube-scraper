"""CLI entry point for youtube-scraper."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from .client import get_popular_videos, sanitize_error_message
    from .config import API_REQUEST_RETRIES, API_REQUEST_TIMEOUT_SECONDS
    from .models import VideoWithTranscript
    from .transcript import get_transcript, get_transcripts_batch
except ImportError:  # pragma: no cover - direct script execution path
    from client import get_popular_videos, sanitize_error_message  # type: ignore
    from config import API_REQUEST_RETRIES, API_REQUEST_TIMEOUT_SECONDS  # type: ignore
    from models import VideoWithTranscript  # type: ignore
    from transcript import get_transcript, get_transcripts_batch  # type: ignore

DEFAULT_OUTPUT_DIR = "output"
VALID_COMMANDS = {"popular", "transcript", "full"}
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,}$")
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}


class CliFailure(Exception):
    """Controlled CLI failure with a JSON payload and exit code."""

    def __init__(self, payload: dict[str, Any], exit_code: int = 1):
        super().__init__(payload.get("error", {}).get("message", "CLI failure"))
        self.payload = payload
        self.exit_code = exit_code


class JsonArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that returns JSON envelopes on argument errors."""

    def error(self, message: str) -> None:
        payload = _error_payload(
            command=_extract_command(sys.argv[1:]),
            input_data={"argv": sys.argv[1:]},
            error_type="ArgumentError",
            error_code="INVALID_ARGUMENTS",
            message=message,
        )
        _emit_payload(payload)
        raise SystemExit(2)


def _extract_command(argv: list[str]) -> str | None:
    if not argv:
        return None
    candidate = argv[0]
    if candidate in VALID_COMMANDS:
        return candidate
    return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _emit_payload(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive number")
    return parsed


def _parse_languages(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    langs = [lang.strip() for lang in raw.split(",") if lang.strip()]
    return langs or None


def _sanitize_filename_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return sanitized or "data"


def _save_json(data: Any, output_dir: str, prefix: str) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{_sanitize_filename_component(prefix)}_{timestamp}.json"
    filepath = out_dir / filename
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return filepath


def _save_text(text: str, output_dir: str, prefix: str) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{_sanitize_filename_component(prefix)}_{timestamp}.txt"
    filepath = out_dir / filename
    filepath.write_text(text, encoding="utf-8")
    return filepath


def _build_meta(*, saved_to: Path | None = None, count: int | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {"generated_at": _utc_now_iso()}
    if saved_to is not None:
        meta["saved_to"] = str(saved_to)
    if count is not None:
        meta["count"] = count
    return meta


def _success_payload(
    command: str,
    input_data: dict[str, Any],
    result: Any,
    *,
    saved_to: Path | None = None,
    count: int | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "command": command,
        "input": input_data,
        "result": result,
        "meta": _build_meta(saved_to=saved_to, count=count),
    }


def _error_payload(
    *,
    command: str | None,
    input_data: dict[str, Any] | None,
    error_type: str,
    error_code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "command": command,
        "input": input_data or {},
        "error": {
            "type": error_type,
            "code": error_code,
            "message": message,
        },
        "meta": _build_meta(),
    }


def _base_input(args: argparse.Namespace) -> dict[str, Any]:
    return {k: v for k, v in vars(args).items() if k != "command"}


def _extract_video_id_from_url(value: str) -> str | None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None

    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host in SHORT_HOSTS:
        return path_parts[0] if path_parts else None

    if host not in YOUTUBE_HOSTS:
        return None

    if parsed.path == "/watch":
        query = parse_qs(parsed.query)
        video_id = query.get("v", [None])[0]
        return video_id

    if len(path_parts) >= 2 and path_parts[0] == "shorts":
        return path_parts[1]

    return None


def resolve_video_reference(video_ref: str) -> str:
    value = video_ref.strip()
    if not value:
        raise ValueError("video reference cannot be empty")
    if VIDEO_ID_PATTERN.fullmatch(value):
        return value

    resolved = _extract_video_id_from_url(value)
    if resolved and VIDEO_ID_PATTERN.fullmatch(resolved):
        return resolved

    raise ValueError(f"Could not extract a video ID from '{video_ref}'.")


def cmd_popular(args: argparse.Namespace) -> dict[str, Any]:
    videos = get_popular_videos(
        args.channel_id,
        top_n=args.top,
        max_results=args.scan,
        retries=args.retries,
        timeout=args.timeout,
    )
    result = [video.to_dict() for video in videos]

    output_dir: str | None = None
    saved_to: Path | None = None
    if args.output is not None:
        output_dir = args.output or DEFAULT_OUTPUT_DIR
        saved_to = _save_json(result, output_dir, f"popular_{args.channel_id}")

    input_data = {
        "channel_id": args.channel_id,
        "top": args.top,
        "scan": args.scan,
        "timeout": args.timeout,
        "retries": args.retries,
        "output_dir": output_dir,
        "json": args.json,
    }
    return _success_payload(
        "popular",
        input_data,
        result,
        saved_to=saved_to,
        count=len(result),
    )


def cmd_transcript(args: argparse.Namespace) -> dict[str, Any]:
    languages = _parse_languages(args.lang)
    try:
        resolved_video_id = resolve_video_reference(args.video_ref)
    except ValueError as exc:
        raise CliFailure(
            _error_payload(
                command="transcript",
                input_data={"video_ref": args.video_ref},
                error_type="ArgumentError",
                error_code="INVALID_ARGUMENTS",
                message=str(exc),
            ),
            exit_code=2,
        ) from exc

    transcript = get_transcript(resolved_video_id, languages=languages)

    input_data = {
        "video_ref": args.video_ref,
        "video_id": resolved_video_id,
        "languages": languages,
        "output_dir": (args.output or DEFAULT_OUTPUT_DIR) if args.output is not None else None,
        "json": args.json,
    }

    if not transcript.ok:
        raise CliFailure(
            _error_payload(
                command="transcript",
                input_data=input_data,
                error_type="TranscriptError",
                error_code=transcript.error_code or "TRANSCRIPT_UNAVAILABLE",
                message=transcript.error or "Transcript is unavailable",
            ),
            exit_code=1,
        )

    result = transcript.to_dict()
    saved_to: Path | None = None
    if args.output is not None:
        output_dir = args.output or DEFAULT_OUTPUT_DIR
        saved_to = _save_text(transcript.text or "", output_dir, f"transcript_{resolved_video_id}")

    return _success_payload(
        "transcript",
        input_data,
        result,
        saved_to=saved_to,
        count=1,
    )


def cmd_full(args: argparse.Namespace) -> dict[str, Any]:
    videos = get_popular_videos(
        args.channel_id,
        top_n=args.top,
        max_results=args.scan,
        retries=args.retries,
        timeout=args.timeout,
    )

    languages = _parse_languages(args.lang)
    transcripts = get_transcripts_batch([video.id for video in videos], languages=languages)
    transcript_map = {item.video_id: item for item in transcripts}

    combined = [
        VideoWithTranscript(video=video, transcript=transcript_map[video.id])
        for video in videos
    ]
    result = [item.to_dict() for item in combined]

    output_dir: str | None = None
    saved_to: Path | None = None
    if args.output is not None:
        output_dir = args.output or DEFAULT_OUTPUT_DIR
        saved_to = _save_json(result, output_dir, f"full_{args.channel_id}")

    input_data = {
        "channel_id": args.channel_id,
        "top": args.top,
        "scan": args.scan,
        "languages": languages,
        "timeout": args.timeout,
        "retries": args.retries,
        "output_dir": output_dir,
        "json": args.json,
    }
    return _success_payload(
        "full",
        input_data,
        result,
        saved_to=saved_to,
        count=len(result),
    )


def _build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(
        prog="youtube-scraper",
        description="Fetch YouTube videos and transcripts for LLM workflows.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  youtube-scraper popular <CHANNEL_ID> --top 5\n"
            "  youtube-scraper transcript <VIDEO_ID_OR_URL> --lang <LANG_CODES>\n"
            "  youtube-scraper full <CHANNEL_ID> --top 3 --lang <LANG_CODES>\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_popular = subparsers.add_parser(
        "popular",
        help="Fetch top videos for a channel",
        description="Fetch top videos for <CHANNEL_ID> sorted by view count.",
    )
    p_popular.add_argument("channel_id", metavar="<CHANNEL_ID>", help="YouTube channel ID")
    p_popular.add_argument("--top", type=_positive_int, default=10, help="Top N videos (default: 10)")
    p_popular.add_argument("--scan", type=_positive_int, default=500, help="Max videos to scan (default: 500)")
    p_popular.add_argument(
        "--timeout",
        type=_positive_float,
        default=API_REQUEST_TIMEOUT_SECONDS,
        help=f"YouTube API timeout in seconds (default: {API_REQUEST_TIMEOUT_SECONDS})",
    )
    p_popular.add_argument(
        "--retries",
        type=_positive_int,
        default=API_REQUEST_RETRIES,
        help=f"YouTube API retry attempts (default: {API_REQUEST_RETRIES})",
    )
    p_popular.add_argument(
        "--json",
        action="store_true",
        help="No-op flag kept for compatibility. Output is always JSON envelope.",
    )
    p_popular.add_argument("--output", nargs="?", const="", default=None, help="Save raw result JSON to directory")

    p_transcript = subparsers.add_parser(
        "transcript",
        help="Fetch transcript for a video",
        description="Fetch transcript for <VIDEO_ID_OR_URL>.",
    )
    p_transcript.add_argument(
        "video_ref",
        metavar="<VIDEO_ID_OR_URL>",
        help="YouTube video ID or video URL",
    )
    p_transcript.add_argument("--lang", default=None, help="Comma-separated language codes, e.g. en,zh")
    p_transcript.add_argument(
        "--json",
        action="store_true",
        help="No-op flag kept for compatibility. Output is always JSON envelope.",
    )
    p_transcript.add_argument(
        "--output",
        nargs="?",
        const="",
        default=None,
        help="Save transcript text to directory",
    )

    p_full = subparsers.add_parser(
        "full",
        help="Fetch top videos and transcripts",
        description="Fetch top videos and transcript summaries for <CHANNEL_ID>.",
    )
    p_full.add_argument("channel_id", metavar="<CHANNEL_ID>", help="YouTube channel ID")
    p_full.add_argument("--top", type=_positive_int, default=5, help="Top N videos (default: 5)")
    p_full.add_argument("--scan", type=_positive_int, default=500, help="Max videos to scan (default: 500)")
    p_full.add_argument("--lang", default=None, help="Comma-separated language codes")
    p_full.add_argument(
        "--timeout",
        type=_positive_float,
        default=API_REQUEST_TIMEOUT_SECONDS,
        help=f"YouTube API timeout in seconds (default: {API_REQUEST_TIMEOUT_SECONDS})",
    )
    p_full.add_argument(
        "--retries",
        type=_positive_int,
        default=API_REQUEST_RETRIES,
        help=f"YouTube API retry attempts (default: {API_REQUEST_RETRIES})",
    )
    p_full.add_argument(
        "--json",
        action="store_true",
        help="No-op flag kept for compatibility. Output is always JSON envelope.",
    )
    p_full.add_argument("--output", nargs="?", const="", default=None, help="Save raw result JSON to directory")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    commands = {
        "popular": cmd_popular,
        "transcript": cmd_transcript,
        "full": cmd_full,
    }

    try:
        payload = commands[args.command](args)
        _emit_payload(payload)
    except CliFailure as failure:
        _emit_payload(failure.payload)
        raise SystemExit(failure.exit_code)
    except SystemExit:
        raise
    except Exception as exc:
        payload = _error_payload(
            command=getattr(args, "command", None),
            input_data=_base_input(args),
            error_type=type(exc).__name__,
            error_code="UNEXPECTED_ERROR",
            message=sanitize_error_message(str(exc)),
        )
        _emit_payload(payload)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
