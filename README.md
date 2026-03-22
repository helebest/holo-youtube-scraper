# Holo YouTube Scraper

[![Tests](https://github.com/helebest/holo-youtube-scraper/actions/workflows/tests.yml/badge.svg)](https://github.com/helebest/holo-youtube-scraper/actions/workflows/tests.yml)

This repository is organized around a deployable YouTube skill. Runtime code lives in `scripts/`, skill-facing docs live in `SKILL.md`, `README.md`, and `references/`, and GitHub automation stays under `automation/`.

## Skill commands

- `popular <CHANNEL_ID>`
  - Fetch the most-viewed videos from a channel.
  - Supports `--top`, `--scan`, `--timeout`, `--retries`, and `--output`.
- `transcript <VIDEO_ID_OR_URL>`
  - Fetch a transcript from a YouTube video ID or URL.
  - Supports `watch`, `youtu.be`, and `shorts` URLs.
  - Supports `--lang` and `--output`.
  - `--output` writes a `.txt` transcript file.
- `full <CHANNEL_ID>`
  - Fetch popular videos and attach transcript results for each video.
  - Supports `--top`, `--scan`, `--lang`, `--timeout`, `--retries`, and `--output`.

All commands write a single JSON envelope to stdout.

## Runtime requirements

- `YOUTUBE_API_KEY` must be set in the environment or in `<skill-root>/.env`.
- The shell wrapper looks for Python in this order:
  1. `YOUTUBE_PYTHON`
  2. OpenClaw global venv at `~/.openclaw/.venv`
  3. `python3`
  4. `python`

## Local usage

```bash
python scripts/main.py --help
python scripts/main.py popular <CHANNEL_ID> --top 5
python scripts/main.py transcript <VIDEO_ID_OR_URL> --lang en,zh --output <DIR>
python scripts/main.py full <CHANNEL_ID> --top 3 --lang en
```

Shell entrypoint:

```bash
bash scripts/youtube.sh help
bash scripts/youtube.sh transcript <VIDEO_ID_OR_URL> --lang <LANG_CODES>
```

## Deployment

Deploy to the default OpenClaw skill location:

```bash
bash openclaw_deploy_skill.sh
```

Deploy to a specific absolute path:

```bash
bash openclaw_deploy_skill.sh <ABS_TARGET_PATH>
```

The deployed skill bundle contains:

```text
<skill-target>/
  SKILL.md
  README.md
  scripts/
  references/
```

The deploy script installs runtime dependencies into the OpenClaw global venv at `~/.openclaw/.venv`.

## Repository-only automation

- Runner: `automation/youtube_automation.py`
- Config: `automation/tasks.yml`
- Workflow: `.github/workflows/youtube-automation.yml`

Automation is kept in the repository for GitHub Actions and is not copied into the deployed skill directory.

## Tests

```bash
uv run pytest
```

Coverage is measured against `scripts/` and `automation/`.
