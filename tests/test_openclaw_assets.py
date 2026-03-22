"""Tests for OpenClaw skill assets, deployment, and shell entrypoints."""

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_FILES = [
    REPO_ROOT / "SKILL.md",
    REPO_ROOT / "README.md",
    REPO_ROOT / "openclaw_deploy_skill.sh",
    REPO_ROOT / "scripts" / "youtube.sh",
    REPO_ROOT / "scripts" / "main.py",
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


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def test_required_openclaw_assets_exist() -> None:
    missing = [str(path) for path in SKILL_FILES if not path.exists()]
    assert not missing, f"Missing OpenClaw files: {missing}"


def test_docs_use_placeholders_without_real_ids() -> None:
    docs = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "SKILL.md",
        REPO_ROOT / "references" / "commands.md",
        REPO_ROOT / "references" / "output-schema.md",
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
    assert "<VIDEO_ID_OR_URL>" in readme


def test_deploy_script_declares_skill_bundle_items() -> None:
    deploy_script = (REPO_ROOT / "openclaw_deploy_skill.sh").read_text(encoding="utf-8")
    assert 'DEFAULT_TARGET_PATH="${HOME}/.openclaw/skills/holo-youtube-scraper"' in deploy_script
    assert '"SKILL.md"' in deploy_script
    assert '"README.md"' in deploy_script
    assert '"scripts"' in deploy_script
    assert '"references"' in deploy_script
    assert '"src"' not in deploy_script
    assert '".env.example"' not in deploy_script


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

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    uv_log = tmp_path / "uv.log"
    fake_uv = fake_bin / "uv"
    fake_python3 = fake_bin / "python3"
    _make_executable(
        fake_uv,
        """#!/bin/bash
set -euo pipefail
if [ -n "${FAKE_UV_LOG:-}" ]; then
  printf '%s\\n' "$*" >> "$FAKE_UV_LOG"
fi
case "${1:-}" in
  venv)
    target="${2:?}"
    mkdir -p "$target/bin"
    cat > "$target/bin/python" <<'EOF'
#!/bin/sh
exit 0
EOF
    chmod +x "$target/bin/python"
    ;;
  pip)
    if [ "${2:-}" != "install" ]; then
      echo "unexpected uv pip args: $*" >&2
      exit 1
    fi
    ;;
  *)
    echo "unexpected uv command: $*" >&2
    exit 1
    ;;
esac
""",
    )
    _make_executable(
        fake_python3,
        """#!/bin/bash
set -euo pipefail
if [ "${1:-}" = "-c" ]; then
  cat <<'EOF'
google-api-python-client>=2.192.0
PySocks>=1.7.1
PyYAML>=6.0.0
youtube-transcript-api>=1.2.4
EOF
  exit 0
fi
echo "unexpected python3 args: $*" >&2
exit 1
""",
    )

    env = os.environ.copy()
    env["HOME"] = tmp_path.as_posix()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["FAKE_UV_LOG"] = uv_log.as_posix()

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
    assert (deployed / "README.md").exists()
    assert (deployed / "scripts" / "youtube.sh").exists()
    assert (deployed / "scripts" / "main.py").exists()
    assert (deployed / "references" / "commands.md").exists()

    assert not (deployed / "src").exists()
    assert not (deployed / "docs").exists()
    assert not (deployed / "tests").exists()
    assert not (deployed / "automation").exists()
    assert not (deployed / "pyproject.toml").exists()
    assert not (deployed / "uv.lock").exists()
    assert not (deployed / ".env.example").exists()

    uv_log_text = uv_log.read_text(encoding="utf-8")
    assert "venv" in uv_log_text
    assert "pip install --python" in uv_log_text
    assert "google-api-python-client" in uv_log_text


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
    assert "<VIDEO_ID_OR_URL>" in help_proc.stdout

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


@pytest.mark.skipif(_bash_path() is None, reason="bash is not available")
def test_shell_prefers_youtube_python_env(tmp_path: Path) -> None:
    bash = _bash_path()
    assert bash is not None

    fake_python = tmp_path / "python"
    log_path = tmp_path / "python.log"
    _make_executable(
        fake_python,
        """#!/bin/bash
set -euo pipefail
printf '%s\\n' "$*" > "${FAKE_PYTHON_LOG:?}"
cat <<'EOF'
{"ok": true, "command": "popular", "input": {"channel_id": "UC_TEST"}, "result": [], "meta": {"generated_at": "2026-03-22T00:00:00Z"}}
EOF
""",
    )

    env = os.environ.copy()
    env["YOUTUBE_PYTHON"] = fake_python.as_posix()
    env["FAKE_PYTHON_LOG"] = log_path.as_posix()

    proc = subprocess.run(
        [str(bash), _bash_arg(REPO_ROOT / "scripts" / "youtube.sh"), "popular", "UC_TEST"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True

    invoked = log_path.read_text(encoding="utf-8")
    assert "scripts/main.py" in invoked
    assert "popular" in invoked
    assert "UC_TEST" in invoked
