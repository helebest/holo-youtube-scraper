# GitHub Automation

This repository keeps GitHub Actions automation separate from the deployed skill bundle.

## Paths

- Workflow: `.github/workflows/youtube-automation.yml`
- Runner: `automation/youtube_automation.py`
- Config: `automation/tasks.yml`

## Supported task modes

- `latest_full`: fetch the newest uploads per channel
- `popular_full`: fetch the most-viewed videos per channel

Automation no longer fetches transcripts and no longer supports `transcript_only`.

## Trigger modes

- `run_mode=all`: run all enabled tasks
- `run_mode=due`: run only tasks whose schedule matches the current time
- `run_mode=task`: run one named task

## Output

Each task run writes:

- `data/<task_name>/<date>/manifest.json`
- `data/<task_name>/<date>/channels/*.json`

The workflow also uploads artifact metadata as `metadata.json`.
