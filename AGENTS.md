# AGENTS.md

## Project

YouTube skill-first scraper that fetches popular videos from YouTube channels and extracts transcripts. The deployable skill lives under `scripts/`, while repository-only GitHub automation lives under `automation/`.

## Tech Stack

- Python 3.12, managed with `uv`
- `google-api-python-client` for YouTube Data API
- `youtube-transcript-api` for subtitle extraction
- `pytest` + `pytest-cov` for testing

## Project Structure

```text
scripts/
  main.py               # CLI entry (popular / transcript / full commands)
  client.py             # YouTube API client (playlistItems + videos strategy)
  config.py             # Lazy .env loading and constants
  models.py             # Dataclasses used by CLI output
  transcript.py         # Transcript fetching and fallback logic
  youtube.sh            # OpenClaw shell entrypoint
automation/
  youtube_automation.py # Repository-only GitHub Actions runner
  tasks.yml             # Automation task config
references/             # Skill-facing command/output/troubleshooting docs
tests/                  # pytest suite with mock factories in conftest.py
```

## Commands

```bash
uv run pytest
uv run python scripts/main.py --help
uv run python automation/youtube_automation.py list --help
```

## Key Design Decisions

- Skill runtime is self-contained in `scripts/`
- Deployment only copies `SKILL.md`, `README.md`, `scripts/`, and `references/`
- Lazy config loading keeps imports side-effect free until the API key is needed
- CLI always emits a JSON envelope to stdout
- `transcript` accepts either a raw video ID or a YouTube URL
