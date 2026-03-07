#!/bin/bash
#
# Deploy holo-youtube-scraper as an OpenClaw skill bundle.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_TARGET_PATH="${HOME}/.openclaw/skills/holo-youtube-scraper"
TARGET_PATH="${1:-$DEFAULT_TARGET_PATH}"

if [[ "$TARGET_PATH" != /* ]]; then
    echo "Error: target path must be absolute." >&2
    echo "Usage: $0 [ABS_TARGET_PATH]" >&2
    exit 1
fi

mkdir -p "$TARGET_PATH"

DEPLOY_ITEMS=(
    "SKILL.md"
    "scripts"
    "references"
    "src"
    "pyproject.toml"
    "uv.lock"
    ".env.example"
)

for item in "${DEPLOY_ITEMS[@]}"; do
    if [ -e "$SCRIPT_DIR/$item" ]; then
        rm -rf "$TARGET_PATH/$item"
        cp -R "$SCRIPT_DIR/$item" "$TARGET_PATH/"
    else
        echo "Warning: missing item, skipped: $item" >&2
    fi
done

cat <<EOF
Deployment complete.
Target: $TARGET_PATH
Included:
  - SKILL.md
  - scripts/
  - references/
  - src/
  - pyproject.toml
  - uv.lock
  - .env.example

Next:
  bash $TARGET_PATH/scripts/youtube.sh help
EOF
