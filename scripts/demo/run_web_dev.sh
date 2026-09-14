#!/bin/sh
# Tasarım turu için web'in geliştirme modu: HMR açık, dev-auth girişi açık, API :8020. Port: 3021.
# Jüri demosu run_web.sh'ın üretim derlemesini kullanır; bu betik yalnız düzenlerken bakmak içindir.
set -eu
KOK="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$KOK/apps/web"
export NEXT_PUBLIC_API_URL=http://localhost:8020
export NEXT_PUBLIC_DEV_AUTH=true
export NEXT_TELEMETRY_DISABLED=1
exec bun run next dev --hostname 127.0.0.1 --port 3021
