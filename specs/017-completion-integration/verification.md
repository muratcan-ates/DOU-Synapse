# 017 yerel doğrulama — 7 Eylül 2026

Bu dosya adayın kanıt satırıdır (README "Adayın kanıtı"). Her satır **koşuldu**;
koşulmayanlar ayrı başlıkta ve "KOŞULMADI" olarak yazılıdır. Anayasa III gereği bu
belgede ölçülmemiş hiçbir sayı yoktur.

Aday: `77124dc` üzerine bu commit · taban: `origin/main` (`ba69ff9`)
Ortam: yerel macOS · PostgreSQL 16 + pgvector · sahte sağlayıcı · izole test veritabanı

## Koşulan kapılar

| Kapı | Komut | Sonuç |
|---|---|---|
| Backend testleri | `cd apps/api && TEST_DB_NAME=dou_017_son .venv/bin/python -m pytest -q` | **1191 passed** <!-- docs-check: backend.tests = 1191 -->, 0 failed, 153,77 sn |
| Lint | `.venv/bin/ruff check .` | temiz |
| Biçim | `.venv/bin/ruff format --check .` | 170 dosya biçimli |
| Tip (backend) | `.venv/bin/mypy app` | 105 dosyada sorun yok <!-- docs-check: backend.mypyFiles = 105 --> |
| Web birim testleri | `cd apps/web && bun test lib/` | **428 passed** <!-- docs-check: frontend.tests = 428 -->, 39 dosya <!-- docs-check: frontend.testFiles = 39 --> |
| Tip (web) | `bunx tsc --noEmit` | temiz |
| Kontrast | `node scripts/contrast.mjs` | metin AA ve 1.4.11 eşikleri geçildi (iki tema) |
| Belge sayaçları | `node scripts/docs_check.mjs` | tüm canlı sayılar ölçümle uyuşuyor |
| Göç numarası | `python3 scripts/migration_check.py --allow-gap 0017` | PASS (19 göç <!-- docs-check: migrations.count = 19 -->, bildirilen boşluk 0017) |
| Göç kapısının kendi testi | `python3 -m unittest scripts.test_migration_check` | 10 test OK (hem Python 3.9 hem 3.12) |
| Yönetişim (son commit) | `python3 scripts/ai_sdlc_check.py --base-sha 88a8097 --head-sha <HEAD>` | PASS |
| Yönetişim (main tabanı) | `--base-sha $(git merge-base origin/main HEAD)` | PASS — bütün-dal dossier'i (017) eklendikten sonra |
| E2E vaka sayımı | `cd apps/web && ./node_modules/.bin/playwright test --list` | **42 vaka** <!-- docs-check: e2e.tests = 42 --> / 7 dosya (sayım; koşum değil) |

## Bu dilimde yakalanan ve düzeltilen gerçek kusurlar

1. **Ders silme 0009'dan beri kırıktı.** `app.audit_course_ai_policy()` tetikleyicisi,
   ders CASCADE ile silinirken `course_ai_policy_audit`'e silinmiş dersi işaret eden satır
   eklemeye çalışıyor ve yabancı anahtarı ihlal ediyordu. Hiçbir test bu yolu denemiyordu.
   `0020_course_policy_audit_cascade.sql` tetikleyiciyi ders hâlâ varken yazacak şekilde
   daraltır; `tests/test_course_policy_cascade.py` kusuru önce kırmızı yakaladı, sonra yeşil.
2. **Göç numarası çakışması:** `0016` iki dalda birden kullanılmış
   (`api_contract_admin_access` + `assessment_integrity`). Göçler her yerde dosya adı
   sırasıyla uygulandığı için numara sıranın tek kaydı; dosya adları farklı olduğundan git
   çakışma üretmiyor ve hiçbir kapı görmüyordu. `scripts/migration_check.py` yazıldı ve
   `ci.yml`'de göç uygulayan adımların önüne bağlandı.
3. **Soru silme ucu arayüzde yoktu.** `DELETE /courses/{cid}/questions/{qid}` ve testi
   vardı; hiçbir ekran çağırmıyordu. Bu yüzden belge silmenin 409 mesajı ("Önce ilgili
   soruları kaldırın") **yapılamayan** bir çıkışı tarif ediyordu. Soru panelinde onaylı
   silme eylemi eklendi; `e2e/question-delete-unblocks-document.spec.ts` çıkmazın açıldığını
   uçtan uca sabitler (409 → arayüzden sil → 204).
4. **Blueprint düzenleme ve silme arayüzde yoktu**, üstelik ekran `editingNoticeFor` ile
   düzenlemenin güvenli olduğunu **anlatıyordu**. Yanlış girilen dağılım ne düzeltilebiliyor
   ne silinebiliyordu. `BlueprintEditor` ve onaylı silme eklendi; hücreler küme olarak
   gönderilir (şema tek hücrelik güncellemeyi bilerek dışarıda bırakıyor).

## KOŞULMADI — dürüst sınır

| Ne | Neden | Nerede koşulur |
|---|---|---|
| Playwright E2E koşumu (42 vaka) | Bu dilimde yalnız **sayıldı**; koşum ayrı API+web örneği ve izole veritabanı ister | `ci.yml` `e2e` işi |
| RLS izolasyon + mutasyon paketi | `psql` üzerinden ayrı veritabanı zinciri gerektirir | `ci.yml` `api` işi |
| Konteyner derlemesi ve runtime belge varlığı kontrolü | Docker gerektirir | `ci.yml` `image` işi |
| `next build` üretim derlemesi | Bu dilimde koşulmadı | `ci.yml` `web` işi |
| Gerçek sağlayıcı (Groq/Gemini) kalitesi | Hiç ölçülmedi; `evaluation/results` altındaki 18 dosyanın **hepsi** sahte/hashing | dış girdi bekliyor |
| İnsan kabulü / öğretmen onayı | Kabul paketi hazır, etiketler **boş** | dış girdi bekliyor |
| Staging / production | Deploy edilmedi, canlı URL yok | dış girdi bekliyor |

## Bilinen, kapatılmamış kusur

`dense.py` CTE'sindeki eşitlik bozma alanları HNSW ANN yolunu yapısal olarak iptal ediyor:
gerçekçi korpusta (20.055 satır, farklı vektörler, planlayıcı serbest) `main` 1,34 ms
`Index Scan [chunks_embedding_idx]` alırken bu dal 109 ms Seq Scan'e düşüyor; RLS açıkken
fark ~437×. Bugünkü demo korpusunda görünmez, korpus büyüdüğünde görünür.
`018-retrieval-performance` şeridinde düzeltilecek; bu dilimde **bilinçli olarak** açık bırakıldı.
