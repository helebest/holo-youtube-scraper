"""CLI entry point for youtube-scraper."""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from youtube_scraper.client import get_popular_videos
from youtube_scraper.models import VideoInfo, VideoWithTranscript
from youtube_scraper.transcript import get_transcript, get_transcripts_batch

console = Console()
error_console = Console(stderr=True)

DEFAULT_OUTPUT_DIR = "output"


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _parse_languages(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    langs = [lang.strip() for lang in raw.split(",") if lang.strip()]
    return langs or None


def _sanitize_filename_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return sanitized or "data"


def _save_json(
    data,
    output_dir: str,
    prefix: str,
    label: str,
    *,
    machine_readable: bool = False,
) -> Path:
    """Save data as JSON to output directory. Returns the file path."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{_sanitize_filename_component(prefix)}_{timestamp}.json"
    filepath = out_dir / filename
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    save_msg = f"[green]Saved {label} → {filepath}[/green]"
    if machine_readable:
        error_console.print(save_msg)
    else:
        console.print(save_msg)
    return filepath


def _emit_unhandled_error(args: argparse.Namespace, exc: Exception) -> None:
    if getattr(args, "json", False):
        payload = {
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    console.print(f"[red]Error: {exc}[/red]")


def cmd_popular(args: argparse.Namespace) -> None:
    """Fetch and display popular videos from a channel."""
    if not args.json:
        console.print(f"[bold]Fetching top {args.top} videos from channel {args.channel_id}...[/bold]")
    videos = get_popular_videos(args.channel_id, top_n=args.top, max_results=args.scan)
    data = [v.to_dict() for v in videos]

    if args.output is not None:
        output_dir = args.output or DEFAULT_OUTPUT_DIR
        _save_json(
            data,
            output_dir,
            f"popular_{args.channel_id}",
            f"{len(videos)} videos",
            machine_readable=args.json,
        )

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    table = Table(title=f"Top {args.top} Videos by View Count")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", max_width=60)
    table.add_column("Views", justify="right")
    table.add_column("Likes", justify="right")
    table.add_column("Published")
    table.add_column("URL", max_width=45)

    for i, v in enumerate(videos, 1):
        table.add_row(
            str(i),
            v.title,
            f"{v.view_count:,}",
            f"{v.like_count:,}",
            v.published_at[:10],
            v.url,
        )

    console.print(table)


def cmd_transcript(args: argparse.Namespace) -> None:
    """Fetch transcript for a video."""
    if not args.json:
        console.print(f"[bold]Fetching transcript for {args.video_id}...[/bold]")
    result = get_transcript(args.video_id, languages=_parse_languages(args.lang))

    if not result.ok:
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            console.print(f"[red]Error: {result.error}[/red]")
        sys.exit(1)

    data = result.to_dict()

    if args.output is not None:
        output_dir = args.output or DEFAULT_OUTPUT_DIR
        _save_json(
            data,
            output_dir,
            f"transcript_{args.video_id}",
            "transcript",
            machine_readable=args.json,
        )

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    console.print(f"[green]Language:[/green] {result.language}")
    console.print(f"[green]Length:[/green] {len(result.text)} chars")
    console.print()
    console.print(result.text)


def cmd_full(args: argparse.Namespace) -> None:
    """Fetch popular videos and their transcripts."""
    if not args.json:
        console.print(f"[bold]Fetching top {args.top} videos + transcripts from {args.channel_id}...[/bold]")
    videos = get_popular_videos(args.channel_id, top_n=args.top, max_results=args.scan)

    langs = _parse_languages(args.lang)
    transcripts = get_transcripts_batch([v.id for v in videos], languages=langs)
    transcript_map = {t.video_id: t for t in transcripts}

    combined = [
        VideoWithTranscript(video=v, transcript=transcript_map[v.id])
        for v in videos
    ]
    data = [c.to_dict() for c in combined]

    if args.output is not None:
        output_dir = args.output or DEFAULT_OUTPUT_DIR
        _save_json(
            data,
            output_dir,
            f"full_{args.channel_id}",
            f"{len(combined)} videos + transcripts",
            machine_readable=args.json,
        )

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    for i, c in enumerate(combined, 1):
        v, t = c.video, c.transcript
        console.print(f"\n[bold cyan]#{i} {v.title}[/bold cyan]")
        console.print(f"   Views: {v.view_count:,}  Likes: {v.like_count:,}  Published: {v.published_at[:10]}")
        console.print(f"   URL: {v.url}")
        if not t.ok:
            console.print(f"   [red]Transcript error: {t.error}[/red]")
        elif t.text:
            preview = t.text[:200] + "..." if len(t.text) > 200 else t.text
            console.print(f"   [green]Transcript ({t.language}):[/green] {preview}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="youtube-scraper",
        description="Fetch popular YouTube videos and transcripts",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # popular
    p_popular = subparsers.add_parser("popular", help="Get popular videos from a channel")
    p_popular.add_argument("channel_id", help="YouTube channel ID")
    p_popular.add_argument("--top", type=_positive_int, default=10, help="Number of top videos (default: 10)")
    p_popular.add_argument("--scan", type=_positive_int, default=500, help="Max videos to scan (default: 500)")
    p_popular.add_argument("--json", action="store_true", help="Output as JSON to stdout")
    p_popular.add_argument("--output", nargs="?", const="", default=None,
                           help="Save to directory (default: output/)")

    # transcript
    p_transcript = subparsers.add_parser("transcript", help="Get transcript for a video")
    p_transcript.add_argument("video_id", help="YouTube video ID")
    p_transcript.add_argument("--lang", default=None, help="Comma-separated language codes (e.g. en,zh)")
    p_transcript.add_argument("--json", action="store_true", help="Output as JSON to stdout")
    p_transcript.add_argument("--output", nargs="?", const="", default=None,
                              help="Save to directory (default: output/)")

    # full
    p_full = subparsers.add_parser("full", help="Get popular videos + transcripts")
    p_full.add_argument("channel_id", help="YouTube channel ID")
    p_full.add_argument("--top", type=_positive_int, default=5, help="Number of top videos (default: 5)")
    p_full.add_argument("--scan", type=_positive_int, default=500, help="Max videos to scan (default: 500)")
    p_full.add_argument("--lang", default=None, help="Comma-separated language codes")
    p_full.add_argument("--json", action="store_true", help="Output as JSON to stdout")
    p_full.add_argument("--output", nargs="?", const="", default=None,
                         help="Save to directory (default: output/)")

    args = parser.parse_args()

    commands = {
        "popular": cmd_popular,
        "transcript": cmd_transcript,
        "full": cmd_full,
    }
    try:
        commands[args.command](args)
    except SystemExit:
        raise
    except Exception as exc:
        _emit_unhandled_error(args, exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
