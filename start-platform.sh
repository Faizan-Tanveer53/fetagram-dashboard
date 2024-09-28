#!/usr/bin/env bash
set -e

echo "Starting Fetagram Enterprise Multi-Service Platform..."
cd "$(dirname "$0")"

# 1. Start Backend API (Port 8000)
(cd backend && python main.py) &

# 2. Start Client Web (Port 3000)
(cd client-web && python -m http.server 3000) &

# 3. Start Isolated Admin Dashboard (Port 3001)
(cd admin-dashboard && python -m http.server 3001) &

echo "✅ Fetagram Backend running on http://localhost:8000"
echo "✅ Fetagram Client Web running on http://localhost:3000"
echo "✅ Fetagram Admin Portal running on http://localhost:3001"
wait
