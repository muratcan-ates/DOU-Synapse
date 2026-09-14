#!/bin/sh
# Jüri demosu API'si (14 Eylül 2026): temiz `dou_demo` veritabanı, dev-auth ile
# sentetik hesaplar, gerçek E5 embedding, ürün bayrakları açık.
# LLM: apps/api/.env içinde GROQ_API_KEY doluysa gerçek model; boşsa sahte
# sağlayıcı (cevaplar etiketli, gerçek model değil). Anahtar değeri basılmaz.
# Kurulum: scripts/demo/setup_db.sh (göçler + rol + seed). Port: 8020.
set -eu
KOK="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$KOK/apps/api"
export ENVIRONMENT=local
export DEV_AUTH_ENABLED=true
export EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-fastembed}"
export EMBEDDING_MODEL="${EMBEDDING_MODEL:-intfloat/multilingual-e5-large}"
export EMBEDDING_CACHE_DIR="${EMBEDDING_CACHE_DIR:-$HOME/.cache/dou-synapse/fastembed}"
# Yerel roller ve parolalar supabase/local_dev_setup.sql'de sabittir (yalnız yerel geliştirme).
export DATABASE_URL="postgresql+psycopg://dou_app:dou_app_local@localhost:5432/${DOU_DEMO_DB:-dou_demo}"
export WORKER_DATABASE_URL="postgresql+psycopg://dou_worker:dou_worker_local@localhost:5432/${DOU_DEMO_DB:-dou_demo}"
export CORS_ORIGINS='["http://localhost:3020","http://127.0.0.1:3020","http://localhost:3021","http://127.0.0.1:3021"]'
export STORAGE_BACKEND=local
export STORAGE_ROOT="${STORAGE_ROOT:-$HOME/.cache/dou-synapse/demo-storage}"
export QUESTION_AUTHORING_ENABLED=true
export STUDENT_ASSESSMENT_WORKSPACE_ENABLED=true
mkdir -p "$STORAGE_ROOT"
ENV_FILE="$KOK/apps/api/.env"
if [ -f "$ENV_FILE" ] && grep -qE '^GROQ_API_KEY=.+' "$ENV_FILE"; then
  GROQ_API_KEY="$(grep -E '^GROQ_API_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  export GROQ_API_KEY
  export LLM_FAKE_PROVIDER=false
  echo "[demo] sağlayıcı: Groq (anahtar .env'den okundu)"
else
  export LLM_FAKE_PROVIDER=true
  echo "[demo] GROQ_API_KEY yok: sahte sağlayıcı — cevaplar gerçek model değil"
fi
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8020
