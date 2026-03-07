# 排障指南

## 参数错误

现象：返回 `error.code = INVALID_ARGUMENTS`。

处理：
- 运行 `bash {baseDir}/scripts/youtube.sh help`。
- 检查必填占位符：`<CHANNEL_ID>`、`<VIDEO_ID>`。
- 检查正数参数：`--top`、`--scan`、`--timeout`、`--retries`。

## 字幕不可用

现象：返回 `error.code = TRANSCRIPT_UNAVAILABLE`。

处理：
- 视频可能没有字幕或受区域限制。
- 尝试切换 `--lang <LANG_CODES>`。

## API 或网络异常

现象：返回 `error.code = UNEXPECTED_ERROR`，message 含请求失败信息。

处理：
- 确认 `YOUTUBE_API_KEY` 已设置。
- 检查网络与 API 配额状态。
- 调整 `--timeout` 与 `--retries`。

## 运行时缺失

现象：bash 层返回 `error.code = PYTHON_RUNTIME_MISSING`。

处理：
- 安装 `uv`，或保证 `python3/python` 可用。
