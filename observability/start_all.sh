#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$ROOT_DIR/logs"

mkdir -p "$LOGS_DIR"

echo "=========================================================="
echo " Starting HydroPond AI & Observability Stack"
echo "=========================================================="

# 1. Start Jaeger All-in-One
echo "[1/3] Starting Jaeger All-in-One (Tracing & UI on :16686, OTLP on :4318)..."
setsid "$SCRIPT_DIR/bin/jaeger-all-in-one" > "$LOGS_DIR/jaeger.log" 2>&1 &
JAEGER_PID=$!
echo "      Jaeger started with PID $JAEGER_PID. Log: logs/jaeger.log"

# Wait for Jaeger to bind ports
sleep 2

# 2. Start Prometheus
echo "[2/3] Starting Prometheus Server (Metrics & Dashboard on :9090)..."
setsid "$SCRIPT_DIR/bin/prometheus" \
  --config.file="$SCRIPT_DIR/prometheus.yml" \
  --web.listen-address="0.0.0.0:9090" \
  --storage.tsdb.path="$LOGS_DIR/prometheus_data" \
  > "$LOGS_DIR/prometheus.log" 2>&1 &
PROM_PID=$!
echo "      Prometheus started with PID $PROM_PID. Log: logs/prometheus.log"

sleep 2

# 3. Start HydroPond FastAPI Application
echo "[3/3] Starting HydroPond AI FastAPI Backend on :3000..."
cd "$ROOT_DIR"
setsid "$ROOT_DIR/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 3000 > "$LOGS_DIR/app_stdout.log" 2>&1 &
APP_PID=$!
echo "      HydroPond Application started with PID $APP_PID. Log: logs/app.log"

sleep 3

echo ""
echo "=========================================================="
echo " Observability Stack is LIVE!"
echo "=========================================================="
echo " - HydroPond AI Web GIS:   http://localhost:3000"
echo " - OpenAPI / Swagger Docs: http://localhost:3000/docs"
echo " - OpenTelemetry Metrics:  http://localhost:3000/metrics"
echo " - Jaeger UI (Traces):     http://localhost:16686"
echo " - Prometheus UI:          http://localhost:9090"
echo "=========================================================="
