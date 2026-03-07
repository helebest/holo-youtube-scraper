# 命令参考

## 通用格式

```bash
bash {baseDir}/scripts/youtube.sh <command> [args...]
```

## 1) popular

```bash
bash {baseDir}/scripts/youtube.sh popular <CHANNEL_ID> [--top <N>] [--scan <N>] [--timeout <SECONDS>] [--retries <N>] [--output [<DIR>]]
```

说明：
- 获取频道内观看量最高的视频集合。
- 默认按 `top=10` 返回。

## 2) transcript

```bash
bash {baseDir}/scripts/youtube.sh transcript <VIDEO_ID> [--lang <LANG_CODES>] [--output [<DIR>]]
```

说明：
- 拉取单视频字幕。
- `--lang` 支持逗号分隔语言代码，例如：`en,zh`。

## 3) full

```bash
bash {baseDir}/scripts/youtube.sh full <CHANNEL_ID> [--top <N>] [--scan <N>] [--lang <LANG_CODES>] [--timeout <SECONDS>] [--retries <N>] [--output [<DIR>]]
```

说明：
- 返回热门视频及其字幕信息。
- 某些视频可能无字幕，结果中会包含 `transcript_error`。

## 示例

```bash
bash {baseDir}/scripts/youtube.sh popular <CHANNEL_ID> --top 5
bash {baseDir}/scripts/youtube.sh transcript <VIDEO_ID> --lang <LANG_CODES>
bash {baseDir}/scripts/youtube.sh full <CHANNEL_ID> --top 3 --lang <LANG_CODES> --output <DIR>
```
