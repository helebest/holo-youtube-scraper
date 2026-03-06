# AGENTS.md

## Project

YouTube scraper — fetches popular videos from YouTube channels via Data API v3 and extracts transcripts. Designed for both CLI use and programmatic LLM skill integration.

## Tech Stack

- Python 3.12, managed with `uv`
- `google-api-python-client` for YouTube Data API
- `youtube-transcript-api` for subtitle extraction
- `rich` for CLI output
- `pytest` + `pytest-cov` for testing

## Project Structure

```
src/youtube_scraper/
  models.py             # Dataclasses: ChannelInfo, VideoInfo, TranscriptResult, VideoWithTranscript
  config.py             # Lazy .env loading, API key, constants
  client.py             # YouTube API client (strategy B: playlistItems + videos)
  transcript.py         # Transcript fetching via list_transcripts + find + fetch
  summarizer.py         # LLM summarizer placeholder
  cli.py                # CLI entry (popular / transcript / full commands)
  __init__.py            # Public API exports for programmatic use
tests/                   # pytest tests with mock factories in conftest.py
```

## Commands

```bash
uv run pytest                              # Run tests with coverage
uv run python -m youtube_scraper --help    # CLI help
```

## Programmatic API (for LLM skill use)

```python
from youtube_scraper import get_popular_videos, get_transcript, VideoInfo, TranscriptResult

videos: list[VideoInfo] = get_popular_videos("UC...", top_n=5)
transcript: TranscriptResult = get_transcript("dQw4w9WgXcQ")
```

All functions return typed dataclasses with `.to_dict()` for serialization.

## Key Design Decisions

- **Strategy B** (playlistItems + videos.list) over search.list for 80% quota savings
- **Dataclass models** for all return types — self-documenting schema for LLM tools
- **Dependency injection** via `service=` kwarg on client functions for testability
- **Lazy config** — no side effects at import time, .env loaded on first API call
- **`--json` mode** outputs pure JSON (including errors) for pipeline use
- Transcript uses single `list_transcripts -> find_transcript -> fetch` flow (1 HTTP call)
