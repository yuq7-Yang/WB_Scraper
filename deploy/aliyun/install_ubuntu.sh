#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/wb_scraper}"
APP_USER="${APP_USER:-wb}"
APP_GROUP="${APP_GROUP:-wb}"
REPO_URL="${REPO_URL:-https://github.com/yuq7-Yang/WB_Scraper.git}"
BRANCH="${BRANCH:-main}"

echo "[1/8] Installing Ubuntu packages..."
apt-get update
apt-get install -y git python3 python3-venv python3-pip

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  echo "[2/8] Creating service user ${APP_USER}..."
  useradd --system --create-home --home-dir "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi

mkdir -p "${APP_DIR}"

if [ ! -d "${APP_DIR}/.git" ]; then
  echo "[3/8] Cloning repository..."
  git clone -b "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
else
  echo "[3/8] Repository already exists, fetching latest ${BRANCH}..."
  git -C "${APP_DIR}" fetch origin
  git -C "${APP_DIR}" checkout "${BRANCH}"
  git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
fi

echo "[4/8] Preparing runtime directories..."
mkdir -p "${APP_DIR}/data" "${APP_DIR}/logs"

if [ ! -f "${APP_DIR}/.env" ]; then
  echo "[5/8] Creating .env from .env.aliyun.example..."
  cp "${APP_DIR}/.env.aliyun.example" "${APP_DIR}/.env"
  echo "Edit ${APP_DIR}/.env before starting the service."
fi

echo "[6/8] Installing Python dependencies..."
python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[7/8] Installing systemd service..."
cp "${APP_DIR}/deploy/systemd/wbscraper.service" /etc/systemd/system/wbscraper.service
systemctl daemon-reload

echo "[8/8] Fixing ownership..."
chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"

echo
echo "Initial install finished."
echo "Next steps:"
echo "1. Edit ${APP_DIR}/.env"
echo "2. Run: systemctl enable --now wbscraper"
echo "3. Run: systemctl status wbscraper"
echo "4. Make sure Aliyun security group allows TCP 8888"
