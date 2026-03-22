# Commands

## `popular <CHANNEL_ID>`

Fetch the most-viewed videos from a channel.

```bash
python scripts/main.py popular <CHANNEL_ID> --top 5 --scan 200 --output <DIR>
```

Options:

- `--top <N>`: number of videos returned. Default `10`.
- `--scan <N>`: number of uploads scanned before sorting by views. Default `500`.
- `--timeout <SECONDS>`: YouTube Data API timeout. Default `30`.
- `--retries <N>`: retry attempts for Data API requests. Default `3`.
- `--output [<DIR>]`: save the result JSON file. Default directory is `output/` when the flag is present without a value.

## `transcript <VIDEO_ID_OR_URL>`

Fetch a transcript from a raw video ID or a supported YouTube URL.

```bash
python scripts/main.py transcript <VIDEO_ID_OR_URL> --lang en,zh --output <DIR>
```

Supported URL forms:

- `https://www.youtube.com/watch?v=<VIDEO_ID>`
- `https://youtu.be/<VIDEO_ID>`
- `https://www.youtube.com/shorts/<VIDEO_ID>`

Options:

- `--lang <LANG_CODES>`: comma-separated language priority list.
- `--output [<DIR>]`: save transcript text as a `.txt` file. Default directory is `output/` when the flag is present without a value.

## `full <CHANNEL_ID>`

Fetch popular videos and attach transcript results for each video.

```bash
python scripts/main.py full <CHANNEL_ID> --top 3 --lang en,zh --output <DIR>
```

Options:

- `--top <N>`: number of videos returned. Default `5`.
- `--scan <N>`: number of uploads scanned before sorting by views. Default `500`.
- `--lang <LANG_CODES>`: comma-separated language priority list.
- `--timeout <SECONDS>`: YouTube Data API timeout. Default `30`.
- `--retries <N>`: retry attempts for Data API requests. Default `3`.
- `--output [<DIR>]`: save the combined JSON file. Default directory is `output/` when the flag is present without a value.
