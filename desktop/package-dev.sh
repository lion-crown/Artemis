#!/bin/bash
# Desktop shell against a source Artemis (hot reload). Not ~/.artemis/portable.
# Starts Artemis in this shell and stops it when wails3 / this script exits.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${ARTEMIS_PORT:-8088}"
URL="${ARTEMIS_DESKTOP_URL:-http://127.0.0.1:${PORT}}"
HEALTH="${URL%/}/api/health"
WAILS3_PKG="github.com/wailsapp/wails/v3/cmd/wails3@latest"

missing=0
if ! command -v go >/dev/null 2>&1; then
  missing=1
  echo "go is not installed (need Go 1.25+)." >&2
  echo "  macOS:  brew install go" >&2
  echo "  Linux:  https://go.dev/dl/" >&2
  echo "  then:   export PATH=\"\$(go env GOPATH)/bin:\$PATH\"" >&2
fi
if ! command -v wails3 >/dev/null 2>&1; then
  missing=1
  echo "wails3 is not installed." >&2
  echo "  go install ${WAILS3_PKG}" >&2
  echo "  export PATH=\"\$(go env GOPATH)/bin:\$PATH\"" >&2
fi
if [[ "$missing" -eq 1 ]]; then
  exit 1
fi

artemis_pid=""
cleaned=0

cleanup() {
  [[ "$cleaned" -eq 1 ]] && return
  cleaned=1
  trap - EXIT INT TERM
  if [[ -n "$artemis_pid" ]] && kill -0 "$artemis_pid" 2>/dev/null; then
    kill -TERM "$artemis_pid" 2>/dev/null || true
    wait "$artemis_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if curl -sf -o /dev/null --max-time 1 "$HEALTH"; then
  echo "Artemis already listening at ${URL}; stop it first so this script can own the process." >&2
  exit 1
fi

echo "starting Artemis with artemis --reload on port ${PORT}"
(
  cd "$REPO"
  exec env ARTEMIS_DESKTOP=1 uv run artemis run --reload --host 127.0.0.1 --port "$PORT"
) &
artemis_pid=$!

for _ in $(seq 1 60); do
  if curl -sf -o /dev/null --max-time 1 "$HEALTH"; then
    break
  fi
  if ! kill -0 "$artemis_pid" 2>/dev/null; then
    echo "Artemis 进程在就绪前退出了，请查看上方日志。" >&2
    exit 1
  fi
  sleep 0.5
done

if ! curl -sf -o /dev/null --max-time 1 "$HEALTH"; then
  echo "Artemis 未在 30 秒内就绪（${URL}）。" >&2
  echo "请查看上方 Artemis（artemis run）的输出；常见原因：端口被占用、依赖缺失，或服务启动失败。" >&2
  exit 1
fi

cd "$REPO/desktop/src"
ARTEMIS_DESKTOP_URL="$URL" wails3 dev
