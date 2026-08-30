#!/usr/bin/env bash
cd /home/student/pond_catchment

PORT=3000

echo "=== Process Status ==="
ps aux | grep uvicorn | grep "${PORT}" || echo "No uvicorn process found on port ${PORT}"
echo ""

echo "=== Port ${PORT} Listener ==="
ss -tulpn | grep "${PORT}" || echo "Port ${PORT} is not active"
echo ""

echo "=== Health Endpoint Test ==="
curl -s "http://127.0.0.1:${PORT}/health" || echo "Health check failed on port ${PORT}"
echo ""
