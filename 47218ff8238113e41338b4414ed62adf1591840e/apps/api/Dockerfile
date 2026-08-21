# DOU-Synapse API imajı.
#
# 3.12 pinli: onnxruntime/fastembed (bge-m3) daha yeni Python sürümlerini geç destekliyor.
# Embedding modeli ileride BUILD AŞAMASINDA imaja gömülecek; çalışma zamanında
# HuggingFace'e bağımlı kalmak, scale-to-zero sonrası ilk isteği dış servise bağlar
# (ARCHITECTURE.md §1, "Deploy gerçekliği").

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --no-cache-dir .

# Kök olmayan kullanıcı
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
