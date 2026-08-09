# DOU-Synapse API imajı (T048).
#
# 3.12 pinli: onnxruntime/fastembed daha yeni Python sürümlerini geç destekliyor.
#
# ## Model neden imajın içinde
#
# Bu imaj HuggingFace'e ÇALIŞMA ZAMANINDA HİÇ GİTMEZ. Model build aşamasında
# indirilir, int8'e quantize edilir ve final katmana kopyalanır. Sebebi ölçülebilir
# bir risktir: çalışma zamanı indirmesi, scale-to-zero'dan uyanan replikanın ilk
# isteğini ~2.1 GB'lık bir dış indirmeye bağlar. 24 Ağustos'ta sunum salonunun
# internetiyle bu, ilk sorunun dakikalarca sürmesi ya da hiç cevaplanmaması demek.
#
# Aynı imaj iki Container App olarak koşar (tasks.md T049 kararı): `api` uvicorn'u,
# `worker` ise `python -m app.worker`'ı çalıştırır. Model her ikisinde de gerekli.
#
# ## Kanıt
#
# "İndirmiyor" iddiası ağsız bir konteynerde sınanır — CI'da ve elle:
#
#     docker build -t dou-synapse-api:test apps/api
#     docker run --rm --network none dou-synapse-api:test \
#       python -c "from app.modules.ingestion.embedding import FastEmbedProvider; \
#                  import os; \
#                  p=FastEmbedProvider(cache_dir=os.environ['EMBEDDING_CACHE_DIR']); \
#                  print(len(p.embed_query('deadlock nedir')))"
#
# Ağsız konteynerde 1024 basılıyorsa model gerçekten içeride demektir.

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------------------
# builder — bağımlılıklar derlenir, model indirilir ve quantize edilir
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Derleyici yalnız burada bulunur; final imaja taşınmaz.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Sanal ortam final katmana tek parça kopyalanabilsin diye ayrı bir yolda kurulur.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

# Modeli indir, int8'e indir ve fp32 ile aynı uzayda olduğunu DOĞRULA.
#
# `onnx` yalnız burada kurulur: quantizasyon bir build adımıdır, çalışma zamanı
# bağımlılığı değildir; final imaja girmemesi imajı küçültür ve saldırı yüzeyini
# daraltır. Bu yüzden pyproject'e de eklenmemiştir.
#
# Betik denklik eşiğinin altında kalırsa sıfırdan farklı döner ve BUILD DÜŞER.
# Sessizce bozuk bir vektör uzayıyla imaj üretmektense build'in kırmızı yanması
# yeğdir: fark çalışma zamanında hata vermez, yalnız retrieval kalitesi düşer.
#
# ÖLÇÜLMÜŞ UYARI (9 Ağustos, `scripts/bake_embedding_model.py`): all-MiniLM-L6-v2
# üzerinde aynı dinamik int8 yolu en düşük 0.9326 / ortalama 0.9513 kosinüs verdi
# ve en yakın komşu SIRASI korunmadı. multilingual-e5-large için sayı ölçülmedi
# (yerel makinede disk yetmedi), ama bu yön kapının düşme ihtimalinin ciddi
# olduğunu söylüyor. Kapı düşerse iki seçenek var ve ikisi de meşru:
#   1. `--build-arg EMBEDDING_QUANTIZE=false` — fp32 göm. İmaj ~2 GB büyür,
#      vektör uzayı indekstekiyle BİREBİR aynı kalır. Demo için güvenli seçenek.
#   2. Korpusu int8 ile yeniden ingest et. Bu bir ingest-zamanı kararıdır ve
#      teslimden günler önce alınmalıdır, demo sabahı değil.
ARG EMBEDDING_QUANTIZE=true
ENV EMBEDDING_CACHE_DIR=/opt/models
COPY scripts/bake_embedding_model.py ./scripts/bake_embedding_model.py
RUN pip install --no-cache-dir "onnx>=1.17" \
    && if [ "${EMBEDDING_QUANTIZE}" = "false" ]; then QUANT_FLAG="--no-quantize"; else QUANT_FLAG=""; fi \
    && python scripts/bake_embedding_model.py \
         --cache-dir "${EMBEDDING_CACHE_DIR}" \
         --report "${EMBEDDING_CACHE_DIR}/embedding_bake_report.json" \
         ${QUANT_FLAG} \
    && pip uninstall -y onnx

# ---------------------------------------------------------------------------
# runtime — derleyicisiz, kök olmayan, modeli gömülü
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Uygulama modeli buradan okur; ayar `Settings.embedding_cache_dir`'e karşılık gelir.
    EMBEDDING_CACHE_DIR=/opt/models \
    # Kütüphaneler ağa çıkmayı denemesin: gömülü model varken bir indirme denemesi
    # yalnız gecikme üretir. Değişken, sessiz bir çevrimiçi yola düşmeyi de engeller.
    HF_HUB_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

# libpq5 psycopg'nin çalışma zamanı gereksinimidir; libpq-dev (başlıklar) değil.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=appuser:appuser /opt/models /opt/models
COPY --chown=appuser:appuser app ./app

USER appuser

EXPOSE 8000

# İki servis aynı imajdan koşar; worker `command` ile bu satırı geçersiz kılar:
#   worker: ["python", "-m", "app.worker"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
