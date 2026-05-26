#!/bin/bash
# Grsai Studio 停止脚本

DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.server.pid"

if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "🛑 停止服务器 (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "✅ 已停止"
    else
        echo "⚠️  服务器未运行 (PID $PID 不存在)"
        rm -f "$PID_FILE"
    fi
else
    echo "⚠️  未找到 .server.pid 文件"
    # Try to kill by port
    lsof -ti :8099 | xargs kill 2>/dev/null && echo "✅ 已停止 8099 端口进程" || echo "没有找到运行中的服务器"
fi
