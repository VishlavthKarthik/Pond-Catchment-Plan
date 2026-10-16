#!/usr/bin/env bash

echo "Stopping HydroPond AI & Observability services..."

# Kill uvicorn on port 3000
fuser -k 3000/tcp 2>/dev/null || true
pkill -f "app.main:app" 2>/dev/null || true

# Kill Jaeger
pkill -f "jaeger-all-in-one" 2>/dev/null || true

# Kill Prometheus
pkill -f "prometheus.*prometheus.yml" 2>/dev/null || true

echo "All services stopped successfully."
