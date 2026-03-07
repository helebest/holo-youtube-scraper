---
name: holo-youtube-scraper
description: 用于获取 YouTube 频道热门视频与字幕的技能。适用于频道内容调研、视频候选筛选、字幕抓取与结构化输出场景。
---

# Holo YouTube Scraper

## 快速入口

1. 先确认依赖：`bash` 与可用的 Python 运行时（优先 `uv`）。
2. 在技能目录执行：`bash {baseDir}/scripts/youtube.sh <command> [args...]`。
3. 所有命令输出统一 JSON 信封，适合 LLM 解析。

详细命令见 [references/commands.md](references/commands.md)。
输出字段见 [references/output-schema.md](references/output-schema.md)。

## 命令选择

- 只要频道热门视频：`popular <CHANNEL_ID>`。
- 只要字幕文本：`transcript <VIDEO_ID>`。
- 频道热门视频 + 字幕：`full <CHANNEL_ID>`。

## 常见失败处理

- 参数错误：先执行 `bash {baseDir}/scripts/youtube.sh help` 对照占位符。
- API 失败：检查 `YOUTUBE_API_KEY` 与网络可达性。
- 运行时缺失：安装 `uv` 或 `python3`。

完整排障见 [references/troubleshooting.md](references/troubleshooting.md)。

## 最小示例

```bash
bash {baseDir}/scripts/youtube.sh popular <CHANNEL_ID> --top 5
bash {baseDir}/scripts/youtube.sh transcript <VIDEO_ID> --lang <LANG_CODES>
bash {baseDir}/scripts/youtube.sh full <CHANNEL_ID> --top 3 --lang <LANG_CODES>
```
