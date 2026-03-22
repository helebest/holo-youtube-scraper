"""Tests for automation/youtube_automation.py."""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from automation.youtube_automation import (
    AutomationConfigError,
    ChannelTarget,
    FetchConfig,
    ScheduleConfig,
    TaskConfig,
    _safe_component,
    execute_task,
    load_tasks,
)


def _make_task(
    name: str = "AI Tracker",
    mode: str = "latest_full",
    tz: str = "Asia/Shanghai",
    video_ids: tuple[str, ...] = ("dQw4w9WgXcQ",),
    channels: tuple[ChannelTarget, ...] = (),
    enabled: bool = True,
) -> TaskConfig:
    return TaskConfig(
        name=name,
        mode=mode,
        enabled=enabled,
        schedule=ScheduleConfig(kind="daily", time="08:00", timezone=tz, weekdays=()),
        fetch=FetchConfig(top_n=5, scan=100, languages=("en",), timeout=30.0, retries=2),
        channels=channels,
        video_ids=video_ids,
    )


def _make_channel(
    name: str = "Test Channel",
    enabled: bool = True,
    status: str = "active",
) -> ChannelTarget:
    return ChannelTarget(
        name=name,
        tier="t1",
        handle="@test",
        channel_id="UC_test",
        enabled=enabled,
        status=status,
    )


def _make_video_payload(video_id: str = "vid1") -> dict[str, object]:
    return {
        "id": video_id,
        "title": "Test Video",
        "channel_title": "Test Channel",
        "published_at": "2026-03-11T10:00:00Z",
        "description": "Test description",
        "duration": "PT10M",
        "view_count": 123,
        "like_count": 45,
        "comment_count": 6,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


class TestSafeComponent:
    def test_lowercase_and_spaces(self):
        assert _safe_component("AI Tracker") == "ai-tracker"

    def test_special_characters(self):
        assert _safe_component("My Channel!!!") == "my-channel"

    def test_already_clean(self):
        assert _safe_component("ai-tracker") == "ai-tracker"

    def test_empty_fallback(self):
        assert _safe_component("!!!") == "task"

    def test_leading_trailing_dots(self):
        assert _safe_component(".hidden.") == "hidden"


class TestTimezoneDateCalculation:
    def test_plan_uses_task_timezone_not_system_local(self):
        task = _make_task(name="tz_test", tz="Asia/Shanghai")
        now_utc = datetime(2026, 3, 11, 20, 0, 0, tzinfo=timezone.utc)

        with (
            patch("automation.youtube_automation._build_service"),
            patch("automation.youtube_automation._latest_full_for_channel", return_value=[]),
        ):
            result = execute_task(
                task,
                output_root=Path("/tmp/test"),
                now_utc=now_utc,
            )

        assert result.date == "2026-03-12"

        from automation.youtube_automation import compute_task_plan

        plan = compute_task_plan(task, output_root=Path("/tmp/test"), now_utc=now_utc)
        assert plan["date"] == result.date
        assert plan["branch"] == result.branch
        assert plan["output_dir"] == result.output_dir


class TestPlanRunConsistency:
    @pytest.mark.parametrize("task_name", ["AI Tracker", "ai_tracker", "hello world 123"])
    def test_branch_matches(self, task_name, tmp_path):
        task = _make_task(name=task_name)
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        from automation.youtube_automation import compute_task_plan

        plan = compute_task_plan(task, output_root=tmp_path, now_utc=now_utc)

        with (
            patch("automation.youtube_automation._build_service"),
            patch("automation.youtube_automation._latest_full_for_channel", return_value=[]),
        ):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        assert plan["branch"] == result.branch
        assert plan["date"] == result.date
        assert plan["output_dir"] == result.output_dir

    def test_explicit_run_date_overrides(self, tmp_path):
        task = _make_task(name="override_test")
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)
        override = date(2026, 1, 1)

        from automation.youtube_automation import compute_task_plan

        plan = compute_task_plan(task, output_root=tmp_path, run_date=override, now_utc=now_utc)

        with (
            patch("automation.youtube_automation._build_service"),
            patch("automation.youtube_automation._latest_full_for_channel", return_value=[]),
        ):
            result = execute_task(task, output_root=tmp_path, run_date=override, now_utc=now_utc)

        assert plan["date"] == "2026-01-01"
        assert plan["branch"] == result.branch
        assert plan["output_dir"] == result.output_dir


class TestChannelsAllSkipped:
    def test_all_channels_pending(self, tmp_path):
        channels = (
            _make_channel(name="ch1", status="pending"),
            _make_channel(name="ch2", status="pending"),
        )
        task = _make_task(name="pending_test", mode="popular_full", channels=channels, video_ids=())
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        with patch("automation.youtube_automation._build_service"):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        s = result.summary
        assert s["channels_ok"] == 0
        assert s["channels_skipped"] == 2
        assert s["channels_total"] == 0

    def test_all_channels_disabled(self, tmp_path):
        channels = (
            _make_channel(name="ch1", enabled=False),
            _make_channel(name="ch2", enabled=False),
        )
        task = _make_task(name="disabled_test", mode="latest_full", channels=channels, video_ids=())
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        with patch("automation.youtube_automation._build_service"):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        s = result.summary
        assert s["channels_total"] == 0
        assert s["channels_ok"] == 0
        assert s["channels_skipped"] == 2

    def test_mixed_skipped_and_ok(self, tmp_path):
        channels = (
            _make_channel(name="active", status="active"),
            _make_channel(name="pending", status="pending"),
        )
        task = _make_task(name="mixed_test", mode="popular_full", channels=channels, video_ids=())
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        with (
            patch("automation.youtube_automation._build_service"),
            patch("automation.youtube_automation._popular_full_for_channel", return_value=[]),
        ):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        s = result.summary
        assert s["channels_total"] == 1
        assert s["channels_ok"] == 1
        assert s["channels_skipped"] == 1


class TestAutomationPayloads:
    @pytest.mark.parametrize(
        ("mode", "patch_target"),
        [
            ("latest_full", "automation.youtube_automation._latest_full_for_channel"),
            ("popular_full", "automation.youtube_automation._popular_full_for_channel"),
        ],
    )
    def test_channel_payload_excludes_transcript_fields(self, mode, patch_target, tmp_path):
        task = _make_task(
            name=f"{mode}_task",
            mode=mode,
            channels=(_make_channel(),),
            video_ids=(),
        )
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        with patch("automation.youtube_automation._build_service"), patch(
            patch_target, return_value=[_make_video_payload()]
        ):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        channel_file = Path(result.output_dir) / "channels" / "test-channel.json"
        payload = json.loads(channel_file.read_text(encoding="utf-8"))

        assert payload["ok"] is True
        assert payload["meta"]["count"] == 1
        assert payload["result"] == [_make_video_payload()]
        assert not any(key.startswith("transcript") for key in payload["result"][0])


class TestConfigValidation:
    def test_transcript_only_mode_is_rejected(self, tmp_path):
        config_path = tmp_path / "automation-config.json"
        config_path.write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "name": "legacy_transcript_task",
                            "mode": "transcript_only",
                            "enabled": True,
                            "schedule": {"kind": "manual", "timezone": "Asia/Shanghai"},
                            "fetch": {"languages": ["en"]},
                            "video_ids": ["dQw4w9WgXcQ"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(AutomationConfigError, match="no longer supported by automation"):
            load_tasks(config_path)
