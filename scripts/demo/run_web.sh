#!/bin/sh
# Jüri demosu web'i: üretim derlemesi, dev-auth girişi açık, API :8020. Port: 3020.
set -eu
KOK="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$KOK/apps/web"
export NEXT_PUBLIC_API_URL=http://localhost:8020
export NEXT_PUBLIC_DEV_AUTH=true
export NEXT_TELEMETRY_DISABLED=1
bun run next build
exec bun run next start --hostname 127.0.0.1 --port 3020
