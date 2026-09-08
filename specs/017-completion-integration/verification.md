# 017 yerel doğrulama — 7 Eylül 2026

Bu dosya adayın kanıt satırıdır (README "Adayın kanıtı"). Her satır **koşuldu**;
koşulmayanlar ayrı başlıkta ve "KOŞULMADI" olarak yazılıdır. Anayasa III gereği bu
belgede ölçülmemiş hiçbir sayı yoktur.

Aday: `77124dc` üzerine bu commit · taban: `origin/main` (`ba69ff9`)
Ortam: yerel macOS · PostgreSQL 16 + pgvector · sahte sağlayıcı · izole test veritabanı

## Koşulan kapılar

| Kapı | Komut | Sonuç |
|---|---|---|
| Backend testleri | `cd apps/api && TEST_DB_NAME=dou_017_v2 .venv/bin/python -m pytest -q` | **1197 passed** <!-- docs-check: tarihsel 1197 · 2026-09-07 -->, 0 failed, 142,57 sn |
| Lint | `.venv/bin/ruff check .` | temiz |
| Biçim | `.venv/bin/ruff format --check .` | 170 dosya biçimli |
| Tip (backend) | `.venv/bin/mypy app` | 105 dosyada sorun yok <!-- docs-check: tarihsel 105 · 2026-09-07 --> |
| Web birim testleri | `cd apps/web && bun test lib/` | **428 passed** <!-- docs-check: tarihsel 428 · 2026-09-07 -->, 39 dosya <!-- docs-check: tarihsel 39 · 2026-09-07 --> |
| Tip (web) | `bunx tsc --noEmit` | temiz |
| Kontrast | `node scripts/contrast.mjs` | metin AA ve 1.4.11 eşikleri geçildi (iki tema) |
| Belge sayaçları | `node scripts/docs_check.mjs` | tüm canlı sayılar ölçümle uyuşuyor |
| Göç numarası | `python3 scripts/migration_check.py --allow-gap 0017` | PASS (19 göç <!-- docs-check: tarihsel 19 · 2026-09-07 -->, bildirilen boşluk 0017) |
| Göç kapısının kendi testi | `python3 -m unittest scripts.test_migration_check` | 10 test OK (hem Python 3.9 hem 3.12) |
| Yönetişim (son commit) | `python3 scripts/ai_sdlc_check.py --base-sha 88a8097 --head-sha <HEAD>` | PASS |
| Yönetişim (main tabanı) | `--base-sha $(git merge-base origin/main HEAD)` | PASS — bütün-dal dossier'i (017) eklendikten sonra |
| E2E vaka sayımı | `cd apps/web && ./node_modules/.bin/playwright test --list` | **42 vaka** <!-- docs-check: tarihsel 42 · 2026-09-08 --> / 7 dosya (sayım; koşum değil) |

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

5. **`.env` ile verilen `WORKER_DRAIN_URL` sessizce yok sayılıyordu.**
   `trigger_drain` adresi `os.environ`'dan okuyordu; `pydantic-settings` `.env` dosyasını
   `Settings`'e okur ama `os.environ`'a **yazmaz**. Sonuç: `.env` ile yapılandırılan her
   dağıtımda uzak worker dalı hiç seçilmiyor, ingestion API sürecinde koşuyordu — oysa
   `docs/deployment.md` ve `.env.example` çalıştığını söylüyordu. Artık `Settings`'ten
   okunuyor; regresyon testi adresi ortama hiç koymadan yalnız ayara veriyor ve eski
   davranış geri konularak kırmızı yandığı doğrulandı.
6. **Tam-tokenizer kota yolu ölüydü:** küme yalnız sağlayıcının kaldırdığı
   `groq/llama-3.3-70b-versatile`'ı tanıyor, yapılandırılmış model ise başkası. Dal
   üretimde hiç koşmuyor. Davranış fail-safe ve rezervasyon sonradan uzlaştırılıyor, ama
   modül dokümanı tersini söylüyordu. Gerçek yazıldı, iki bekçi test eklendi.
7. **`escape_for_context`'in ikinci temizleme katmanı ulaşılamazdı** (bütün sınır
   işaretleri `<` ile başlıyor, kaçış zaten `<`'i yok ediyor). Ulaşılamayan savunma
   yanıltıcıdır; kaldırıldı, invaryant üç testle çivilendi. Güvenlik seviyesi değişmedi.

## İkinci turda koşulan kanıtlar (daha önce hiçbir iş akışında koşmuyordu)

Beş kanıt betiği depoda vardı ama **hiçbir workflow onları çağırmıyordu** — yani
"politika bozulduğunda testimiz kırmızı yanar" iddiasının kanıtı yazılıp rafta
bırakılmıştı. Koşmayan kanıt kanıt değildir; hepsi `ci.yml`'in `api` işine bağlandı ve
yerelde koşuldu:

| Kanıt | Sonuç |
|---|---|
| `rls_isolation_mutation_check.sh` | **57 mutasyon denendi, 57'si yakalandı** (115 iddia) |
| `rls_blueprint.sql` | 17 iddia, 0 FAIL |
| `rls_blueprint_mutation_check.sh` | **23 mutasyon, 23'ü yakalandı** |
| `rls_portal_admin_mutation_check.sh` | **3 sızıntı mutasyonu, 3'ü yakalandı** |
| `rls_question_authoring.sql` | 0 FAIL |
| `question_authoring_concurrency_check.py` | 4 PASS (eşzamanlı cevap/oturum taslağı dondurur) |

Ayrıca RLS kapısında **iki ayrı sessizlik** vardı ve ikisi de ölçüldü (boş bir veritabanında
bilerek bozuk SQL koşturularak):

| Koşum | Çıkış kodu |
|---|---|
| `psql -f` (ON_ERROR_STOP yok) | **0** — SQL yarıda kesildi, kapı yeşil |
| `psql -v ON_ERROR_STOP=1 -f` | 3 ✓ |
| `ON_ERROR_STOP` + `\| tee` (pipefail yok) | **0** — `tee` her zaman 0 döner, yutuldu |
| `ON_ERROR_STOP` + `\| tee` + `set -o pipefail` | 3 ✓ |

Yani ekrana `FAIL` yazmak SQL hatası değildir ve tek başına `pipefail` yetmez. RLS
adımlarına hem `set -euo pipefail` hem `-v ON_ERROR_STOP=1` (ve psqlrc'yi devre dışı bırakan
`-X`) eklendi. Bu ayrımı `019` şeridini hazırlayan GPT oturumu yakaladı; ölçüm burada.

## KOŞULMADI — dürüst sınır

| Ne | Neden | Nerede koşulur |
|---|---|---|
| Playwright E2E koşumu | Bu dilimde yalnız **sayıldı**; koşum ayrı API+web örneği ister | `ci.yml` `e2e` işi |
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
