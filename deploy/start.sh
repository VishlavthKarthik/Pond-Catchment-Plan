#!/usr/bin/env bash
cd /home/student/pond_catchment

PORT=3000

# Stop existing server on port
PID_ON_PORT=$(ss -tulpn | grep ":${PORT}" | grep -oP 'pid=\K[0-9]+' | head -n 1)
if [ -n "$PID_ON_PORT" ]; then
    echo "Stopping existing process on port ${PORT} (PID: $PID_ON_PORT)..."
    kill -9 "$PID_ON_PORT" 2>/dev/null || true
    sleep 1
fi

echo "Starting Pond Catchment API on port ${PORT}..."
nohup /home/student/pond_catchment/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT} > /home/student/pond_catchment/deploy/server.log 2>&1 &
echo $! > /home/student/pond_catchment/deploy/server.pid
sleep 2
echo "Server started (PID: $(cat /home/student/pond_catchment/deploy/server.pid)) on port ${PORT}"
