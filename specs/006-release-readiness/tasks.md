# Tasks: Release Readiness

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/staging-preflight-report.md`

## Phase 1: Specification

- [x] T001 Exact base `6c35a7f0bdb44b88205f408ca18e6a4e50cb153e` ve kapsamı `specs/006-release-readiness/` altında kaydet.
- [x] T002 Yeni migration/deploy olmadığını ve claim boundary'yi plan/contract'ta sabitle.

## Phase 2: Preflight Foundation

- [x] T003 [P] Başarılı, blocked, failed ve redaction testlerini `.release/test_staging_preflight.py` içinde önce kırmızı yaz.
- [x] T004 `.release/staging_preflight.py` içinde result modeli, exit-code kararı ve güvenli JSON/Markdown renderer'ı uygula.
- [x] T005 Candidate exact-SHA/digest doğrulamasını mevcut `.release/validate_evidence.py` ile bağla.
- [x] T006 Health, auth, storage, migration, real-provider, kill-switch ve dış evidence kontrollerini timeout/fail-closed davranışla uygula.
- [x] T007 `.release/test_staging_preflight.py` paketini yeşile getir ve secret sentinel taramasını kaydet.

## Phase 3: Browser Integrity Gates

- [x] T008 [P] `apps/api/tests/test_role_aware_agent_application_guards.py` içine kill switch'in provider çağrısından önce kapandığını doğrudan ölçen testi ekle.
- [x] T009 [P] `apps/web/e2e/release-readiness.spec.ts` içinde aktif sınav ve yasak `mode: exam` ham POST senaryolarını ekle.
- [x] T010 `.github/workflows/ci.yml` içinde yalnız E2E job'a flag kapalı ikinci API sürecini ve zorunlu `E2E_DISABLED_API_URL` değişkenini ekle.
- [x] T011 `apps/web/components/course-assistant/course-assistant.tsx` içinde `globally_disabled` reason'ını koru ve bakım metni göster.
- [x] T012 `apps/web/e2e/release-readiness.spec.ts` içinde gerçek disabled API availability/POST ve UI bakım durumunu doğrula.

## Phase 4: Documentation and Evidence

- [ ] T013 [P] `.release/README.md`, `docs/engineering/RELEASE_PROCESS.md` ve `docs/deployment.md` güncel davranış/sınırlarla düzelt.
- [ ] T014 Hedefli Python testleri, frontend lint/type ve mümkünse gerçek API Playwright senaryolarını çalıştır.
- [ ] T015 Release docs kapısı, git whitespace/sızıntı kontrolü ve base diff denetimini çalıştır.
- [ ] T016 Her doğrulanmış mantıksal dilimi conventional commit ile kapat; çalışmayan/çalıştırılmayan kanıtı açık bırak.

## Dependencies

- T003 → T004–T007
- T009 → T010–T012
- T004–T012 → T013–T016

## Disk-Safe Execution

- Yeni bağımlılık kurulmaz ve browser indirilmez.
- `.next`, trace ve screenshot yalnız gerçek E2E koşusu için; alan 10 GiB altındaysa ağır koşu başlatılmaz.
- Tam paket yerine önce bağımlılıksız `.release` unit testleri çalıştırılır.
