#!/bin/bash
# Grsai Studio 停止脚本（停止 FastAPI + poster-studio）

set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=${1:-8099}
PS_PORT=${PS_PORT:-8100}

stop_pidfile() {
    local file="$1"
    local label="$2"
    if [[ -f "$file" ]]; then
        local pid
        pid=$(cat "$file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "🛑 停止 $label (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            rm -f "$file"
        else
            echo "⚠️  $label 未运行 (PID $pid 不存在)"
            rm -f "$file"
        fi
    fi
}

stop_pidfile "$DIR/.server.pid" "FastAPI"
stop_pidfile "$DIR/poster-studio.pid" "poster-studio"

# 兜底：按端口清理
for p in $PORT $PS_PORT; do
    lsof -ti :$p | xargs kill 2>/dev/null && echo "✅ 已清理 :$p 端口" || true
done

echo "✅ 已停止"
