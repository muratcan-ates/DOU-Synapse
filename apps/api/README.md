# DOU-Synapse API

FastAPI backend'i: ders materyaliyle sınırlandırılmış RAG hattı, guardrail zinciri,
sınav/Sokratik öğretim motoru.

## Geliştirme kurulumu

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
cp ../../.env.example .env      # değerleri doldur
uv run alembic-yok              # migration'lar supabase/migrations altında düz SQL
uv run uvicorn app.main:app --reload
```

Veritabanı (lokal):

```bash
createdb dou_synapse
psql -d dou_synapse -f ../../supabase/migrations/0001_core_schema.sql
```

## Kalite kapıları

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Modül haritası

| Dizin | Sorumluluk |
|---|---|
| `app/core/` | config, DB oturumu, JWT doğrulama, hata ve log altyapısı |
| `app/models/` | SQLAlchemy tabloları |
| `app/schemas/` | API giriş/çıkış sözleşmeleri (Pydantic) |
| `app/api/` | HTTP uçları ve yetkilendirme bağımlılıkları |
| `app/modules/ingestion/` | dosya ayrıştırma, chunking, embedding |
| `app/modules/retrieval/` | hybrid arama (dense + FTS + RRF) |
| `app/modules/generation/` | LLM çağrısı, şemalı çıktı |
| `app/modules/guardrails/` | atıf doğrulama, kanıt eşiği, sızıntı filtresi |
| `app/modules/assessment/` | soru üretimi, puanlama, "neden yanlış" |
| `app/modules/mastery/` | konu bazlı performans göstergesi |
