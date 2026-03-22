"""Tests for automation/youtube_automation.py."""

import json
from argparse import Namespace
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import automation.youtube_automation as automation_mod
from automation.youtube_automation import (
    AutomationConfigError,
    ChannelTarget,
    FetchConfig,
    ScheduleConfig,
    TaskConfig,
    _safe_component,
    execute_task,
    is_task_due,
    load_tasks,
    main,
    select_tasks,
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

    def test_load_tasks_json_fallback_without_yaml_module(self, tmp_path, monkeypatch):
        config_path = tmp_path / "automation-config.json"
        config_path.write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "name": "daily_task",
                            "mode": "latest_full",
                            "schedule": {"kind": "daily", "time": "08:00", "timezone": "UTC"},
                            "fetch": {"top_n": 2, "scan": 5, "languages": ["en"], "timeout": 10, "retries": 2},
                            "channels": [{"name": "Test Channel", "handle": "@test"}],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "yaml":
                raise ModuleNotFoundError("yaml intentionally unavailable")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)

        tasks = load_tasks(config_path)
        assert tasks["daily_task"].fetch.languages == ("en",)
        assert tasks["daily_task"].channels[0].handle == "@test"

    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            ({"tasks": None}, "top-level 'tasks' list"),
            ({"tasks": ["bad"]}, "must be an object"),
            ({"tasks": [{"mode": "latest_full"}]}, "missing name"),
            (
                {
                    "tasks": [
                        {"name": "dup", "mode": "latest_full", "schedule": {"kind": "manual"}, "fetch": {}},
                        {"name": "dup", "mode": "latest_full", "schedule": {"kind": "manual"}, "fetch": {}},
                    ]
                },
                "Duplicate task name",
            ),
            (
                {
                    "tasks": [
                        {"name": "bad", "mode": "weird", "schedule": {"kind": "manual"}, "fetch": {}},
                    ]
                },
                "must be one of",
            ),
        ],
    )
    def test_load_tasks_validation_errors(self, payload, message, tmp_path):
        config_path = tmp_path / "bad-config.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(AutomationConfigError, match=message):
            load_tasks(config_path)


class TestHelperValidation:
    def test_parse_hhmm_accepts_and_rejects_values(self):
        assert automation_mod._parse_hhmm("09:30") == (9, 30)
        with pytest.raises(AutomationConfigError, match="Expected HH:MM"):
            automation_mod._parse_hhmm("930")
        with pytest.raises(AutomationConfigError, match="Invalid schedule time"):
            automation_mod._parse_hhmm("24:00")

    def test_parse_positive_number_helpers(self):
        assert automation_mod._parse_positive_int("5", field="x") == 5
        assert automation_mod._parse_positive_float("1.5", field="x") == 1.5

        with pytest.raises(AutomationConfigError, match="Invalid integer"):
            automation_mod._parse_positive_int("nope", field="x")
        with pytest.raises(AutomationConfigError, match="must be positive"):
            automation_mod._parse_positive_int(0, field="x")
        with pytest.raises(AutomationConfigError, match="Invalid float"):
            automation_mod._parse_positive_float("nope", field="x")
        with pytest.raises(AutomationConfigError, match="must be positive"):
            automation_mod._parse_positive_float(0, field="x")

    def test_get_timezone_fallback_and_invalid(self, monkeypatch):
        class Boom(Exception):
            pass

        monkeypatch.setattr(automation_mod, "ZoneInfo", lambda _: (_ for _ in ()).throw(Boom("bad tz")))
        assert automation_mod._get_timezone("UTC") == timezone.utc
        with pytest.raises(Boom):
            automation_mod._get_timezone("Mars/Phobos")

    def test_parse_channel_validation(self):
        channel = automation_mod._parse_channel(
            {"name": "Example", "tier": "t1", "handle": " @test ", "channel_id": " ", "status": " ACTIVE "},
            task_name="demo",
            index=0,
        )
        assert channel.name == "Example"
        assert channel.handle == "@test"
        assert channel.channel_id is None
        assert channel.status == "active"

        with pytest.raises(AutomationConfigError, match="missing name"):
            automation_mod._parse_channel({}, task_name="demo", index=0)

    def test_parse_schedule_validation(self):
        schedule = automation_mod._parse_schedule(
            {"kind": "weekly", "time": "08:15", "timezone": "UTC", "weekdays": ["mon", "wed"]},
            task_name="demo",
        )
        assert schedule.kind == "weekly"
        assert schedule.weekdays == ("mon", "wed")

        with pytest.raises(AutomationConfigError, match="must be one of"):
            automation_mod._parse_schedule({"kind": "hourly"}, task_name="demo")
        with pytest.raises(AutomationConfigError, match="requires schedule.time"):
            automation_mod._parse_schedule({"kind": "daily"}, task_name="demo")
        with pytest.raises(AutomationConfigError, match="Invalid timezone"):
            automation_mod._parse_schedule({"kind": "manual", "timezone": "Mars/Phobos"}, task_name="demo")
        with pytest.raises(AutomationConfigError, match="weekdays must be a list"):
            automation_mod._parse_schedule(
                {"kind": "weekly", "time": "08:15", "weekdays": "mon"},
                task_name="demo",
            )
        with pytest.raises(AutomationConfigError, match="requires weekdays"):
            automation_mod._parse_schedule({"kind": "weekly", "time": "08:15"}, task_name="demo")
        with pytest.raises(AutomationConfigError, match="invalid weekdays"):
            automation_mod._parse_schedule(
                {"kind": "weekly", "time": "08:15", "weekdays": ["funday"]},
                task_name="demo",
            )

    def test_parse_fetch_validation(self):
        fetch = automation_mod._parse_fetch(
            {"top_n": 2, "scan": 4, "languages": ["en", "zh"], "timeout": 12, "retries": 5},
            task_name="demo",
        )
        assert fetch.languages == ("en", "zh")
        assert fetch.timeout == 12.0

        with pytest.raises(AutomationConfigError, match="languages must be a list"):
            automation_mod._parse_fetch({"languages": "en"}, task_name="demo")

    def test_parse_iso_utc_and_task_run_result_to_dict(self):
        parsed = automation_mod._parse_iso_utc("2026-03-08T13:00:00")
        assert parsed.tzinfo == timezone.utc
        assert parsed.isoformat().endswith("+00:00")

        result = automation_mod.TaskRunResult(
            task="demo",
            mode="latest_full",
            date="2026-03-08",
            branch="data_demo/2026-03-08",
            output_dir="data/demo/2026-03-08",
            summary={"channels_ok": 1},
        )
        assert result.to_dict()["task"] == "demo"


class TestTaskSelection:
    def test_is_task_due_daily_and_weekly(self):
        daily = _make_task()
        now_utc = datetime(2026, 3, 12, 0, 0, 0, tzinfo=timezone.utc)
        assert is_task_due(daily, now_utc=now_utc) is True

        weekly = TaskConfig(
            name="weekly",
            mode="latest_full",
            enabled=True,
            schedule=ScheduleConfig(kind="weekly", time="08:00", timezone="Asia/Shanghai", weekdays=("thu",)),
            fetch=daily.fetch,
            channels=(),
            video_ids=(),
        )
        assert is_task_due(weekly, now_utc=now_utc) is True

        disabled = TaskConfig(
            name="disabled",
            mode="latest_full",
            enabled=False,
            schedule=daily.schedule,
            fetch=daily.fetch,
            channels=(),
            video_ids=(),
        )
        assert is_task_due(disabled, now_utc=now_utc) is False
        manual = TaskConfig(
            name="manual",
            mode="latest_full",
            enabled=True,
            schedule=ScheduleConfig(kind="manual", time=None, timezone="UTC", weekdays=()),
            fetch=daily.fetch,
            channels=(),
            video_ids=(),
        )
        assert is_task_due(manual, now_utc=now_utc) is False
        assert is_task_due(daily, now_utc=datetime(2026, 3, 11, 23, 59, tzinfo=timezone.utc)) is False

    def test_select_tasks_variants(self):
        due_task = _make_task(name="due_task")
        disabled_task = _make_task(name="disabled_task", enabled=False)
        tasks = {due_task.name: due_task, disabled_task.name: disabled_task}
        now_utc = datetime(2026, 3, 12, 0, 0, 0, tzinfo=timezone.utc)

        assert select_tasks(tasks, run_mode="all", now_utc=now_utc) == [due_task]
        assert select_tasks(tasks, run_mode="due", now_utc=now_utc) == [due_task]
        assert select_tasks(tasks, run_mode="task", task_name="due_task", now_utc=now_utc) == [due_task]

        with pytest.raises(AutomationConfigError, match="requires --task-name"):
            select_tasks(tasks, run_mode="task", now_utc=now_utc)
        with pytest.raises(AutomationConfigError, match="Task not found"):
            select_tasks(tasks, run_mode="task", task_name="missing", now_utc=now_utc)
        with pytest.raises(AutomationConfigError, match="Task is disabled"):
            select_tasks(tasks, run_mode="task", task_name="disabled_task", now_utc=now_utc)
        with pytest.raises(AutomationConfigError, match="run_mode must be one of"):
            select_tasks(tasks, run_mode="bad", now_utc=now_utc)


class TestAutomationHelpers:
    def test_build_service_uses_api_key_and_timeout(self, monkeypatch):
        captured: dict[str, object] = {}

        def fake_build(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return "service"

        monkeypatch.setattr(automation_mod, "get_api_key", lambda: "test-key")
        monkeypatch.setattr(automation_mod, "build", fake_build)

        result = automation_mod._build_service(timeout=12.5)

        assert result == "service"
        assert captured["args"] == ("youtube", "v3")
        assert captured["kwargs"]["developerKey"] == "test-key"
        assert captured["kwargs"]["http"].timeout == 12.5

    def test_resolve_channel_id_from_handle(self):
        service = MagicMock()
        service.channels().list.return_value.execute.return_value = {"items": [{"id": "UC123"}]}
        assert automation_mod._resolve_channel_id_from_handle(handle="@demo", service=service, retries=2) == "UC123"

        with pytest.raises(ValueError, match="empty"):
            automation_mod._resolve_channel_id_from_handle(handle="@", service=service, retries=2)

        service.channels().list.return_value.execute.return_value = {"items": []}
        with pytest.raises(ValueError, match="not found"):
            automation_mod._resolve_channel_id_from_handle(handle="@demo", service=service, retries=2)

    def test_latest_and_popular_helpers(self):
        fetch = FetchConfig(top_n=2, scan=5, languages=(), timeout=30.0, retries=2)
        videos = [
            MagicMock(published_at="2026-03-10T00:00:00Z", to_dict=lambda: {"id": "old"}),
            MagicMock(published_at="2026-03-11T00:00:00Z", to_dict=lambda: {"id": "new"}),
            MagicMock(published_at="2026-03-09T00:00:00Z", to_dict=lambda: {"id": "older"}),
        ]

        with (
            patch("automation.youtube_automation.get_channel_videos", return_value=["a", "b", "c"]),
            patch("automation.youtube_automation.get_video_details", return_value=videos),
        ):
            assert automation_mod._latest_full_for_channel(channel_id="UC", fetch=fetch, service=object()) == [
                {"id": "new"},
                {"id": "old"},
            ]

        popular_videos = [MagicMock(to_dict=lambda: {"id": "hot"})]
        with patch("automation.youtube_automation.get_popular_videos", return_value=popular_videos):
            assert automation_mod._popular_full_for_channel(channel_id="UC", fetch=fetch, service=object()) == [
                {"id": "hot"}
            ]

    def test_execute_task_handle_resolution_and_failure_payload(self, tmp_path):
        channels = (
            ChannelTarget(name="resolved", tier="t1", handle="@resolved", channel_id=None, enabled=True, status="active"),
            ChannelTarget(name="broken", tier="t1", handle=None, channel_id=None, enabled=True, status="active"),
        )
        task = _make_task(name="resolve_task", channels=channels, video_ids=())
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        with (
            patch("automation.youtube_automation._build_service", return_value=MagicMock()),
            patch("automation.youtube_automation._resolve_channel_id_from_handle", return_value="UC_RESOLVED"),
            patch("automation.youtube_automation._latest_full_for_channel", return_value=[_make_video_payload("vid2")]),
        ):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        resolved_payload = json.loads(
            (Path(result.output_dir) / "channels" / "resolved.json").read_text(encoding="utf-8")
        )
        broken_payload = json.loads(
            (Path(result.output_dir) / "channels" / "broken.json").read_text(encoding="utf-8")
        )

        assert resolved_payload["channel"]["resolved_channel_id"] == "UC_RESOLVED"
        assert broken_payload["error"]["code"] == "ValueError"
        assert result.summary["channels_ok"] == 1
        assert result.summary["channels_failed"] == 1

    def test_execute_task_rejects_unknown_mode_at_runtime(self, tmp_path):
        task = _make_task(name="weird_mode", mode="unexpected", channels=(_make_channel(),), video_ids=())
        now_utc = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

        with patch("automation.youtube_automation._build_service"):
            result = execute_task(task, output_root=tmp_path, now_utc=now_utc)

        payload = json.loads((Path(result.output_dir) / "channels" / "test-channel.json").read_text(encoding="utf-8"))
        assert payload["error"]["code"] == "RuntimeError"


class TestAutomationMain:
    def test_list_command_success(self, tmp_path, capsys):
        config_path = tmp_path / "automation-config.json"
        config_path.write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "name": "demo",
                            "mode": "latest_full",
                            "enabled": True,
                            "schedule": {"kind": "manual", "timezone": "UTC"},
                            "fetch": {},
                            "channels": [],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        with patch(
            "sys.argv",
            ["youtube-automation", "list", "--config", str(config_path), "--run-mode", "all"],
        ):
            main()

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["tasks"] == ["demo"]

    def test_run_and_plan_commands_success(self, tmp_path, capsys):
        task = _make_task(name="demo", channels=())
        task_result = automation_mod.TaskRunResult(
            task="demo",
            mode="latest_full",
            date="2026-03-11",
            branch="data_demo/2026-03-11",
            output_dir=str(tmp_path / "data"),
            summary={"channels_ok": 0},
        )
        tasks = {"demo": task}

        with (
            patch("automation.youtube_automation.load_tasks", return_value=tasks),
            patch("automation.youtube_automation.execute_task", return_value=task_result),
            patch(
                "sys.argv",
                ["youtube-automation", "run", "--config", "ignored", "--task-name", "demo", "--output-root", str(tmp_path)],
            ),
        ):
            main()

        run_payload = json.loads(capsys.readouterr().out)
        assert run_payload["ok"] is True
        assert run_payload["result"]["task"] == "demo"

        with (
            patch("automation.youtube_automation.load_tasks", return_value=tasks),
            patch(
                "sys.argv",
                ["youtube-automation", "plan", "--config", "ignored", "--task-name", "demo", "--output-root", str(tmp_path)],
            ),
        ):
            main()

        plan_payload = json.loads(capsys.readouterr().out)
        assert plan_payload["ok"] is True
        assert plan_payload["result"]["task"] == "demo"

    def test_main_reports_config_and_unexpected_errors(self, capsys):
        with (
            patch("automation.youtube_automation.load_tasks", side_effect=AutomationConfigError("bad config")),
            patch("sys.argv", ["youtube-automation", "list", "--config", "ignored", "--run-mode", "all"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["error"]["type"] == "AutomationConfigError"

        with (
            patch("automation.youtube_automation.load_tasks", side_effect=RuntimeError("boom")),
            patch("sys.argv", ["youtube-automation", "list", "--config", "ignored", "--run-mode", "all"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["error"]["type"] == "RuntimeError"
