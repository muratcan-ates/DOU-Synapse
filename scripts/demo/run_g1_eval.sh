#!/bin/sh
# G1 — GERÇEK modelle holdout değerlendirmesi (yerel).
#
# Neden ayrı bir betik: değerlendirme çalışma zamanı kendi anahtarını ister ve
# `config.py::_isolate_evaluation_credentials` bu anahtarın uygulama anahtarından
# FARKLI olmasını şart koşar (yedek sağlayıcı asla değerlendirme kotasını yemesin
# diye). Doğrulayıcı ayrıca `LLM_PRIMARY_MODEL`/`LLM_FALLBACK_MODEL` hedeflerinin
# hepsinin EVAL_LLM_PROVIDER ile eşleşmesini ister.
#
# Anahtar ~/.dou-eval-key dosyasından okunur (depo dışında, 600). Betik anahtarı
# hiçbir yere basmaz. Korpus önce kurulmuş olmalı:
#   evaluation/build_corpus.py --database dou_eval --recreate --admin/app/worker-dsn ...
#
# Kullanım:  sh scripts/demo/run_g1_eval.sh [--max-requests N] [--set holdout|calibration]
set -eu
KOK="$(cd "$(dirname "$0")/../.." && pwd)"
ANAHTAR="${DOU_EVAL_KEY_FILE:-$HOME/.dou-eval-key}"
CIKTI="${DOU_EVAL_OUT:-$HOME/.cache/dou-synapse/g1}"
KORPUS="${DOU_EVAL_CORPUS:-$CIKTI/dou-corpus.json}"
PORT="${DOU_EVAL_PORT:-8025}"
KUME=holdout
MAXREQ=40
while [ $# -gt 0 ]; do
  case "$1" in
    --max-requests) MAXREQ="$2"; shift 2 ;;
    --set) KUME="$2"; shift 2 ;;
    *) echo "bilinmeyen secenek: $1" >&2; exit 2 ;;
  esac
done

[ -f "$ANAHTAR" ] || { echo "HATA: $ANAHTAR yok. Once eval anahtarini kaydet."; exit 1; }
[ -f "$KORPUS" ] || { echo "HATA: korpus ozeti yok: $KORPUS"; exit 1; }
mkdir -p "$CIKTI"

# Anahtar dosyası KEY=VALUE satırları içerir; degerler basilmaz.
. "$ANAHTAR"
: "${EVAL_LLM_PROVIDER:?~/.dou-eval-key icinde EVAL_LLM_PROVIDER yok}"
: "${EVAL_LLM_API_KEY:?~/.dou-eval-key icinde EVAL_LLM_API_KEY yok}"
export EVAL_LLM_PROVIDER EVAL_LLM_API_KEY

DB=dou_eval
export EVAL_ADMIN_DSN="postgresql+psycopg://$(id -un)@localhost:5432/$DB"
export EVAL_APP_DSN="postgresql+psycopg://dou_app:dou_app_local@localhost:5432/$DB"
export EVAL_WORKER_DSN="postgresql+psycopg://dou_worker:dou_worker_local@localhost:5432/$DB"
export DATABASE_URL="$EVAL_APP_DSN"
export WORKER_DATABASE_URL="$EVAL_WORKER_DSN"
export EVAL_RUNTIME_ENABLED=true
# Runtime sırrı LLM anahtarından ayrı olmak zorunda (config.py doğrulaması).
export EVAL_RUNTIME_SECRET="${EVAL_RUNTIME_SECRET:-$(openssl rand -hex 24)}"
export ENVIRONMENT=local
export DEV_AUTH_ENABLED=true
export EMBEDDING_PROVIDER=fastembed
export EMBEDDING_MODEL=intfloat/multilingual-e5-large
export EMBEDDING_CACHE_DIR="${EMBEDDING_CACHE_DIR:-$HOME/.cache/dou-synapse/fastembed}"
export STORAGE_BACKEND=local
export STORAGE_ROOT="$HOME/.cache/dou-synapse/eval-storage"
export LLM_FAKE_PROVIDER=false
# Hedefler sağlayıcıyla eşleşmeli; varsayılanlar zaten groq/*.
if [ "$EVAL_LLM_PROVIDER" = "gemini" ]; then
  export LLM_PRIMARY_MODEL="${LLM_PRIMARY_MODEL:-gemini/gemini-2.0-flash}"
  export LLM_FALLBACK_MODEL="${LLM_FALLBACK_MODEL:-gemini/gemini-2.0-flash}"
else
  export LLM_PRIMARY_MODEL="${LLM_PRIMARY_MODEL:-groq/openai/gpt-oss-120b}"
  export LLM_FALLBACK_MODEL="${LLM_FALLBACK_MODEL:-groq/qwen/qwen3.6-27b}"
fi
# Uygulama .env'i YÜKLENMESİN: içindeki demo GROQ_API_KEY değerlendirme
# anahtarıyla karışmasın diye çalışma dizini depo kökü (orada .env yok).
export PYTHONPATH="$KOK/apps/api"
cd "$KOK"

echo "[g1] ön kontrol"
apps/api/.venv/bin/python scripts/real_eval_preflight.py \
  --repo "$KOK" --corpus "$KORPUS" --required-db-name "$DB" \
  --output "$CIKTI/preflight.json"

echo "[g1] API $PORT açılıyor (sağlayıcı: $EVAL_LLM_PROVIDER)"
apps/api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" \
  > "$CIKTI/api.log" 2>&1 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

i=0
while [ $i -lt 90 ]; do
  if curl -sf -o /dev/null "http://127.0.0.1:$PORT/health/ready"; then break; fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "HATA: API acilamadi. Son satirlar:"; tail -20 "$CIKTI/api.log"; exit 1
  fi
  i=$((i + 1)); sleep 2
done
[ $i -lt 90 ] || { echo "HATA: API 180 sn icinde hazir olmadi"; tail -20 "$CIKTI/api.log"; exit 1; }
echo "[g1] API hazır"

echo "[g1] $KUME kümesi, e2e katmanı, gerçek model, en fazla $MAXREQ istek"
apps/api/.venv/bin/python evaluation/evaluate.py \
  --set "$KUME" --layer e2e --require-real \
  --max-requests "$MAXREQ" --concurrency 1 \
  --api-url "http://127.0.0.1:$PORT" \
  --corpus "$KORPUS" --results-dir "$CIKTI/results" \
  --llm-note "G1 yerel gercek model kosusu ($EVAL_LLM_PROVIDER)"

echo
echo "[g1] bitti. Sonuçlar: $CIKTI/results"
ls -1 "$CIKTI/results" | tail -5
