# Implementation Plan: Release Readiness

**Branch**: `006-release-readiness` | **Date**: 2026-08-19 | **Spec**: `spec.md`

**Base SHA**: `2f40ac193114b896d33ef73e72ea51cc51f34d26` (PR #17'nin web bağımlılık güncellemesi sonrası yeniden tabanlandı; ilk kapsam tabanı `6c35a7f0bdb44b88205f408ca18e6a4e50cb153e`)

## Summary

Bağımlılıksız bir Python staging preflight CLI'ı, güvenli JSON/Markdown kanıt çıktısı ve mevcut gerçek API Playwright paketine üç fail-closed senaryo eklenir. Deploy, migration ve production secret yönetimi kapsam dışıdır.

## Technical Context

**Language/Version**: Python 3.12; TypeScript/Next.js 16

**Primary Dependencies**: Python standard library; mevcut Playwright ve FastAPI test altyapısı

**Storage**: Yeni tablo yok; salt-okunur migration ledger ve Supabase Storage metadata kontrolü

**Testing**: `unittest`, mevcut pytest, Playwright Chromium

**Target Platform**: macOS/Linux yerel doğrulama ve GitHub Actions

**Project Type**: Monorepo release tooling + web/API integration tests

**Performance Goals**: Her ağ isteği sert timeout taşır; preflight asılı kalmaz

**Constraints**: Yeni paket, migration, secret çıktısı, deploy veya production iddiası yok

**Scale/Scope**: Bir CLI, rapor contract'ı, hedefli UI düzeltmesi ve üç browser gate

## Constitution Check

- **I Kaynak yoksa cevap yok**: LLM smoke yalnız atıflı, cache dışı sonuçta geçer.
- **II İki katmanlı izolasyon**: Auth ve course-scoped smoke korunur; client course ID yetki sayılmaz.
- **III Ölçmeden iddia etme**: `not_run`/`blocked` başarıya dönüşmez; tahmin yoktur.
- **IV Fail-closed**: Eksik candidate, secret, ledger veya dış kanıt exit `2` üretir.
- **V Türkçe**: Operatör ve UI metinleri anlaşılır Türkçedir.
- **VIII Doğrulama**: Birim + gerçek API/tarayıcı kanıtı olmadan görev kapanmaz.
- **IX Git**: Exact base SHA, bağımsız dal ve conventional commit kullanılır.
- **XI Modülerlik**: HTTP, migration, redaction ve rendering ayrı saf işlevlerdir.

Gate sonucu: PASS. Anayasa istisnası yoktur.

## Project Structure

```text
.release/
├── staging_preflight.py
└── test_staging_preflight.py

apps/api/tests/
└── test_role_aware_agent_application_guards.py

apps/web/
├── components/course-assistant/course-assistant.tsx
└── e2e/release-readiness.spec.ts

specs/006-release-readiness/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/staging-preflight-report.md
└── tasks.md
```

**Structure Decision**: Release aracı `.release` içinde mevcut dependency-free evidence araçlarının yanında yaşar. Yeni E2E dosyası eski feature dalıyla çakışmayı azaltır.

## Complexity Tracking

Anayasa ihlali veya yeni framework yoktur.
