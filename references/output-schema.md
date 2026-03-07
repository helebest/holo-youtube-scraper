# 输出结构

所有命令都输出单个 JSON 对象。

## 成功

```json
{
  "ok": true,
  "command": "popular|transcript|full",
  "input": {},
  "result": {},
  "meta": {
    "generated_at": "<ISO_8601_UTC>",
    "count": 0,
    "saved_to": "<OPTIONAL_PATH>"
  }
}
```

说明：
- `meta.count` 主要用于列表结果。
- `meta.saved_to` 仅在使用 `--output` 时出现。

## 失败

```json
{
  "ok": false,
  "command": "popular|transcript|full|null",
  "input": {},
  "error": {
    "type": "<ERROR_TYPE>",
    "code": "<ERROR_CODE>",
    "message": "<ERROR_MESSAGE>"
  },
  "meta": {
    "generated_at": "<ISO_8601_UTC>"
  }
}
```

常见 `error.code`：
- `INVALID_ARGUMENTS`
- `TRANSCRIPT_UNAVAILABLE`
- `UNEXPECTED_ERROR`
- `INVALID_COMMAND`（bash 入口层）
