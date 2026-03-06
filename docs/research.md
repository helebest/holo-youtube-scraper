# YouTube Scraper 调研文档

## YouTube Data API v3 核心接口

| 接口 | 用途 | 配额消耗 |
|------|------|----------|
| `channels.list` | 获取频道元数据（名称、统计、uploads playlist ID） | 1 单位 |
| `playlistItems.list` | 分页获取播放列表中的视频 ID（每页最多 50 个） | 1 单位/页 |
| `videos.list` | 批量获取视频详情（统计数据、时长等，每次最多 50 个 ID） | 1 单位/次 |
| `search.list` | 搜索视频（支持排序，但配额昂贵） | **100 单位/次** |

## 热点视频获取策略对比

### 策略 A: search.list (order=viewCount)

- 直接调用 `search.list(channelId=..., order=viewCount)`
- 优点：一步到位，API 自动排序
- 缺点：每次调用消耗 **100 配额单位**，获取 50 个视频就需要 100 单位
- 适用：偶尔查询、不在意配额

### 策略 B: playlistItems.list + videos.list (本项目采用)

1. `channels.list` 获取 uploads playlist ID → 1 单位
2. `playlistItems.list` 分页拉取视频 ID → 1 单位/页（50 个/页）
3. `videos.list` 批量获取统计数据 → 1 单位/次（50 个 ID/次）
4. 本地按 viewCount 排序

- 获取 500 个视频并排序：1 + 10 + 10 = **21 单位**
- 获取 50 个视频并排序：1 + 1 + 1 = **3 单位**
- 远优于策略 A

### 结论

采用策略 B，配额消耗降低约 80%。

## 配额限制

- 每日免费配额：**10,000 单位**
- 策略 B 下可支持约 400+ 次完整查询（每次 ~21 单位）
- 建议：缓存结果，避免重复查询

## 库选型

| 库 | 用途 | 说明 |
|----|------|------|
| `google-api-python-client` | YouTube Data API 调用 | Google 官方 Python 客户端 |
| `youtube-transcript-api` | 字幕/转录文本提取 | 不依赖 API Key，直接抓取字幕 |
| `rich` | CLI 美化输出 | 表格、颜色、进度条 |

## API Key 获取

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建项目（或选择已有项目）
3. 启用 YouTube Data API v3：API 和服务 → 库 → 搜索 "YouTube Data API v3" → 启用
4. 创建凭据：API 和服务 → 凭据 → 创建凭据 → API 密钥
5. 将 API Key 写入项目根目录 `.env` 文件：`YOUTUBE_API_KEY=your_key_here`
