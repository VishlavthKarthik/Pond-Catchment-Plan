#!/usr/bin/env bash
cd /home/student/pond_catchment

# Stop existing server on port 3317
PID_ON_PORT=$(ss -tulpn | grep :3317 | grep -oP 'pid=\K[0-9]+' | head -n 1)
if [ -n "$PID_ON_PORT" ]; then
    echo "Stopping existing process on port 3317 (PID: $PID_ON_PORT)..."
    kill -9 "$PID_ON_PORT" 2>/dev/null || true
    sleep 1
fi

echo "Starting Pond Catchment API on port 3317..."
nohup /home/student/pond_catchment/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 3317 > /home/student/pond_catchment/server.log 2>&1 &
echo $! > /home/student/pond_catchment/server.pid
sleep 2
echo "Server started (PID: $(cat /home/student/pond_catchment/server.pid))"
