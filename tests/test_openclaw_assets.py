"""Tests for OpenClaw skill assets and shell entrypoints."""

import json
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_FILES = [
    REPO_ROOT / "SKILL.md",
    REPO_ROOT / "openclaw_deploy_skill.sh",
    REPO_ROOT / "scripts" / "youtube.sh",
    REPO_ROOT / "references" / "commands.md",
    REPO_ROOT / "references" / "output-schema.md",
    REPO_ROOT / "references" / "troubleshooting.md",
]


def _bash_path() -> Path | None:
    candidates = [
        Path("C:/Program Files/Git/bin/bash.exe"),
        Path("/usr/bin/bash"),
        Path("/bin/bash"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _bash_arg(path: Path) -> str:
    return path.resolve().as_posix()


def test_required_openclaw_assets_exist() -> None:
    missing = [str(path) for path in SKILL_FILES if not path.exists()]
    assert not missing, f"Missing OpenClaw files: {missing}"


def test_docs_use_placeholders_without_real_ids() -> None:
    docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "SKILL.md",
        REPO_ROOT / "references" / "commands.md",
        REPO_ROOT / "src" / "youtube_scraper" / "__init__.py",
    ]

    forbidden_snippets = [
        "UCbfYPyITQ-7l4upoX8nvctg",
        "dQw4w9WgXcQ",
    ]

    for path in docs:
        text = path.read_text(encoding="utf-8")
        for snippet in forbidden_snippets:
            assert snippet not in text, f"Found concrete ID in {path}: {snippet}"

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "<CHANNEL_ID>" in readme
    assert "<VIDEO_ID>" in readme


def test_deploy_script_declares_self_contained_items() -> None:
    deploy_script = (REPO_ROOT / "openclaw_deploy_skill.sh").read_text(encoding="utf-8")
    assert "DEFAULT_TARGET_PATH=\"${HOME}/.openclaw/skills/holo-youtube-scraper\"" in deploy_script
    assert '"SKILL.md"' in deploy_script
    assert '"scripts"' in deploy_script
    assert '"references"' in deploy_script
    assert '"src"' in deploy_script
    assert '"pyproject.toml"' in deploy_script
    assert '"uv.lock"' in deploy_script
    assert '".env.example"' in deploy_script


@pytest.mark.skipif(_bash_path() is None, reason="bash is not available")
def test_deploy_script_rejects_relative_path() -> None:
    bash = _bash_path()
    assert bash is not None

    proc = subprocess.run(
        [str(bash), _bash_arg(REPO_ROOT / "openclaw_deploy_skill.sh"), "relative/path"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 1
    assert "absolute" in (proc.stdout + proc.stderr).lower()


@pytest.mark.skipif(_bash_path() is None, reason="bash is not available")
def test_deploy_script_default_target_with_home_override(tmp_path: Path) -> None:
    bash = _bash_path()
    assert bash is not None

    env = os.environ.copy()
    env["HOME"] = tmp_path.as_posix()

    proc = subprocess.run(
        [str(bash), _bash_arg(REPO_ROOT / "openclaw_deploy_skill.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr

    deployed = tmp_path / ".openclaw" / "skills" / "holo-youtube-scraper"
    assert (deployed / "SKILL.md").exists()
    assert (deployed / "scripts" / "youtube.sh").exists()
    assert (deployed / "references" / "commands.md").exists()
    assert (deployed / "src" / "youtube_scraper" / "cli.py").exists()


@pytest.mark.skipif(_bash_path() is None, reason="bash is not available")
def test_shell_help_and_invalid_command_output() -> None:
    bash = _bash_path()
    assert bash is not None

    help_proc = subprocess.run(
        [str(bash), _bash_arg(REPO_ROOT / "scripts" / "youtube.sh"), "help"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    assert help_proc.returncode == 0
    assert "<CHANNEL_ID>" in help_proc.stdout
    assert "<VIDEO_ID>" in help_proc.stdout

    bad_proc = subprocess.run(
        [str(bash), _bash_arg(REPO_ROOT / "scripts" / "youtube.sh"), "bad-command"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    assert bad_proc.returncode == 1

    payload = json.loads(bad_proc.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_COMMAND"
