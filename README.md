# Holo YouTube Scraper

[![CI](https://github.com/helebest/holo-youtube-scraper/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/helebest/holo-youtube-scraper/actions/workflows/tests.yml)
[![Release v1.0.0](https://img.shields.io/badge/release-v1.0.0-blue.svg)](https://github.com/helebest/holo-youtube-scraper/releases/tag/v1.0.0)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/github/license/helebest/holo-youtube-scraper)](https://github.com/helebest/holo-youtube-scraper/blob/main/LICENSE)

通过 YouTube Data API v3 获取频道热门视频，并提取视频字幕/转录文本。

## 功能

- 热门视频：获取指定频道播放量最高的视频，按观看数排序
- 字幕提取：获取视频字幕文本（支持多语言）
- 一站式：热门视频 + 字幕一次获取
- 统一输出：CLI 默认输出 LLM 友好的 JSON 信封

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
uv run python -m youtube_scraper popular <CHANNEL_ID> --top 5

# 获取视频字幕
uv run python -m youtube_scraper transcript <VIDEO_ID>

# 热门视频 + 字幕（一站式）
uv run python -m youtube_scraper full <CHANNEL_ID> --top 3 --lang <LANG_CODES>

# 可选保存原始结果到目录
uv run python -m youtube_scraper popular <CHANNEL_ID> --output <DIR>
```

## OpenClaw Skill 部署

```bash
# 默认部署到 ~/.openclaw/skills/holo-youtube-scraper
bash openclaw_deploy_skill.sh

# 或部署到自定义绝对路径
bash openclaw_deploy_skill.sh <ABS_TARGET_PATH>
```

部署内容：`SKILL.md`、`scripts/`、`references/`、`src/`、`pyproject.toml`、`uv.lock`、`.env.example`。

技能入口：

```bash
bash {baseDir}/scripts/youtube.sh help
bash {baseDir}/scripts/youtube.sh popular <CHANNEL_ID> --top 5
```

## 输出契约

CLI 与 bash 入口统一输出单个 JSON 信封：

- 成功：`ok=true`，包含 `command/input/result/meta`
- 失败：`ok=false`，包含 `command/input/error/meta`

详见：`references/output-schema.md`

## 编程接口

可直接作为 Python 库使用：

```python
from youtube_scraper import get_popular_videos, get_transcript

videos = get_popular_videos("<CHANNEL_ID>", top_n=5)
transcript = get_transcript("<VIDEO_ID>")
```

所有函数返回类型化 dataclass，支持 `.to_dict()` 序列化。

## 开发

```bash
uv run pytest
```

测试包含覆盖率门禁：`youtube_scraper` 包行覆盖率需 >= 90%。
