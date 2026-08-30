#!/usr/bin/env bash
cd /home/student/pond_catchment

echo "=== Process Status ==="
ps aux | grep uvicorn | grep 3317 || echo "No uvicorn process found on port 3317"
echo ""

echo "=== Port 3317 Listener ==="
ss -tulpn | grep 3317 || echo "Port 3317 is not active"
echo ""

echo "=== Health Endpoint Test ==="
curl -s http://127.0.0.1:3317/health || echo "Health check failed"
echo ""
