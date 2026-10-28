#!/bin/sh
# Start the API the way a server runs it (Render, Docker): migrate the database, then serve.
#
#   PORT                 port to listen on (default 8000; Render sets it)
#   FORWARDED_ALLOW_IPS  proxies whose X-Forwarded-For is trusted, so rate limits see the
#                        real client IP. uvicorn's default is 127.0.0.1; behind a hosting
#                        provider's proxy (Render) set it to "*".
#
# One process on purpose: the rate limits are counted in memory, per process.
set -e
cd "$(dirname "$0")"
alembic upgrade head
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --no-server-header \
  --timeout-graceful-shutdown 20
