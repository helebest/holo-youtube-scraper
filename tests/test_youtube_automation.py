"""Tests for scripts/youtube_automation.py — plan/run consistency."""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# The script lives under scripts/ which isn't a package; import helpers directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from youtube_automation import (
    AutomationConfigError,
    ChannelTarget,
    FetchConfig,
    ScheduleConfig,
    TaskConfig,
    TaskRunResult,
    _safe_component,
    execute_task,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(
    name: str = "AI Tracker",
    mode: str = "transcript_only",
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


# ---------------------------------------------------------------------------
# 1. Task name normalisation — _safe_component
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 2. Timezone date calculation — plan must use task tz, not system local
# ---------------------------------------------------------------------------

class TestTimezoneDateCalculation:
    """When UTC time is 2026-03-11T20:00:00Z (evening UTC), it's already
    2026-03-12 in Asia/Shanghai (UTC+8).  Plan and run must agree on the
    date derived from the task timezone, not the system clock."""

    def test_plan_uses_task_timezone_not_system_local(self):
        """plan command must produce the same date as execute_task for identical now_utc."""
        task = _make_task(name="tz_test", tz="Asia/Shanghai")
        # 20:00 UTC on March 11 → 04:00 March 12 in Shanghai
        now_utc = datetime(2026, 3, 11, 20, 0, 0, tzinfo=timezone.utc)

        with patch("youtube_automation.get_transcripts_batch", return_value=[]):
            result = execute_task(
                task,
                output_root=Path("/tmp/test"),
                now_utc=now_utc,
            )

        assert result.date == "2026-03-12", (
            "execute_task must compute date in task timezone (Asia/Shanghai)"
        )

        # Now verify plan would produce the same values.
        # We import main's plan logic indirectly by calling compute_task_plan.
        from youtube_automation import compute_task_plan

        plan = compute_task_plan(task, output_root=Path("/tmp/test"), now_utc=now_utc)
        assert plan["date"] == result.date
        assert plan["branch"] == result.branch
        assert plan["output_dir"] == result.output_dir


# ---------------------------------------------------------------------------
# 3. plan / run consistency
# ---------------------------------------------------------------------------

class TestPlanRunConsistency:
    """plan and run (execute_task) must return identical branch, date, and
    output_dir for the same inputs."""

    @pytest.mark.parametrize("task_name", ["AI Tracker", "ai_tracker", "hello world 123"])
    def test_branch_matches(self, task_name, tmp_path):
        task = _make_task(name=task_name)
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        from youtube_automation import compute_task_plan

        plan = compute_task_plan(task, output_root=tmp_path, now_utc=now_utc)

        with patch("youtube_automation.get_transcripts_batch", return_value=[]):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        assert plan["branch"] == result.branch
        assert plan["date"] == result.date
        assert plan["output_dir"] == result.output_dir

    def test_explicit_run_date_overrides(self, tmp_path):
        task = _make_task(name="override_test")
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)
        override = date(2026, 1, 1)

        from youtube_automation import compute_task_plan

        plan = compute_task_plan(task, output_root=tmp_path, run_date=override, now_utc=now_utc)

        with patch("youtube_automation.get_transcripts_batch", return_value=[]):
            result = execute_task(task, output_root=tmp_path, run_date=override, now_utc=now_utc)

        assert plan["date"] == "2026-01-01"
        assert plan["branch"] == result.branch
        assert plan["output_dir"] == result.output_dir


# ---------------------------------------------------------------------------
# 4. channels_ok=0 when all channels are skipped → not a failure
# ---------------------------------------------------------------------------

class TestChannelsAllSkipped:
    """When every channel is disabled or pending, channels_ok=0 is expected.
    The summary.channels_total must reflect only *attempted* channels so the
    workflow check  (CHANNELS_TOTAL > 0 && CHANNELS_OK == 0)  does not
    wrongly fail."""

    def test_all_channels_pending(self, tmp_path):
        channels = (
            _make_channel(name="ch1", status="pending"),
            _make_channel(name="ch2", status="pending"),
        )
        task = _make_task(name="pending_test", mode="popular_full", channels=channels, video_ids=())
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        with patch("youtube_automation._build_service"):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        s = result.summary
        assert s["channels_ok"] == 0
        assert s["channels_skipped"] == 2
        # Critical: channels_total must NOT be > 0 when all are skipped,
        # otherwise workflow incorrectly marks the task as failed.
        assert s["channels_total"] == 0, (
            "channels_total should count only attempted channels (ok + failed)"
        )

    def test_all_channels_disabled(self, tmp_path):
        channels = (
            _make_channel(name="ch1", enabled=False),
            _make_channel(name="ch2", enabled=False),
        )
        task = _make_task(name="disabled_test", mode="latest_full", channels=channels, video_ids=())
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        with patch("youtube_automation._build_service"):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        s = result.summary
        assert s["channels_total"] == 0
        assert s["channels_ok"] == 0
        assert s["channels_skipped"] == 2

    def test_mixed_skipped_and_ok(self, tmp_path):
        """One active channel succeeds, one is pending — channels_total = 1."""
        channels = (
            _make_channel(name="active", status="active"),
            _make_channel(name="pending", status="pending"),
        )
        task = _make_task(name="mixed_test", mode="popular_full", channels=channels, video_ids=())
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        with (
            patch("youtube_automation._build_service"),
            patch("youtube_automation._popular_full_for_channel", return_value=[]),
        ):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        s = result.summary
        assert s["channels_total"] == 1  # only the attempted channel
        assert s["channels_ok"] == 1
        assert s["channels_skipped"] == 1
