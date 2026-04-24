#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/wb_scraper}"
BRANCH="${BRANCH:-main}"
APP_USER="${APP_USER:-wb}"
APP_GROUP="${APP_GROUP:-wb}"

echo "[1/5] Updating repository..."
git -C "${APP_DIR}" fetch origin
git -C "${APP_DIR}" checkout "${BRANCH}"
git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"

echo "[2/5] Updating Python dependencies..."
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[3/5] Refreshing service file..."
cp "${APP_DIR}/deploy/systemd/wbscraper.service" /etc/systemd/system/wbscraper.service
systemctl daemon-reload

echo "[4/5] Restarting service..."
chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
systemctl restart wbscraper

echo "[5/5] Service status:"
systemctl --no-pager --full status wbscraper
