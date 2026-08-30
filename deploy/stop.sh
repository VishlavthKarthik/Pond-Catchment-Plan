#!/usr/bin/env bash
cd /home/student/pond_catchment

PORT=3000

if [ -f /home/student/pond_catchment/server.pid ]; then
    PID=$(cat /home/student/pond_catchment/server.pid)
    kill -9 "$PID" 2>/dev/null || true
    rm -f /home/student/pond_catchment/server.pid
fi

PID_ON_PORT=$(ss -tulpn | grep ":${PORT}" | grep -oP 'pid=\K[0-9]+' | head -n 1)
if [ -n "$PID_ON_PORT" ]; then
    kill -9 "$PID_ON_PORT" 2>/dev/null || true
fi

echo "Server stopped on port ${PORT}."
