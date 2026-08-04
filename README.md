# DOU-Synapse

**CourseGPT — Yapay Zekâ Destekli Kişiselleştirilmiş Ders ve Sınav Asistanı**
Doğuş Üniversitesi · COME 491/492 Bitirme Projesi · 2026

Öğretim elemanının yüklediği ders materyalleriyle **sınırlandırılmış**, her cevabı sayfa/slayt
kaynağıyla veren, Sokratik öğretim ve sınav provası sunan RAG tabanlı ders asistanı.

## Belgeler

| Belge | İçerik |
|---|---|
| [PLAN.md](PLAN.md) | Kapsam (P0/P1), 15 iş günlük takvim, roller, kabul kriterleri, riskler |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Teknoloji kararları ve gerekçeleri, veri modeli, sorgu pipeline'ı, guardrail zinciri, değerlendirme tasarımı |

## Özet

- **Yığın:** Next.js · FastAPI · Supabase (PostgreSQL + pgvector + Auth + Storage) ·
  bge-m3 embedding · hybrid retrieval (dense + BM25 + RRF) · LiteLLM (Groq ⇄ Gemini)
- **Çekirdek ilke:** Cevap, kaynağı doğrulanmadan gösterilmez. Kanıt yoksa cevap yoktur.
- **Takvim:** 4–24 Ağustos 2026 · Kapı demosu 10 Ağu · Özellik dondurma 17 Ağu

## Durum

Planlama tamamlandı, geliştirme başlıyor. Kurulum ve kullanım talimatları `docs/` altında
yayımlanacak.

## Lisans

[MIT](LICENSE)
