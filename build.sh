#!/usr/bin/env bash
# build.sh — repo root
#
# Single-service deployment (2026-09-16): builds the frontend, copies its
# static output into a location the backend serves directly (main.py's
# STATIC_DIR), then installs backend dependencies. Render's build command
# should just be `bash build.sh`. Local dev is unaffected — Vite's own dev
# server still serves the frontend directly there; this script only
# matters for a real deploy.
set -e  # stop immediately on the first failure, don't half-deploy

echo "--- Building frontend ---"
cd pawgress-frontend
npm install
npm run build
cd ..

echo "--- Copying frontend build into backend/static ---"
rm -rf pawgress-backend/static
mkdir -p pawgress-backend/static
cp -r pawgress-frontend/dist/* pawgress-backend/static/

echo "--- Installing backend dependencies ---"
cd pawgress-backend
pip install -r requirements.txt

echo "--- Build complete ---"
