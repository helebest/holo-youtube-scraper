# YouTube Scraper

通过 YouTube Data API v3 获取频道热门视频，并提取视频字幕/转录文本。

## 功能

- **热门视频** — 获取指定频道播放量最高的视频，按观看数排序
- **字幕提取** — 获取视频的字幕文本（支持多语言，无需额外 API Key）
- **一站式** — 热门视频 + 字幕一次搞定，支持 JSON 输出

## 快速开始

### 1. 安装

```bash
uv sync
```

### 2. 配置 API Key

在 [Google Cloud Console](https://console.cloud.google.com/apis/credentials) 创建 API 密钥并启用 YouTube Data API v3，然后：

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 3. 使用

```bash
# 获取频道热门视频（默认 top 10）
uv run python -m youtube_scraper popular <channel_id> --top 5

# 获取视频字幕
uv run python -m youtube_scraper transcript <video_id>

# 热门视频 + 字幕（一站式）
uv run python -m youtube_scraper full <channel_id> --top 3

# 所有命令支持 --json 输出
uv run python -m youtube_scraper popular <channel_id> --json
```

### 示例

```bash
# Two Minute Papers 频道 top 5
uv run python -m youtube_scraper popular UCbfYPyITQ-7l4upoX8nvctg --top 5
```

## 编程接口

可直接作为 Python 库使用：

```python
from youtube_scraper import get_popular_videos, get_transcript

videos = get_popular_videos("UCbfYPyITQ-7l4upoX8nvctg", top_n=5)
for v in videos:
    print(f"{v.title} - {v.view_count:,} views")

transcript = get_transcript("dQw4w9WgXcQ")
if transcript.ok:
    print(transcript.text)
```

所有函数返回类型化的 dataclass，支持 `.to_dict()` 序列化。

## 项目结构

```
src/youtube_scraper/
  config.py        # 配置管理（API Key、默认参数）
  models.py        # 数据模型（ChannelInfo, VideoInfo, TranscriptResult）
  client.py        # YouTube API 客户端
  transcript.py    # 字幕提取
  cli.py           # CLI 入口
tests/             # 单元测试
docs/research.md   # API 调研文档
```

## 配额说明

采用 playlistItems + videos.list 策略（而非 search.list），配额消耗低约 80%：

| 操作 | 配额消耗 |
|------|----------|
| 获取 50 个视频并排序 | ~3 单位 |
| 获取 500 个视频并排序 | ~21 单位 |
| YouTube 每日免费配额 | 10,000 单位 |

## 开发

```bash
uv run pytest          # 运行测试 + 覆盖率
```
