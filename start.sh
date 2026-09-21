#!/bin/bash
# Grsai Studio 一键启动脚本（前台跑 FastAPI，后台跑 poster-studio 画布）
# Usage: bash start.sh [port]

set -euo pipefail

PORT=${1:-8099}
PS_PORT=${PS_PORT:-8100}
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 停掉已占用端口的进程
lsof -ti :$PORT | xargs kill 2>/dev/null || true
lsof -ti :$PS_PORT | xargs kill 2>/dev/null || true

# ---- Python venv + 依赖 ----
if [[ ! -d ".venv" ]]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv .venv
fi
source .venv/bin/activate
echo "📦 同步 Python 依赖..."
pip install -q -r requirements.txt

# ---- poster-studio (Next.js 画布) ----
NEXT_PID=""
if command -v node >/dev/null 2>&1; then
    if [[ ! -d "poster-studio/.next" ]]; then
        echo "⚙️  poster-studio 首次使用，执行安装与构建（几分钟）..."
        bash scripts/setup-poster-studio.sh
    fi
    mkdir -p logs
    echo "🖼️  启动 poster-studio 画布 (端口 :$PS_PORT)..."
    ( cd poster-studio && ./node_modules/.bin/next start -p "$PS_PORT" ) > logs/poster-studio.log 2>&1 &
    NEXT_PID=$!
    for _ in $(seq 1 40); do
        if curl -sf -o /dev/null "http://127.0.0.1:$PS_PORT/" 2>/dev/null; then break; fi
        sleep 1
    done
else
    echo "⚠️  未检测到 Node.js，跳过 poster-studio 画布（仅启动图片工作台）。"
fi

cleanup() {
    if [[ -n "$NEXT_PID" ]]; then
        echo ""
        echo "🛑 停止 poster-studio (PID: $NEXT_PID)..."
        kill "$NEXT_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# ---- FastAPI（前台，实时日志）----
echo "🚀 启动 Grsai Studio..."
echo "   工作台: http://127.0.0.1:$PORT/"
echo "   画布:   http://127.0.0.1:$PS_PORT/  (或 http://127.0.0.1:$PORT/studio)"
if [[ -n "$NEXT_PID" ]]; then
    echo "   画布日志: logs/poster-studio.log"
fi
echo "   按 Ctrl+C 停止全部"

uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
