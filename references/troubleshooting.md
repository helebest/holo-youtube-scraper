# Troubleshooting

## `YOUTUBE_API_KEY not set`

- Set `YOUTUBE_API_KEY` in the environment.
- Or create `<skill-root>/.env` with:

```bash
YOUTUBE_API_KEY=<YOUR_API_KEY>
```

## `PYTHON_RUNTIME_MISSING`

The shell wrapper checks Python in this order:

1. `YOUTUBE_PYTHON`
2. `~/.openclaw/.venv`
3. `python3`
4. `python`

If the wrapper still fails, deploy the skill again so dependencies are installed into the OpenClaw global venv.

## `INVALID_ARGUMENTS`

Common causes:

- `popular` or `full` received an invalid `<CHANNEL_ID>`
- `transcript` received an unsupported URL instead of `<VIDEO_ID_OR_URL>`
- numeric flags such as `--top`, `--scan`, `--timeout`, or `--retries` were zero or negative

## Transcript-specific failures

- `NO_TRANSCRIPT_FOUND`
  - No transcript exists for the requested language preference.
- `TRANSCRIPTS_DISABLED`
  - The video owner disabled subtitles.
- `TRANSCRIPT_UNAVAILABLE`
  - Transcript retrieval failed without a more specific typed error.
- `REQUEST_BLOCKED`
  - Transcript requests were blocked from the current IP.
- `INVALID_VIDEO_ID`
  - The resolved video ID is invalid.

## GitHub automation

Automation is repository-only:

- runner: `automation/youtube_automation.py`
- config: `automation/tasks.yml`

If automation breaks, check `.github/workflows/youtube-automation.yml` and `docs/automation.md`.
