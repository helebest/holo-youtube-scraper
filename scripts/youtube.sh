#!/bin/bash
#
# OpenClaw entrypoint for holo-youtube-scraper
#

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

json_escape() {
    local value="$1"
    value=${value//\\/\\\\}
    value=${value//\"/\\\"}
    value=${value//$'\n'/\\n}
    value=${value//$'\r'/\\r}
    value=${value//$'\t'/\\t}
    printf '%s' "$value"
}

emit_error_json() {
    local code="$1"
    local message="$2"
    local command_value="${3:-}"

    local escaped_message
    escaped_message="$(json_escape "$message")"
    local escaped_command
    escaped_command="$(json_escape "$command_value")"

    cat <<EOF
{
  "ok": false,
  "command": "${escaped_command}",
  "input": {},
  "error": {
    "type": "ShellError",
    "code": "${code}",
    "message": "${escaped_message}"
  },
  "meta": {
    "generated_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  }
}
EOF
}

print_help() {
    cat <<'EOF'
Holo YouTube Scraper

Usage:
  bash {baseDir}/scripts/youtube.sh <command> [args...]

Commands:
  popular <CHANNEL_ID> [--top <N>] [--scan <N>] [--timeout <SECONDS>] [--retries <N>] [--output [<DIR>]]
  transcript <VIDEO_ID_OR_URL> [--lang <LANG_CODES>] [--output [<DIR>]]
  full <CHANNEL_ID> [--top <N>] [--scan <N>] [--lang <LANG_CODES>] [--timeout <SECONDS>] [--retries <N>] [--output [<DIR>]]

Output Contract:
  Every command writes a single JSON envelope to stdout.
  Success: {ok:true, command, input, result, meta}
  Error:   {ok:false, command, input, error{type,code,message}, meta}

Examples:
  bash {baseDir}/scripts/youtube.sh popular <CHANNEL_ID> --top 5
  bash {baseDir}/scripts/youtube.sh transcript <VIDEO_ID_OR_URL> --lang <LANG_CODES>
  bash {baseDir}/scripts/youtube.sh full <CHANNEL_ID> --top 3 --lang <LANG_CODES>
EOF
}

resolve_python() {
    local global_venv="${HOME}/.openclaw/.venv"
    local candidates=()

    if [ -n "${YOUTUBE_PYTHON:-}" ]; then
        candidates+=("${YOUTUBE_PYTHON}")
    fi

    candidates+=(
        "${global_venv}/bin/python"
        "${global_venv}/Scripts/python.exe"
        "${global_venv}/Scripts/python"
    )

    local candidate
    for candidate in "${candidates[@]}"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

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

run_python_cli() {
    local python_bin
    if ! python_bin="$(resolve_python)"; then
        emit_error_json "PYTHON_RUNTIME_MISSING" "No Python runtime found. Set YOUTUBE_PYTHON or install the OpenClaw global venv/python3/python." "$1"
        return 1
    fi

    (
        cd "$BASE_DIR"
        "$python_bin" "$BASE_DIR/scripts/main.py" "$@"
    )
    return $?
}

main() {
    local cmd="${1:-}"

    if [ -z "$cmd" ] || [ "$cmd" = "help" ] || [ "$cmd" = "-h" ] || [ "$cmd" = "--help" ]; then
        print_help
        return 0
    fi

    case "$cmd" in
        popular|transcript|full)
            run_python_cli "$@"
            return $?
            ;;
        *)
            emit_error_json "INVALID_COMMAND" "Unsupported command: $cmd" "$cmd"
            return 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
