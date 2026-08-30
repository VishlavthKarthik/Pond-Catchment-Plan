#!/usr/bin/env bash
# deploy.sh — Deploy the Pond Catchment API to a remote constrained box
# Usage: ./deploy/deploy.sh <user@host> [deploy_dir]
#
# Requirements on the remote:
#   - Python 3.10+
#   - git
#   - systemd
#   - (optional) nginx

set -euo pipefail

REMOTE="${1:?Usage: $0 <user@host> [deploy_dir]}"
DEPLOY_DIR="${2:-/opt/pond-api}"
SERVICE_NAME="pond-api"

echo "==> Deploying to ${REMOTE}:${DEPLOY_DIR}"

ssh "$REMOTE" bash -s <<EOF
set -euo pipefail

# --- Swap file (safety net for 512 MB RAM) ---
if [ ! -f /swapfile ]; then
  echo "[swap] Creating 512 MB swap file..."
  fallocate -l 512M /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=512
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "[swap] Done."
else
  echo "[swap] Swap file already exists, skipping."
fi

# --- Pull/clone repo ---
if [ -d "${DEPLOY_DIR}/.git" ]; then
  echo "[git] Pulling latest..."
  git -C "${DEPLOY_DIR}" pull --ff-only
else
  echo "[git] Cloning..."
  git clone "$(git config --get remote.origin.url 2>/dev/null || echo 'PASTE_REPO_URL_HERE')" "${DEPLOY_DIR}"
fi

# --- Virtual environment ---
cd "${DEPLOY_DIR}"
if [ ! -d .venv ]; then
  echo "[venv] Creating virtual environment..."
  python3 -m venv .venv
fi
echo "[pip] Installing dependencies..."
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt --quiet

echo "[pip] Installed package sizes:"
du -sh .venv/lib/

# --- systemd service ---
cp deploy/pond-api.service /etc/systemd/system/${SERVICE_NAME}.service
sed -i "s|/opt/pond-api|${DEPLOY_DIR}|g" /etc/systemd/system/${SERVICE_NAME}.service
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"
sleep 2
systemctl is-active "${SERVICE_NAME}" && echo "[service] ${SERVICE_NAME} is running." || echo "[service] WARNING: ${SERVICE_NAME} may not be running."

# --- (optional) nginx ---
if command -v nginx >/dev/null 2>&1; then
  cp deploy/nginx.conf /etc/nginx/sites-available/${SERVICE_NAME}
  ln -sf /etc/nginx/sites-available/${SERVICE_NAME} /etc/nginx/sites-enabled/${SERVICE_NAME}
  nginx -t && systemctl reload nginx && echo "[nginx] Reloaded."
fi

echo "==> Deploy complete. Test with:"
echo "  curl http://localhost:8000/health"
EOF
