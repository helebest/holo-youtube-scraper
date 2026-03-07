import os
from pathlib import Path

_dotenv_loaded = False
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOTENV_KEY = "YOUTUBE_API_KEY"


def _load_dotenv() -> None:
    """Load .env file from project root if it exists. Idempotent."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key != _DOTENV_KEY:
                continue
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def get_api_key() -> str:
    """Get YouTube API key from environment. Loads .env on first call."""
    _load_dotenv()
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if not key:
        raise RuntimeError(
            "YOUTUBE_API_KEY not set. "
            "Set it in your environment or in a .env file at the project root. "
            "See .env.example for reference."
        )
    return key


# Defaults
DEFAULT_MAX_RESULTS = 500
DEFAULT_TOP_N = 10
PLAYLIST_PAGE_SIZE = 50  # Max allowed by YouTube API
VIDEO_BATCH_SIZE = 50    # Max allowed by YouTube API
API_REQUEST_TIMEOUT_SECONDS = 30
API_REQUEST_RETRIES = 3
