#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP="$ROOT_DIR/app.py"
PYTHON="$ROOT_DIR/.venv/bin/python"
PORT="${COMPRASLAB_PORT:-8501}"
RUN_DIR="$ROOT_DIR/storage/run"
PID_FILE="$RUN_DIR/streamlit-$PORT.pid"
LOG_FILE="$RUN_DIR/streamlit-$PORT.log"

if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( 10#$PORT < 1 || 10#$PORT > 65535 )); then
    echo "COMPRASLAB_PORT debe ser un puerto entre 1 y 65535." >&2
    exit 2
fi

is_project_process() {
    local pid="$1" command cwd
    [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/cmdline" ]] || return 1
    cwd="$(readlink -f -- "/proc/$pid/cwd" 2>/dev/null)" || return 1
    [[ "$cwd" == "$ROOT_DIR" ]] || return 1
    command="$(tr '\0' ' ' < "/proc/$pid/cmdline")"
    [[ "$command" == *"streamlit run $APP"* || "$command" == *"streamlit run app.py"* ]]
}

listening_pid() {
    command -v lsof >/dev/null 2>&1 || return 0
    lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

project_pid() {
    local pid
    if [[ -f "$PID_FILE" ]]; then
        pid="$(< "$PID_FILE")"
        if is_project_process "$pid"; then
            printf '%s\n' "$pid"
            return
        fi
        rm -f -- "$PID_FILE"
    fi
    pid="$(listening_pid)"
    if [[ -n "$pid" ]] && is_project_process "$pid"; then
        printf '%s\n' "$pid"
    fi
}

start() {
    local pid current
    current="$(project_pid)"
    if [[ -n "$current" ]]; then
        echo "ComprasLab ya está activo en http://localhost:$PORT (PID $current)."
        return
    fi
    if [[ -n "$(listening_pid)" ]]; then
        echo "El puerto $PORT está ocupado por otro proceso." >&2
        exit 1
    fi
    if [[ ! -x "$PYTHON" ]]; then
        echo "Falta .venv. Ejecute: uv sync --python 3.13 --all-extras --locked" >&2
        exit 1
    fi
    mkdir -p -- "$RUN_DIR"
    cd -- "$ROOT_DIR"
    nohup "$PYTHON" -m streamlit run "$APP" \
        --server.headless=true --server.address=127.0.0.1 --server.port="$PORT" \
        >"$LOG_FILE" 2>&1 </dev/null &
    pid=$!
    printf '%s\n' "$pid" > "$PID_FILE"
    for ((i=0; i<40; i++)); do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f -- "$PID_FILE"
            echo "ComprasLab no pudo iniciar. Revise $LOG_FILE" >&2
            exit 1
        fi
        if "$PYTHON" -c 'import sys, urllib.request; sys.exit(0 if urllib.request.urlopen(sys.argv[1], timeout=1).read().strip() == b"ok" else 1)' \
            "http://127.0.0.1:$PORT/_stcore/health" >/dev/null 2>&1; then
            echo "ComprasLab activo en http://localhost:$PORT (PID $pid)."
            echo "Registro: $LOG_FILE"
            return
        fi
        sleep 0.25
    done
    echo "ComprasLab no respondió a tiempo. Revise $LOG_FILE" >&2
    exit 1
}

stop() {
    local pid
    pid="$(project_pid)"
    if [[ -z "$pid" ]]; then
        echo "ComprasLab no está activo en el puerto $PORT."
        return
    fi
    kill "$pid"
    for ((i=0; i<40; i++)); do
        if ! is_project_process "$pid"; then
            rm -f -- "$PID_FILE"
            echo "ComprasLab detenido (PID $pid)."
            return
        fi
        sleep 0.25
    done
    echo "ComprasLab no se detuvo a tiempo (PID $pid)." >&2
    exit 1
}

case "${1:-}" in
    start) start ;;
    stop) stop ;;
    restart) stop; start ;;
    status)
        pid="$(project_pid)"
        if [[ -n "$pid" ]]; then
            echo "ComprasLab activo en http://localhost:$PORT (PID $pid)."
        else
            echo "ComprasLab no está activo en el puerto $PORT."
        fi
        ;;
    *)
        echo "Uso: $0 {start|stop|restart|status}" >&2
        exit 2
        ;;
esac
