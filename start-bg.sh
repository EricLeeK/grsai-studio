#!/bin/bash
# Grsai Studio 后台启动脚本（FastAPI + poster-studio 都在后台）
# Usage: bash start-bg.sh [port]

set -euo pipefail

PORT=${1:-8099}
PS_PORT=${PS_PORT:-8100}
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.server.pid"
PS_PID_FILE="$DIR/poster-studio.pid"
LOG_FILE="$DIR/logs/server.log"
PS_LOG_FILE="$DIR/logs/poster-studio.log"

cd "$DIR"

# 停掉已占用端口的进程
for p in $PORT $PS_PORT; do
    lsof -ti :$p | xargs kill 2>/dev/null || true
done

# ---- Python venv + 依赖 ----
if [[ ! -d ".venv" ]]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv .venv
fi
source .venv/bin/activate
echo "📦 同步 Python 依赖..."
pip install -q -r requirements.txt

mkdir -p logs

# ---- poster-studio (Next.js 画布) ----
if command -v node >/dev/null 2>&1; then
    if [[ ! -d "poster-studio/.next" ]]; then
        echo "⚙️  poster-studio 首次使用，执行安装与构建（几分钟）..."
        bash scripts/setup-poster-studio.sh
    fi
    echo "🖼️  启动 poster-studio 画布 (端口 :$PS_PORT)..."
    nohup bash -c "cd poster-studio && ./node_modules/.bin/next start -p $PS_PORT" > "$PS_LOG_FILE" 2>&1 &
    echo $! > "$PS_PID_FILE"
else
    echo "⚠️  未检测到 Node.js，跳过 poster-studio 画布。"
    rm -f "$PS_PID_FILE"
fi

# ---- FastAPI ----
nohup uvicorn app.main:app --host 127.0.0.1 --port "$PORT" > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

echo "🚀 Grsai Studio 已在后台启动"
echo "   工作台: http://127.0.0.1:$PORT/"
echo "   画布:   http://127.0.0.1:$PS_PORT/  (或 http://127.0.0.1:$PORT/studio)"
echo "   FastAPI PID: $(cat "$PID_FILE")  日志: $LOG_FILE"
[[ -f "$PS_PID_FILE" ]] && echo "   画布  PID: $(cat "$PS_PID_FILE")  日志: $PS_LOG_FILE"
echo ""
echo "停止: bash stop.sh"
