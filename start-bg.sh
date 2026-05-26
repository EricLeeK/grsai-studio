#!/bin/bash
# Grsai Studio 后台启动脚本
# Usage: bash start-bg.sh [port]

set -euo pipefail

PORT=${1:-8099}
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.server.pid"
LOG_FILE="$DIR/logs/server.log"

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

# Create logs directory
mkdir -p logs

# Start server in background
nohup uvicorn app.main:app --host 127.0.0.1 --port "$PORT" > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

echo "🚀 Grsai Studio 已在后台启动"
echo "   地址: http://127.0.0.1:$PORT"
echo "   PID:  $(cat "$PID_FILE")"
echo "   日志: $LOG_FILE"
echo ""
echo "停止: bash stop.sh"
