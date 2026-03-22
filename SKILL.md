---
name: holo-youtube-scraper
description: Fetch YouTube popular videos and transcripts as a skill-friendly JSON workflow.
---

# Holo YouTube Scraper

## When to use

- You need the most-viewed videos from a YouTube channel.
- You need a transcript for a single video ID or a YouTube URL.
- You need a combined video list with transcript results attached.

## Entry point

```bash
bash {baseDir}/scripts/youtube.sh <command> [args...]
```

## Commands

- `popular <CHANNEL_ID>`
  - Returns the most-viewed videos for a channel.
- `transcript <VIDEO_ID_OR_URL>`
  - Accepts a raw video ID or a YouTube URL.
  - Supports `youtube.com/watch?v=...`, `youtu.be/...`, and `youtube.com/shorts/...`.
  - `--output` writes a `.txt` transcript file while stdout stays JSON.
- `full <CHANNEL_ID>`
  - Returns popular videos with transcript results merged into each item.

## Output contract

- Success envelope: `{"ok": true, "command": ..., "input": ..., "result": ..., "meta": ...}`
- Error envelope: `{"ok": false, "command": ..., "input": ..., "error": ..., "meta": ...}`

Use [references/commands.md](references/commands.md) for command details and [references/output-schema.md](references/output-schema.md) for schema details.

## Required configuration

- `YOUTUBE_API_KEY`
  - Set it in the environment, or in `{baseDir}/.env`.

## Common failures

- `INVALID_ARGUMENTS`
  - The command arguments are malformed, such as an unsupported YouTube URL.
- `PYTHON_RUNTIME_MISSING`
  - The shell wrapper could not find `YOUTUBE_PYTHON`, the OpenClaw global venv, `python3`, or `python`.
- Transcript errors such as `TRANSCRIPT_UNAVAILABLE`, `NO_TRANSCRIPT_FOUND`, `TRANSCRIPTS_DISABLED`, or `REQUEST_BLOCKED`
  - The video does not expose subtitles or transcript access is blocked.
