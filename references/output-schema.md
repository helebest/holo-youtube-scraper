# Output Schema

Every command writes one JSON object to stdout.

## Success envelope

```json
{
  "ok": true,
  "command": "transcript",
  "input": {},
  "result": {},
  "meta": {
    "generated_at": "2026-03-22T00:00:00Z"
  }
}
```

Fields:

- `ok`: `true`
- `command`: `popular`, `transcript`, or `full`
- `input`: normalized command input
- `result`: command payload
- `meta.generated_at`: UTC timestamp
- `meta.count`: present on collection-oriented results
- `meta.saved_to`: present when `--output` is used

## Error envelope

```json
{
  "ok": false,
  "command": "transcript",
  "input": {},
  "error": {
    "type": "ArgumentError",
    "code": "INVALID_ARGUMENTS",
    "message": "Could not extract a video ID from '<VIDEO_ID_OR_URL>'."
  },
  "meta": {
    "generated_at": "2026-03-22T00:00:00Z"
  }
}
```

## Command-specific notes

### `popular`

- `input.channel_id`: requested channel ID
- `result`: array of video objects
- `meta.count`: number of returned videos
- `meta.saved_to`: path to the saved JSON file when `--output` is used

### `transcript`

- `input.video_ref`: original raw input
- `input.video_id`: resolved video ID after URL normalization
- `result`: transcript object with `video_id`, `language`, `text`, `segments`, `error`, and `error_code`
- `meta.saved_to`: path to the saved `.txt` transcript when `--output` is used

### `full`

- `input.channel_id`: requested channel ID
- `result`: array of video objects enriched with `transcript`, `transcript_language`, and `transcript_error`
- `meta.count`: number of returned items
- `meta.saved_to`: path to the saved JSON file when `--output` is used
