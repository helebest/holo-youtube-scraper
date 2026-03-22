# CLAUDE.md

## Project

YouTube skill-first scraper that fetches popular channel videos and transcripts. Runtime code is centered in `scripts/`; GitHub automation is repository-only and lives in `automation/`.

## Tech Stack

- Python 3.12 with `uv`
- `google-api-python-client`
- `youtube-transcript-api`
- `pytest` + `pytest-cov`

## Project Structure

```text
scripts/
  main.py
  client.py
  config.py
  models.py
  transcript.py
  youtube.sh
automation/
  youtube_automation.py
  tasks.yml
references/
tests/
```

## Commands

```bash
uv run pytest
uv run python scripts/main.py --help
uv run python automation/youtube_automation.py list --help
```

## Notes

- The deployed skill bundle contains `SKILL.md`, `README.md`, `scripts/`, and `references/`.
- `transcript --output` writes a `.txt` transcript file.
- CLI stdout remains a single JSON envelope for success and error cases.
