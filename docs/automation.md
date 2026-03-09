# GitHub Automation Tasks

This project supports task-based YouTube monitoring in GitHub Actions.

## Config file

Task config is stored in `.github/youtube-tasks.yml`.

Current first task:

- `name`: `ai_tracker`
- `mode`: `latest_full`
- `schedule`: daily `21:00` (`Asia/Shanghai`)
- `fetch.top_n`: `5` (per channel)

## Mode options

- `latest_full`: latest uploads per channel + transcripts.
- `popular_full`: most-viewed videos per channel + transcripts.
- `transcript_only`: transcript fetch for explicit `video_ids`.

## Trigger modes

Workflow: `.github/workflows/youtube-automation.yml`

Runner: `scripts/youtube_automation.py`

- `schedule`: hourly cron (`0 * * * *`), then task-level due check.
- `workflow_dispatch` inputs:
  - `run_mode`: `due | task | all`
  - `task_name`: used when `run_mode=task`
  - `run_date`: optional `YYYY-MM-DD`
  - `dry_run`: run without branch push

## Data branch strategy

For each task run, target branch name is:

- `data_<task_name>/<date>`

For `ai_tracker` on `2026-03-08`:

- `data_ai_tracker/2026-03-08`

Output files are written to:

- `data/<task_name>/<date>/manifest.json`
- `data/<task_name>/<date>/channels/*.json`

## Required secret

Set repository secret:

- `YOUTUBE_API_KEY`
