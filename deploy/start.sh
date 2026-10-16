#!/usr/bin/env bash
set -e

cd /home/student/pond_catchment

PORT=3000
LOGS_DIR=/home/student/pond_catchment/deploy/logs
mkdir -p "$LOGS_DIR"

echo "=== Deploying HydroPond AI & OpenTelemetry on Container ==="

# 1. Install / update dependencies if needed
if [ -f "/home/student/pond_catchment/.venv/bin/pip" ]; then
    /home/student/pond_catchment/.venv/bin/pip install -q -r requirements.txt
fi

# 2. Ensure standalone observability binaries exist
mkdir -p /home/student/pond_catchment/observability/bin
if [ ! -f /home/student/pond_catchment/observability/bin/jaeger-all-in-one ]; then
    echo "Downloading Jaeger All-in-One..."
    cd /home/student/pond_catchment/observability
    curl -L -s https://github.com/jaegertracing/jaeger/releases/download/v1.60.0/jaeger-1.60.0-linux-amd64.tar.gz | tar -xz
    cp jaeger-1.60.0-linux-amd64/jaeger-all-in-one bin/
    rm -rf jaeger-1.60.0-linux-amd64*
    chmod +x bin/jaeger-all-in-one
    cd /home/student/pond_catchment
fi

if [ ! -f /home/student/pond_catchment/observability/bin/prometheus ]; then
    echo "Downloading Prometheus..."
    cd /home/student/pond_catchment/observability
    curl -L -s https://github.com/prometheus/prometheus/releases/download/v3.15.0/prometheus-3.15.0.linux-amd64.tar.gz | tar -xz
    cp prometheus-3.15.0.linux-amd64/prometheus bin/
    rm -rf prometheus-3.15.0.linux-amd64*
    chmod +x bin/prometheus
    cd /home/student/pond_catchment
fi

# 3. Stop existing processes
pkill -f "jaeger-all-in-one" 2>/dev/null || true
pkill -f "prometheus.*prometheus.yml" 2>/dev/null || true
PID_ON_PORT=$(ss -tulpn | grep ":${PORT}" | grep -oP 'pid=\K[0-9]+' | head -n 1 || true)
if [ -n "$PID_ON_PORT" ]; then
    kill -9 "$PID_ON_PORT" 2>/dev/null || true
fi
sleep 1

# 4. Start Jaeger
echo "Starting Jaeger All-in-One (Tracing & UI on :16686, OTLP on :4318)..."
nohup /home/student/pond_catchment/observability/bin/jaeger-all-in-one > "$LOGS_DIR/jaeger.log" 2>&1 &
echo $! > /home/student/pond_catchment/deploy/jaeger.pid

# 5. Start Prometheus
echo "Starting Prometheus Server (:9090)..."
nohup /home/student/pond_catchment/observability/bin/prometheus \
  --config.file=/home/student/pond_catchment/observability/prometheus.yml \
  --web.listen-address="0.0.0.0:9090" \
  --storage.tsdb.path="$LOGS_DIR/prometheus_data" \
  > "$LOGS_DIR/prometheus.log" 2>&1 &
echo $! > /home/student/pond_catchment/deploy/prometheus.pid

# 6. Start HydroPond FastAPI Application
echo "Starting HydroPond API on port ${PORT}..."
nohup /home/student/pond_catchment/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT} > "$LOGS_DIR/server.log" 2>&1 &
echo $! > /home/student/pond_catchment/deploy/server.pid

sleep 2
echo "=========================================================="
echo " Deployment Complete on Container!"
echo " - HydroPond API: :${PORT} (Mapped to external port :3317)"
echo " - Jaeger UI:     :16686"
echo " - Prometheus UI: :9090"
echo " - OpenTelemetry: /metrics"
echo "=========================================================="
