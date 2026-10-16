#!/usr/bin/env bash

cd /home/student/pond_catchment
PORT=3000

echo "Stopping services on container..."

# Stop App
if [ -f /home/student/pond_catchment/deploy/server.pid ]; then
    kill -9 "$(cat /home/student/pond_catchment/deploy/server.pid)" 2>/dev/null || true
    rm -f /home/student/pond_catchment/deploy/server.pid
fi
PID_ON_PORT=$(ss -tulpn | grep ":${PORT}" | grep -oP 'pid=\K[0-9]+' | head -n 1 || true)
if [ -n "$PID_ON_PORT" ]; then
    kill -9 "$PID_ON_PORT" 2>/dev/null || true
fi

# Stop Jaeger
if [ -f /home/student/pond_catchment/deploy/jaeger.pid ]; then
    kill -9 "$(cat /home/student/pond_catchment/deploy/jaeger.pid)" 2>/dev/null || true
    rm -f /home/student/pond_catchment/deploy/jaeger.pid
fi
pkill -f "jaeger-all-in-one" 2>/dev/null || true

# Stop Prometheus
if [ -f /home/student/pond_catchment/deploy/prometheus.pid ]; then
    kill -9 "$(cat /home/student/pond_catchment/deploy/prometheus.pid)" 2>/dev/null || true
    rm -f /home/student/pond_catchment/deploy/prometheus.pid
fi
pkill -f "prometheus.*prometheus.yml" 2>/dev/null || true

echo "All services stopped."
