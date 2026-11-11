#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$PROJECT_DIR/storage/run"
PID_FILE="$RUN_DIR/streamlit.pid"
PORT_FILE="$RUN_DIR/streamlit.port"
LOG_FILE="$RUN_DIR/streamlit.log"
STREAMLIT="$PROJECT_DIR/.venv/bin/streamlit"
PORT="${PEDRO_PORT:-8501}"

cd "$PROJECT_DIR"

managed_process() {
    local pid="$1" command_line process_dir
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    [[ "$(ps -p "$pid" -o stat= 2>/dev/null)" != Z* ]] || return 1
    process_dir="$(readlink -f "/proc/$pid/cwd" 2>/dev/null)" || return 1
    [[ "$process_dir" == "$PROJECT_DIR" ]] || return 1
    command_line="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)" || return 1
    [[ "$command_line" == *streamlit* && "$command_line" == *app.py* ]]
}

running_pid() {
    local pid
    [[ -f "$PID_FILE" ]] || return 1
    pid="$(<"$PID_FILE")"
    managed_process "$pid" || return 1
    printf '%s\n' "$pid"
}

running_port() {
    local pid="$1" argument
    if [[ -f "$PORT_FILE" ]]; then
        printf '%s\n' "$(<"$PORT_FILE")"
        return
    fi
    while IFS= read -r -d '' argument; do
        case "$argument" in
            --server.port=*) printf '%s\n' "${argument#--server.port=}"; return ;;
        esac
    done < "/proc/$pid/cmdline"
    printf '8501\n'
}

clear_state() {
    [[ ! -f "$PID_FILE" ]] || rm -- "$PID_FILE"
    [[ ! -f "$PORT_FILE" ]] || rm -- "$PORT_FILE"
}

validate_port() {
    if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( 10#$PORT < 1 || 10#$PORT > 65535 )); then
        printf 'PEDRO_PORT deve estar entre 1 e 65535.\n' >&2
        return 1
    fi
}

start() {
    local pid attempt
    validate_port
    if pid="$(running_pid)"; then
        printf 'Pedro já está ativo em http://localhost:%s (PID %s).\n' "$(running_port "$pid")" "$pid"
        return 0
    fi
    clear_state
    [[ -x "$STREAMLIT" ]] || {
        printf 'Falta .venv/bin/streamlit. Execute: uv sync --python 3.13 --all-extras --locked\n' >&2
        return 1
    }
    mkdir -p "$RUN_DIR"
    pid="$("$PROJECT_DIR/.venv/bin/python" - "$PROJECT_DIR" "$STREAMLIT" "$LOG_FILE" "$PORT" <<'PY'
import subprocess
import sys

project_dir, streamlit, log_path, port = sys.argv[1:]
with open(log_path, "ab") as log:
    process = subprocess.Popen(
        [streamlit, "run", "app.py", "--server.headless=true",
         "--server.address=127.0.0.1", f"--server.port={port}"],
        cwd=project_dir, stdin=subprocess.DEVNULL, stdout=log,
        stderr=subprocess.STDOUT, start_new_session=True,
    )
print(process.pid)
PY
)"
    printf '%s\n' "$pid" > "$PID_FILE"
    printf '%s\n' "$PORT" > "$PORT_FILE"
    for ((attempt = 0; attempt < 30; attempt++)); do
        if ! managed_process "$pid"; then
            clear_state
            printf 'Pedro não iniciou. Verifique %s\n' "$LOG_FILE" >&2
            return 1
        fi
        if curl -fsS --max-time 1 "http://127.0.0.1:$PORT/_stcore/health" > /dev/null 2>&1; then
            printf 'Pedro ativo em http://localhost:%s (PID %s).\n' "$PORT" "$pid"
            return 0
        fi
        sleep 0.5
    done
    printf 'Pedro não respondeu a tempo. Verifique %s\n' "$LOG_FILE" >&2
    stop > /dev/null
    return 1
}

stop() {
    local pid attempt
    if ! pid="$(running_pid)"; then
        clear_state
        printf 'Pedro não está ativo.\n'
        return 0
    fi
    kill "$pid"
    for ((attempt = 0; attempt < 20; attempt++)); do
        if ! managed_process "$pid"; then
            clear_state
            printf 'Pedro parado (PID %s).\n' "$pid"
            return 0
        fi
        sleep 0.25
    done
    if managed_process "$pid"; then
        kill -KILL "$pid"
    fi
    clear_state
    printf 'Pedro parado (PID %s).\n' "$pid"
}

status() {
    local pid
    if pid="$(running_pid)"; then
        printf 'Pedro ativo em http://localhost:%s (PID %s).\n' "$(running_port "$pid")" "$pid"
    else
        printf 'Pedro não está ativo.\n'
    fi
}

case "${1:-start}" in
    start) start ;;
    restart) validate_port; stop; start ;;
    stop) stop ;;
    status) status ;;
    *) printf 'Uso: %s {start|restart|stop|status}\n' "$0" >&2; exit 2 ;;
esac
