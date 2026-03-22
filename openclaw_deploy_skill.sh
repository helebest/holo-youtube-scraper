#!/bin/bash
#
# Deploy holo-youtube-scraper as an OpenClaw skill bundle.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_TARGET_PATH="${HOME}/.openclaw/skills/holo-youtube-scraper"
GLOBAL_VENV="${HOME}/.openclaw/.venv"
TARGET_PATH="${1:-$DEFAULT_TARGET_PATH}"

if [[ "$TARGET_PATH" != /* ]]; then
    echo "Error: target path must be absolute." >&2
    echo "Usage: $0 [ABS_TARGET_PATH]" >&2
    exit 1
fi

resolve_bootstrap_python() {
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi
    return 1
}

resolve_global_python() {
    local candidates=(
        "${GLOBAL_VENV}/bin/python"
        "${GLOBAL_VENV}/Scripts/python.exe"
        "${GLOBAL_VENV}/Scripts/python"
    )

    local candidate
    for candidate in "${candidates[@]}"; do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is required for deployment." >&2
    exit 1
fi

BOOTSTRAP_PYTHON="$(resolve_bootstrap_python || true)"
if [ -z "$BOOTSTRAP_PYTHON" ]; then
    echo "Error: python3 or python is required for deployment." >&2
    exit 1
fi

if ! GLOBAL_PYTHON="$(resolve_global_python)"; then
    echo "Creating OpenClaw global virtual environment at $GLOBAL_VENV"
    uv venv "$GLOBAL_VENV"
    GLOBAL_PYTHON="$(resolve_global_python)"
fi

mapfile -t DEPS < <(
    "$BOOTSTRAP_PYTHON" -c "
import tomllib
from pathlib import Path

with Path(r'$SCRIPT_DIR/pyproject.toml').open('rb') as handle:
    data = tomllib.load(handle)
for item in data.get('project', {}).get('dependencies', []):
    print(item)
"
)

if [ "${#DEPS[@]}" -gt 0 ]; then
    echo "Installing runtime dependencies into $GLOBAL_VENV"
    uv pip install --python "$GLOBAL_PYTHON" "${DEPS[@]}"
fi

mkdir -p "$TARGET_PATH"

DEPLOY_ITEMS=(
    "SKILL.md"
    "README.md"
    "scripts"
    "references"
)

for item in "${DEPLOY_ITEMS[@]}"; do
    if [ -e "$SCRIPT_DIR/$item" ]; then
        rm -rf "$TARGET_PATH/$item"
        cp -R "$SCRIPT_DIR/$item" "$TARGET_PATH/"
    else
        echo "Warning: missing item, skipped: $item" >&2
    fi
done

find "$TARGET_PATH" -type d -name "__pycache__" -prune -exec rm -rf {} +

cat <<EOF
Deployment complete.
Target: $TARGET_PATH
Included:
  - SKILL.md
  - README.md
  - scripts/
  - references/

Runtime:
  - dependencies installed into $GLOBAL_VENV

Next:
  bash $TARGET_PATH/scripts/youtube.sh help
EOF
