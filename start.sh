#!/bin/bash
# Grsai Studio 一键启动脚本
# Usage: bash start.sh [port]

set -euo pipefail

PORT=${1:-8099}
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.server.pid"

cd "$DIR"

# Kill existing server if running
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "🔄 停止旧服务器 (PID: $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

# Also kill any uvicorn on the same port
lsof -ti :$PORT | xargs kill 2>/dev/null || true

# Check venv
if [[ ! -d ".venv" ]]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -q fastapi uvicorn sqlalchemy aiofiles python-multipart
else
    source .venv/bin/activate
fi

# Start server
echo "🚀 启动 Grsai Studio..."
echo "   地址: http://127.0.0.1:$PORT"
echo "   按 Ctrl+C 停止"

uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
