"""Task-based YouTube automation runner for GitHub Actions."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httplib2
from googleapiclient.discovery import build

from youtube_scraper.client import (
    get_channel_videos,
    get_popular_videos,
    get_video_details,
    sanitize_error_message,
)
from youtube_scraper.config import API_REQUEST_RETRIES, API_REQUEST_TIMEOUT_SECONDS, get_api_key
from youtube_scraper.models import TranscriptResult, VideoWithTranscript
from youtube_scraper.transcript import get_transcripts_batch

SUPPORTED_MODES = {"latest_full", "popular_full", "transcript_only"}
SUPPORTED_SCHEDULES = {"daily", "weekly", "manual"}
DEFAULT_TIMEZONE = "Asia/Shanghai"
FALLBACK_TIMEZONES = {
    "UTC": timezone.utc,
    "Asia/Shanghai": timezone(timedelta(hours=8)),
}
WEEKDAY_TO_INT = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


class AutomationConfigError(ValueError):
    """Invalid automation configuration."""


@dataclass(frozen=True)
class ChannelTarget:
    name: str
    tier: str | None
    handle: str | None
    channel_id: str | None
    enabled: bool
    status: str

    @property
    def is_pending(self) -> bool:
        return self.status.lower() == "pending"


@dataclass(frozen=True)
class ScheduleConfig:
    kind: str
    time: str | None
    timezone: str
    weekdays: tuple[str, ...]


@dataclass(frozen=True)
class FetchConfig:
    top_n: int
    scan: int
    languages: tuple[str, ...]
    timeout: float
    retries: int


@dataclass(frozen=True)
class TaskConfig:
    name: str
    mode: str
    enabled: bool
    schedule: ScheduleConfig
    fetch: FetchConfig
    channels: tuple[ChannelTarget, ...]
    video_ids: tuple[str, ...]


@dataclass(frozen=True)
class TaskRunResult:
    task: str
    mode: str
    date: str
    branch: str
    output_dir: str
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "mode": self.mode,
            "date": self.date,
            "branch": self.branch,
            "output_dir": self.output_dir,
            "summary": self.summary,
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("._-")
    return cleaned or "task"


def _get_timezone(name: str):
    try:
        return ZoneInfo(name)
    except Exception as exc:
        fallback = FALLBACK_TIMEZONES.get(name)
        if fallback is not None:
            return fallback
        raise exc

def _parse_hhmm(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{2}):(\d{2})", value or "")
    if not match:
        raise AutomationConfigError(f"Invalid schedule time '{value}'. Expected HH:MM.")
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        raise AutomationConfigError(f"Invalid schedule time '{value}'.")
    return hour, minute


def _parse_positive_int(value: Any, *, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AutomationConfigError(f"Invalid integer for {field}: {value!r}") from exc
    if parsed <= 0:
        raise AutomationConfigError(f"{field} must be positive, got {parsed}.")
    return parsed


def _parse_positive_float(value: Any, *, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise AutomationConfigError(f"Invalid float for {field}: {value!r}") from exc
    if parsed <= 0:
        raise AutomationConfigError(f"{field} must be positive, got {parsed}.")
    return parsed


def _load_yaml_or_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
    except ModuleNotFoundError:
        loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise AutomationConfigError("Automation config must be a YAML/JSON object.")
    return loaded


def _parse_channel(raw: dict[str, Any], *, task_name: str, index: int) -> ChannelTarget:
    name = str(raw.get("name", "")).strip()
    if not name:
        raise AutomationConfigError(f"tasks[{task_name}].channels[{index}] is missing name.")
    handle = raw.get("handle")
    if handle is not None:
        handle = str(handle).strip() or None
    channel_id = raw.get("channel_id")
    if channel_id is not None:
        channel_id = str(channel_id).strip() or None
    return ChannelTarget(
        name=name,
        tier=(str(raw.get("tier")).strip() if raw.get("tier") is not None else None),
        handle=handle,
        channel_id=channel_id,
        enabled=bool(raw.get("enabled", True)),
        status=str(raw.get("status", "active")).strip().lower() or "active",
    )


def _parse_schedule(raw: dict[str, Any], *, task_name: str) -> ScheduleConfig:
    kind = str(raw.get("kind", "manual")).strip().lower()
    if kind not in SUPPORTED_SCHEDULES:
        raise AutomationConfigError(
            f"tasks[{task_name}].schedule.kind must be one of {sorted(SUPPORTED_SCHEDULES)}."
        )
    time_value = raw.get("time")
    time_text = str(time_value).strip() if time_value is not None else None
    if kind in {"daily", "weekly"} and not time_text:
        raise AutomationConfigError(f"tasks[{task_name}] requires schedule.time for {kind}.")
    if time_text is not None:
        _parse_hhmm(time_text)

    tz_name = str(raw.get("timezone", DEFAULT_TIMEZONE)).strip() or DEFAULT_TIMEZONE
    try:
        _get_timezone(tz_name)
    except Exception as exc:
        raise AutomationConfigError(f"Invalid timezone '{tz_name}' in task '{task_name}'.") from exc

    weekdays_raw = raw.get("weekdays", [])
    if weekdays_raw is None:
        weekdays_raw = []
    if not isinstance(weekdays_raw, list):
        raise AutomationConfigError(f"tasks[{task_name}].schedule.weekdays must be a list.")
    weekdays = tuple(str(item).strip().lower() for item in weekdays_raw if str(item).strip())
    if kind == "weekly":
        if not weekdays:
            raise AutomationConfigError(f"tasks[{task_name}] weekly schedule requires weekdays.")
        unknown_days = [day for day in weekdays if day not in WEEKDAY_TO_INT]
        if unknown_days:
            raise AutomationConfigError(
                f"tasks[{task_name}] has invalid weekdays: {', '.join(unknown_days)}."
            )

    return ScheduleConfig(kind=kind, time=time_text, timezone=tz_name, weekdays=weekdays)


def _parse_fetch(raw: dict[str, Any], *, task_name: str) -> FetchConfig:
    langs_raw = raw.get("languages", [])
    if langs_raw is None:
        langs_raw = []
    if not isinstance(langs_raw, list):
        raise AutomationConfigError(f"tasks[{task_name}].fetch.languages must be a list.")
    languages = tuple(str(item).strip() for item in langs_raw if str(item).strip())

    return FetchConfig(
        top_n=_parse_positive_int(raw.get("top_n", 5), field=f"tasks[{task_name}].fetch.top_n"),
        scan=_parse_positive_int(raw.get("scan", 100), field=f"tasks[{task_name}].fetch.scan"),
        languages=languages,
        timeout=_parse_positive_float(
            raw.get("timeout", API_REQUEST_TIMEOUT_SECONDS),
            field=f"tasks[{task_name}].fetch.timeout",
        ),
        retries=_parse_positive_int(
            raw.get("retries", API_REQUEST_RETRIES),
            field=f"tasks[{task_name}].fetch.retries",
        ),
    )


def load_tasks(config_path: Path) -> dict[str, TaskConfig]:
    data = _load_yaml_or_json(config_path)
    tasks_raw = data.get("tasks")
    if not isinstance(tasks_raw, list):
        raise AutomationConfigError("Config must include a top-level 'tasks' list.")

    tasks: dict[str, TaskConfig] = {}
    for idx, raw_task in enumerate(tasks_raw):
        if not isinstance(raw_task, dict):
            raise AutomationConfigError(f"tasks[{idx}] must be an object.")

        name = str(raw_task.get("name", "")).strip()
        if not name:
            raise AutomationConfigError(f"tasks[{idx}] is missing name.")
        if name in tasks:
            raise AutomationConfigError(f"Duplicate task name: {name}")

        mode = str(raw_task.get("mode", "")).strip().lower()
        if mode not in SUPPORTED_MODES:
            raise AutomationConfigError(
                f"tasks[{name}].mode must be one of {sorted(SUPPORTED_MODES)}."
            )

        channels_raw = raw_task.get("channels", [])
        if channels_raw is None:
            channels_raw = []
        if not isinstance(channels_raw, list):
            raise AutomationConfigError(f"tasks[{name}].channels must be a list.")
        channels = tuple(
            _parse_channel(channel, task_name=name, index=i)
            for i, channel in enumerate(channels_raw)
        )

        video_ids_raw = raw_task.get("video_ids", [])
        if video_ids_raw is None:
            video_ids_raw = []
        if not isinstance(video_ids_raw, list):
            raise AutomationConfigError(f"tasks[{name}].video_ids must be a list.")
        video_ids = tuple(str(item).strip() for item in video_ids_raw if str(item).strip())

        if mode == "transcript_only" and not video_ids:
            raise AutomationConfigError(f"tasks[{name}] transcript_only requires video_ids.")

        tasks[name] = TaskConfig(
            name=name,
            mode=mode,
            enabled=bool(raw_task.get("enabled", True)),
            schedule=_parse_schedule(raw_task.get("schedule", {}), task_name=name),
            fetch=_parse_fetch(raw_task.get("fetch", {}), task_name=name),
            channels=channels,
            video_ids=video_ids,
        )
    return tasks


def is_task_due(task: TaskConfig, now_utc: datetime | None = None) -> bool:
    if not task.enabled:
        return False
    if task.schedule.kind == "manual":
        return False

    current_utc = now_utc or _utc_now()
    if current_utc.tzinfo is None:
        current_utc = current_utc.replace(tzinfo=timezone.utc)
    local_dt = current_utc.astimezone(_get_timezone(task.schedule.timezone))

    assert task.schedule.time is not None  # guarded by config validation
    schedule_hour, schedule_minute = _parse_hhmm(task.schedule.time)
    if local_dt.hour != schedule_hour or local_dt.minute != schedule_minute:
        return False

    if task.schedule.kind == "weekly":
        expected = {WEEKDAY_TO_INT[day] for day in task.schedule.weekdays}
        return local_dt.weekday() in expected
    return True


def select_tasks(
    tasks: dict[str, TaskConfig],
    *,
    run_mode: str,
    task_name: str | None = None,
    now_utc: datetime | None = None,
) -> list[TaskConfig]:
    if run_mode == "task":
        if not task_name:
            raise AutomationConfigError("run_mode=task requires --task-name.")
        task = tasks.get(task_name)
        if task is None:
            raise AutomationConfigError(f"Task not found: {task_name}")
        if not task.enabled:
            raise AutomationConfigError(f"Task is disabled: {task_name}")
        return [task]

    enabled_tasks = [task for task in tasks.values() if task.enabled]
    if run_mode == "all":
        return enabled_tasks
    if run_mode == "due":
        return [task for task in enabled_tasks if is_task_due(task, now_utc=now_utc)]
    raise AutomationConfigError("run_mode must be one of: due, all, task.")


def _build_service(timeout: float):
    return build(
        "youtube",
        "v3",
        developerKey=get_api_key(),
        http=httplib2.Http(timeout=timeout),
        cache_discovery=False,
    )


def _resolve_channel_id_from_handle(*, handle: str, service, retries: int) -> str:
    cleaned_handle = handle.strip().lstrip("@")
    if not cleaned_handle:
        raise ValueError("Channel handle is empty.")
    response = service.channels().list(part="id,snippet", forHandle=cleaned_handle).execute(
        num_retries=retries
    )
    items = response.get("items", [])
    if not items:
        raise ValueError(f"Channel handle not found: @{cleaned_handle}")
    return str(items[0]["id"])


def _latest_full_for_channel(
    *,
    channel_id: str,
    fetch: FetchConfig,
    service,
) -> list[dict[str, Any]]:
    video_ids = get_channel_videos(
        channel_id,
        max_results=fetch.scan,
        service=service,
        retries=fetch.retries,
        timeout=fetch.timeout,
    )
    videos = get_video_details(
        video_ids,
        service=service,
        retries=fetch.retries,
        timeout=fetch.timeout,
    )
    videos.sort(key=lambda item: item.published_at, reverse=True)
    selected = videos[: fetch.top_n]
    transcripts = get_transcripts_batch(
        [video.id for video in selected],
        languages=list(fetch.languages) or None,
    )
    transcript_by_video_id = {result.video_id: result for result in transcripts}
    merged = [
        VideoWithTranscript(video=video, transcript=transcript_by_video_id[video.id]).to_dict()
        for video in selected
    ]
    return merged


def _popular_full_for_channel(
    *,
    channel_id: str,
    fetch: FetchConfig,
    service,
) -> list[dict[str, Any]]:
    videos = get_popular_videos(
        channel_id,
        top_n=fetch.top_n,
        max_results=fetch.scan,
        service=service,
        retries=fetch.retries,
        timeout=fetch.timeout,
    )
    transcripts = get_transcripts_batch(
        [video.id for video in videos],
        languages=list(fetch.languages) or None,
    )
    transcript_by_video_id = {result.video_id: result for result in transcripts}
    merged = [
        VideoWithTranscript(video=video, transcript=transcript_by_video_id[video.id]).to_dict()
        for video in videos
    ]
    return merged


def _transcript_only(task: TaskConfig, *, fetch: FetchConfig) -> list[dict[str, Any]]:
    transcripts: list[TranscriptResult] = get_transcripts_batch(
        list(task.video_ids),
        languages=list(fetch.languages) or None,
    )
    return [item.to_dict() for item in transcripts]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_task_plan(
    task: TaskConfig,
    *,
    output_root: Path,
    run_date: date | None = None,
    now_utc: datetime | None = None,
) -> dict[str, str]:
    """Compute date/branch/output_dir consistently for both plan and run."""
    local_now = (now_utc or _utc_now()).astimezone(_get_timezone(task.schedule.timezone))
    effective_date = run_date or local_now.date()
    date_text = effective_date.isoformat()
    safe_task_name = _safe_component(task.name)
    return {
        "date": date_text,
        "branch": f"data_{safe_task_name}/{date_text}",
        "output_dir": str(output_root / safe_task_name / date_text),
    }


def execute_task(
    task: TaskConfig,
    *,
    output_root: Path,
    run_date: date | None = None,
    now_utc: datetime | None = None,
) -> TaskRunResult:
    plan = compute_task_plan(
        task, output_root=output_root, run_date=run_date, now_utc=now_utc,
    )
    date_text = plan["date"]
    safe_task_name = _safe_component(task.name)

    output_dir = output_root / safe_task_name / date_text
    channels_dir = output_dir / "channels"
    channels_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "generated_at": _utc_iso(),
        "task_name": task.name,
        "mode": task.mode,
        "timezone": task.schedule.timezone,
        "channels_total": 0,
        "channels_ok": 0,
        "channels_failed": 0,
        "channels_skipped": 0,
        "videos_total": 0,
    }

    if task.mode == "transcript_only":
        transcripts = _transcript_only(task, fetch=task.fetch)
        payload = {
            "ok": True,
            "task": task.name,
            "mode": task.mode,
            "date": date_text,
            "result": transcripts,
            "meta": {"count": len(transcripts), "generated_at": _utc_iso()},
        }
        _write_json(output_dir / "transcripts.json", payload)
        summary["videos_total"] = len(transcripts)
        summary["channels_total"] = 0
        _write_json(output_dir / "manifest.json", summary)
        return TaskRunResult(
            task=task.name,
            mode=task.mode,
            date=plan["date"],
            branch=plan["branch"],
            output_dir=plan["output_dir"],
            summary=summary,
        )

    service = _build_service(timeout=task.fetch.timeout)
    for channel in task.channels:
        file_name = _safe_component(channel.name)
        channel_payload: dict[str, Any] = {
            "ok": False,
            "task": task.name,
            "mode": task.mode,
            "channel": {
                "name": channel.name,
                "tier": channel.tier,
                "handle": channel.handle,
                "channel_id": channel.channel_id,
                "status": channel.status,
                "enabled": channel.enabled,
            },
            "date": date_text,
            "result": [],
            "error": None,
            "meta": {"generated_at": _utc_iso(), "count": 0},
        }

        if not channel.enabled:
            summary["channels_skipped"] += 1
            channel_payload["error"] = {"code": "CHANNEL_DISABLED", "message": "Channel is disabled."}
            _write_json(channels_dir / f"{file_name}.json", channel_payload)
            continue
        if channel.is_pending:
            summary["channels_skipped"] += 1
            channel_payload["error"] = {
                "code": "PENDING_CHANNEL",
                "message": "Channel is pending and skipped until identifiers are completed.",
            }
            _write_json(channels_dir / f"{file_name}.json", channel_payload)
            continue

        try:
            channel_id = channel.channel_id
            if not channel_id:
                if not channel.handle:
                    raise ValueError("Missing channel_id/handle for channel target.")
                channel_id = _resolve_channel_id_from_handle(
                    handle=channel.handle,
                    service=service,
                    retries=task.fetch.retries,
                )

            channel_payload["channel"]["resolved_channel_id"] = channel_id
            if task.mode == "latest_full":
                result = _latest_full_for_channel(channel_id=channel_id, fetch=task.fetch, service=service)
            elif task.mode == "popular_full":
                result = _popular_full_for_channel(channel_id=channel_id, fetch=task.fetch, service=service)
            else:
                raise RuntimeError(f"Unsupported mode at runtime: {task.mode}")

            channel_payload["ok"] = True
            channel_payload["result"] = result
            channel_payload["meta"]["count"] = len(result)
            summary["channels_ok"] += 1
            summary["videos_total"] += len(result)
        except Exception as exc:
            summary["channels_failed"] += 1
            channel_payload["error"] = {
                "code": type(exc).__name__,
                "message": sanitize_error_message(str(exc)),
            }
        _write_json(channels_dir / f"{file_name}.json", channel_payload)

    summary["channels_total"] = summary["channels_ok"] + summary["channels_failed"]
    _write_json(output_dir / "manifest.json", summary)
    return TaskRunResult(
        task=task.name,
        mode=task.mode,
        date=plan["date"],
        branch=plan["branch"],
        output_dir=plan["output_dir"],
        summary=summary,
    )


def _parse_iso_utc(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="youtube-automation",
        description="Task runner used by GitHub Actions for channel monitoring.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_list = subparsers.add_parser("list", help="List selected task names.")
    p_list.add_argument("--config", default=".github/youtube-tasks.yml", help="Path to task config.")
    p_list.add_argument("--run-mode", choices=["due", "all", "task"], required=True)
    p_list.add_argument("--task-name", default=None, help="Task name for run-mode=task.")
    p_list.add_argument(
        "--now-utc",
        default=None,
        help="Override current UTC timestamp, e.g. 2026-03-08T13:00:00Z.",
    )

    p_run = subparsers.add_parser("run", help="Run a single task and write output data.")
    p_run.add_argument("--config", default=".github/youtube-tasks.yml", help="Path to task config.")
    p_run.add_argument("--task-name", required=True, help="Task name to execute.")
    p_run.add_argument("--output-root", default="data", help="Root output folder.")
    p_run.add_argument("--run-date", default=None, help="Override logical run date (YYYY-MM-DD).")
    p_run.add_argument(
        "--now-utc",
        default=None,
        help="Override current UTC timestamp, e.g. 2026-03-08T13:00:00Z.",
    )

    p_plan = subparsers.add_parser("plan", help="Plan task execution (get branch/date info).")
    p_plan.add_argument("--config", default=".github/youtube-tasks.yml", help="Path to task config.")
    p_plan.add_argument("--task-name", required=True, help="Task name to plan.")
    p_plan.add_argument("--output-root", default="data", help="Root output folder.")
    p_plan.add_argument("--run-date", default=None, help="Override logical run date (YYYY-MM-DD).")
    p_plan.add_argument(
        "--now-utc",
        default=None,
        help="Override current UTC timestamp, e.g. 2026-03-08T13:00:00Z.",
    )
    return parser


def _emit_success(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, ensure_ascii=False))


def _emit_error(message: str, *, error_type: str = "AutomationError") -> None:
    print(
        json.dumps(
            {
                "ok": False,
                "error": {
                    "type": error_type,
                    "message": sanitize_error_message(message),
                },
                "meta": {"generated_at": _utc_iso()},
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        config_path = Path(args.config)
        tasks = load_tasks(config_path)
        now_utc = _parse_iso_utc(args.now_utc) if args.now_utc else _utc_now()

        if args.command == "list":
            selected = select_tasks(
                tasks,
                run_mode=args.run_mode,
                task_name=args.task_name,
                now_utc=now_utc,
            )
            _emit_success(
                {
                    "command": "list",
                    "run_mode": args.run_mode,
                    "tasks": [item.name for item in selected],
                    "meta": {"generated_at": _utc_iso()},
                }
            )
            return

        if args.command == "run":
            task = tasks.get(args.task_name)
            if task is None:
                raise AutomationConfigError(f"Task not found: {args.task_name}")
            if not task.enabled:
                raise AutomationConfigError(f"Task is disabled: {task.name}")
            logical_date = date.fromisoformat(args.run_date) if args.run_date else None
            result = execute_task(
                task,
                output_root=Path(args.output_root),
                run_date=logical_date,
                now_utc=now_utc,
            )
            _emit_success({"command": "run", "result": result.to_dict(), "meta": {"generated_at": _utc_iso()}})
            return

        if args.command == "plan":
            task = tasks.get(args.task_name)
            if task is None:
                raise AutomationConfigError(f"Task not found: {args.task_name}")
            if not task.enabled:
                raise AutomationConfigError(f"Task is disabled: {task.name}")
            logical_date = date.fromisoformat(args.run_date) if args.run_date else None
            plan_info = compute_task_plan(
                task,
                output_root=Path(args.output_root),
                run_date=logical_date,
                now_utc=now_utc,
            )
            _emit_success({
                "command": "plan",
                "result": {
                    "task": task.name,
                    **plan_info,
                },
                "meta": {"generated_at": _utc_iso()},
            })
            return

        raise AutomationConfigError(f"Unsupported command: {args.command}")
    except AutomationConfigError as exc:
        _emit_error(str(exc), error_type="AutomationConfigError")
        raise SystemExit(2)
    except Exception as exc:
        _emit_error(str(exc), error_type=type(exc).__name__)
        raise SystemExit(1)


if __name__ == "__main__":
    main()





