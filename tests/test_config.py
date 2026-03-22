"""Tests for scripts.config."""

import os

import pytest

import scripts.config as cfg
from scripts.config import _load_dotenv, get_api_key


class TestGetApiKey:
    def test_returns_key_from_env(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "my-secret-key")
        assert get_api_key() == "my-secret-key"

    def test_raises_when_key_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cfg, "SKILL_ROOT", tmp_path)
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY not set"):
            get_api_key()

    def test_raises_when_key_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cfg, "SKILL_ROOT", tmp_path)
        monkeypatch.setenv("YOUTUBE_API_KEY", "")
        with pytest.raises(RuntimeError, match="not set"):
            get_api_key()

    def test_reads_dotenv_from_skill_root_not_cwd(self, tmp_path, monkeypatch):
        skill_root = tmp_path / "skill"
        other_dir = tmp_path / "other"
        skill_root.mkdir()
        other_dir.mkdir()
        (skill_root / ".env").write_text("YOUTUBE_API_KEY=from-skill-root\n")
        (other_dir / ".env").write_text("YOUTUBE_API_KEY=from-cwd\n")

        monkeypatch.setattr(cfg, "SKILL_ROOT", skill_root)
        monkeypatch.chdir(other_dir)
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

        assert get_api_key() == "from-skill-root"


class TestLoadDotenv:
    def test_loads_only_youtube_api_key(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("YOUTUBE_API_KEY=from-file\nOTHER_KEY=should_not_be_loaded\n")
        monkeypatch.setattr(cfg, "SKILL_ROOT", tmp_path)
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        monkeypatch.delenv("OTHER_KEY", raising=False)

        _load_dotenv()
        assert os.environ.get("YOUTUBE_API_KEY") == "from-file"
        assert os.environ.get("OTHER_KEY") is None

    def test_does_not_override_existing_env(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("YOUTUBE_API_KEY=from-file\n")
        monkeypatch.setattr(cfg, "SKILL_ROOT", tmp_path)
        monkeypatch.setenv("YOUTUBE_API_KEY", "from-env")

        _load_dotenv()
        assert os.environ["YOUTUBE_API_KEY"] == "from-env"

    def test_strips_quotes(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        monkeypatch.setattr(cfg, "SKILL_ROOT", tmp_path)
        # Only YOUTUBE_API_KEY should be loaded from .env
        env_file.write_text('YOUTUBE_API_KEY="double_quoted"\nUNUSED=\'single_quoted\'\n')
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        monkeypatch.delenv("UNUSED", raising=False)

        _load_dotenv()
        assert os.environ.get("YOUTUBE_API_KEY") == "double_quoted"
        assert os.environ.get("UNUSED") is None
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        monkeypatch.delenv("UNUSED", raising=False)

    def test_no_env_file_is_fine(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cfg, "SKILL_ROOT", tmp_path)
        _load_dotenv()  # Should not raise

    def test_idempotent(self, tmp_path, monkeypatch):
        """Calling _load_dotenv twice should not re-read the file."""
        env_file = tmp_path / ".env"
        env_file.write_text("YOUTUBE_API_KEY=first\n")
        monkeypatch.setattr(cfg, "SKILL_ROOT", tmp_path)
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

        _load_dotenv()
        assert os.environ.get("YOUTUBE_API_KEY") == "first"

        # Modify file and call again — should NOT pick up changes
        env_file.write_text("YOUTUBE_API_KEY=second\n")
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        _load_dotenv()
        # Variable was deleted from env but _load_dotenv is idempotent, so not re-read
        assert os.environ.get("YOUTUBE_API_KEY") is None

        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

    def test_get_api_key_triggers_dotenv(self, tmp_path, monkeypatch):
        """get_api_key() should lazily load .env."""
        env_file = tmp_path / ".env"
        env_file.write_text("YOUTUBE_API_KEY=from-dotenv\n")
        monkeypatch.setattr(cfg, "SKILL_ROOT", tmp_path)
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

        assert get_api_key() == "from-dotenv"
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
