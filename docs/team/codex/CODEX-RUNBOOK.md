# CODEX RUNBOOK — DOU-Synapse'i production seviyesine taşı (tek sohbet, durmaksızın)

> 018 uzlaştırma notu (8 Eylül 2026): Bu runbook 017 tabanındaki iş önerisi olarak korunur. Güncel durum [tamamlama defterinde](../../completion-program.md) ve [018 kabul kaydında](../../../specs/018-codex-production-line/verification.md) izlenir. B2 zaten014'te vardı; B1 konusuz grubu bilinçli destekler; B6 authoring kapalıyken uygun havuz yayını mümkündür; B3 teknik sözleşme ile gerçek model kalitesi ayrı kabullerdir. 0024 sonrasında göç denetimi açık0017/0021/0022/0023 boşluklarını kullanır. Bu tarihsel metindeki eksik/tamam iddiaları yeniden ölçmeden güncel kabul sayılmaz.

> Bu belge tek bir Codex oturumunun **kuyruktan iş çekerek** kesintisiz çalışması için
> yazıldı. Planı Claude yaptı, ölçümleri Claude aldı; geliştirmeyi sen (Codex) yaparsın.
> Sıra: **§0 kurallar → §1 durum → §2 çalışma döngüsü → §3 iş kuyruğu.** Kuyruğu yukarıdan
> aşağı tüket; her iş bittiğinde §2'deki döngüyü kapat, sormadan sıradakine geç. Yalnız
> §4'teki "Murat'a sor" maddelerinde dur.

---

## §0 — Kimlik, taban, pazarlık edilmeyen kurallar

**Depo:** `github.com/muratcan-ates/DOU-Synapse` (public).
**Taban:** dal `017-completion-integration`'ın **uç commit'i** (`git rev-parse origin/017-completion-integration`).
§1'deki ölçümler `b1986792e5d12f22b314cb06c8f5fcdcb8724cee` anında alındı; uç ondan yalnız bu
runbook'un commit'i kadar ileridedir. `main` (`ba69ff9`) 20 Ağustos'ta kaldı; ürün 017'de.
**`main`'den değil, 017'nin ucundan dallan.**

**Çalışma dalı:** `018-codex-production-line` — 017 ucundan bir kez aç, sonuna kadar orada
çalış. Her iş = bir commit. İlk commit'ten sonra `017-completion-integration` hedefli bir
**draft PR** aç ve her commit'te push'la; Murat istediği commit'te birleştirir. Bekleme yok.

**Kurulum (Codex ortamı):**
```bash
git clone https://github.com/muratcan-ates/DOU-Synapse && cd DOU-Synapse
git checkout -b 018-codex-production-line origin/017-completion-integration
cd apps/api && uv sync --extra dev --frozen && cd ../web && bun install && cd ../..
# PostgreSQL 16 + pgvector gerekir. Yoksa: docker compose up -d db  (docker-compose.yml)
# Docker da yoksa: DB isteyen kapıları koşamazsın; §2'deki "not-run" kuralı geçerli.
```
`.env` yok ve **olmayacak** (gitignore). Testler `.env` istemez; API'yi ayağa kaldırman
gerekirse `DEV_AUTH_ENABLED=true EMBEDDING_PROVIDER=hashing` ile çalışır (hashing yalnız
test içindir; gerçek arama kalitesi için `fastembed`).

**Pazarlık edilmeyenler (Anayasa):**
1. **Ölçmediğini yazma.** "Kanıtlandı / geçti / çalışıyor" yalnız koşturduğun komutun çıktısıyla.
   Koşamadıysan `not-run` yaz. Sayı uydurma, SHA uydurma, dosya uydurma.
2. **Kaynak yoksa cevap yok.** Kanıt eşiği altındaki sorgu LLM'e gitmeden ret döner. Bunu
   gevşeten hiçbir değişiklik yapma.
3. **İki katmanlı yetki.** Sunucu üyelik kontrolü **ve** aynı oturumda PostgreSQL RLS. Biri
   yetmez. RLS testleri politika bilerek bozulunca kırmızı yanmalı (mutasyon betikleri var).
4. **Şema düz SQL göçleriyle**, dosya adı sırasıyla uygulanır. Numara sıranın tek kaydı.
   Göç eklerken `python3 scripts/migration_check.py --allow-gap 0017` yeşil kalmalı.
   Rezerve numaralar: **0021, 0022, 0023** (aşağıda hangi işe ait olduğu yazıyor); 0017'yi
   **kullanma** (başka dalda). Yeni ihtiyaç doğarsa 0024'ten devam et ve kuyruğa not düş.
5. **Yönetişim (`.ai/`)**: `.ai/policy.json`'daki hassas yola dokunan commit **aynı commit'te**
   dossier (`.ai/changes/NNN-*.json`) + kanıt (`.ai/evidence/NNN-*.json`) ister. Kayıtlar
   append-only: var olanı düzenleme/silme; düzeltme yeni kayıttır. Numara: `.ai/changes/`
   altındaki en büyük sayının bir fazlası (`ls .ai/changes | sort | tail -2`); iki kayıt aynı
   öneki alamaz. Şablon: `.ai/changes/example.json`; `evaluation` referansları gerçek dosya olmalı.
   **CI gerçeği (ölçüldü):** `ci.yml`, `ai-quality.yml`, `security.yml` yalnız **`main`'e push**
   ve **`pull_request`** olayında koşar; `018-codex-production-line`'a push **hiçbir şey
   tetiklemez**. Tek sinyal PR check'idir ve doğrulayıcı orada tabanı **PR hedef dalının ucu**
   alır; bir dossier yalnız **HEAD'de tanıtıldığı** commit'te ve `base_sha` o tabana eşitse
   sayılır (`scripts/ai_sdlc_check.py:1795-1823`). Dolayısıyla:
   - **Her hassas commit** kendi dossier'ini taşır: `base_sha` = üstüne inşa ettiğin commit
     (commit'ten önce `git rev-parse HEAD`), `candidate_sha: "SELF"`, kanıt dosyasının
     `report_sha256`'sı gerçek özet. Bu insan inceleme izidir; PR kapısını tek başına yeşile çevirmez.
   - **Her push'tan önce** `apps/api/.venv/bin/python scripts/refresh_aggregate_dossier.py --target origin/017-completion-integration`
     koştur. `AGGREGATE=OK` derse dosya yazmaz — geç. `AGGREGATE=WROTE` derse: ürettiği kaydın
     `evaluation` bloğunu gerçek dosyalara bağla, kanıtı koştuğun komutlarla `pass`e çek — kanıt
     dosyasında `result`, dossier'de `evidence[0].result` **ve** yeniden hesaplanmış
     `report_sha256` — `status: evidence-ready` yap ve **push'lanacak son commit'e** ekle
     (o commit henüz push'lanmadıysa `--amend`, aksi hâlde yeni commit). Toplayıcı yeni ölçüm
     iddia etmez; kanıt metnini öyle yaz. Doğrulayıcıyı gevşetme, `continue-on-error` ekleme.
   - Yerel doğrulama commit **sonrası**, temiz ağaçta; `--head-sha`'ya sembolik `HEAD` verme
     (`HEAD_REF_NOT_IMMUTABLE`), kirli ağaçta koşma (`CHECKOUT_SHA`).
6. **Dil:** kod/dosya adı İngilizce; yorum, docstring, kullanıcıya dönen metin ve commit gövdesi
   Türkçe. Commit başlığı conventional (`fix(retrieval): …`), gövdede **neden**.
   `Co-Authored-By` satırı **asla**.
7. **Tasarım:** `DESIGN.md` tek otorite. İkon kütüphanesi yok, elle SVG yok (tek istisna marka
   işareti). Renk tek başına bilgi taşımaz — metin + `aria-*`. Kontrast kapısı iki temada AA.
8. **Bağımlılık ekleme** (`pyproject.toml`, `uv.lock`, `package.json`, `bun.lock`) → §4'e düş,
   Murat'a sor. Gerekçesini ve alternatifini yaz, sonra kuyruktaki bir sonraki işe geç.

**Kapılar — her commit'ten önce, hepsi yeşil:**
```bash
KOK="$(git rev-parse --show-toplevel)"
cd "$KOK/apps/api" && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
TEST_DB_NAME=dou_codex .venv/bin/python -m pytest -q
cd "$KOK/apps/web" && bun test lib/ && bunx tsc --noEmit && node scripts/contrast.mjs
cd "$KOK" && node scripts/docs_check.mjs
python3 scripts/migration_check.py --allow-gap 0017
# yönetişim — commit SONRASI, temiz ağaçta; PR check'inin gördüğü taban = 017 ucu:
python3 scripts/ai_sdlc_check.py --base-sha "$(git merge-base origin/017-completion-integration HEAD)" --head-sha "$(git rev-parse HEAD)"
```
Ağır olanlar (tam pytest, `bun run build`, Playwright, RLS mutasyon betikleri) sıralı koşar.
`docs_check --duzelt`'i yalnız **web bağımlılıkları + `bunx playwright install chromium`**
kuruluyken koştur; yoksa frontend/e2e sayaçlarını yanlış yazar.

---

## §1 — Doğrulanmış durum (7 Eylül 2026, hepsi ölçüldü)

**Ürün:** FastAPI + SQLAlchemy async + PostgreSQL 16/pgvector · Next.js 16 + React 19 +
Tailwind v4 · litellm→Groq (`groq/openai/gpt-oss-120b`, yedek `groq/qwen/qwen3.6-27b`) ·
fastembed `multilingual-e5-large`. LangChain/LlamaIndex **yok ve eklenmeyecek**.

**Büyüklük:** 1197 backend testi · 428 web birim testi · 42 Playwright vakası (sayım) ·
67 API ucu / 16 modül · 19 web sayfası · 19 göç · 27 tablo · RLS 115+59+37+28 iddia,
mutasyon 57/57 + 24/24 + 23/23 + 3/3 yakalandı.

**Danışman gereksinimleri (Yasemin Karagül, 30 Tem):** 9 gereksinimden **5 tam**
(kaynak yönetimi, Sokratik mod, soru havuzu, kapsam kontrolü, kaynak gösterimi), **4 kısmi**:
- Sınav provası: süre/puanlama sunucuda var; öğrenci web'den blueprint sınavına **giremiyor**
- Konu seçerek soru çözme: API `topic_id` alıyor, exam sayfasında seçici **yok**
- "Neden yanlış?": MCQ+kısa cevapta var; açık uçlu/kod sorularında çelişen kaynak **yok**
- Kod/senaryo inceleme: `code_trace`/`bug_hunt` tipleri var, backend puanlama testi **sıfır**

**Beklenen üç çıktı:** çalışır web platformu (yerelde var, canlı yok) · örnek materyal paketi
+ **başarı testi raporu** (`docs/test-report.md` var, her kalite sayısı sahte sağlayıcı damgalı)
· eğitmen/öğrenci kılavuzu (var, 9 Ağustos arayüzünü anlatıyor; admin kılavuzu yok).

**En büyük boşluk:** `evaluation/results` altındaki 18 dosyanın **hepsi** fake/hashing.
Gerçek sağlayıcı koşusu **sıfır**. Harness hazır, ölçüm yok.

**Bu gece Claude'un kapattığı kusurlar (tekrar açma, üstüne inşa et):**
1. Ders silme 0009'dan beri kırıktı (denetim tetikleyicisi FK ihlali) → `0020` + regresyon testi
2. `0016` göç numarası iki dalda → `scripts/migration_check.py` + CI adımı
3. Soru silme ucu arayüzde yoktu (belge silme 409 çıkmazı) → `ConfirmAction` + E2E
4. Blueprint düzenleme/silme yoktu → `BlueprintEditor` + silme
5. `.env` ile verilen `WORKER_DRAIN_URL` yok sayılıyordu (`os.environ` vs Settings) → düzeltildi + mutasyon kanıtlı test
6. Tam-tokenizer kota yolu ölüydü → gerçek yazıldı + 2 bekçi test
7. `escape_for_context` ulaşılamaz ikinci katman → kaldırıldı + 3 invaryant testi
8. `psql | tee` çıkış kodu yutuyordu + `ON_ERROR_STOP` yoktu → ikisi de eklendi
9. 5 kanıt betiği hiçbir workflow'da koşmuyordu → CI'a bağlandı, yerelde yeşil
10. README kanıt bağlantısı olmayan dosyaya gidiyordu → `specs/017-completion-integration/verification.md`
11. "41/41 tarayıcı testi geçti" toplama sayısıydı → ölçümle uyumlu hâle getirildi
12. Yönetişim kapısı main tabanında düşüyordu → toplayıcı dossier + `refresh_aggregate_dossier.py`
13. test-report RLS "8 iddia" → bugünkü 115

**Bilinen, açık bırakılan kusur (Faz C senin):** `dense.py` CTE'sindeki eşitlik bozma alanları
HNSW yolunu iptal ediyor — ölçüm: `main` 1,34 ms `Index Scan` ↔ 017 109 ms Seq Scan; RLS ile ~437×.

---

## §2 — Çalışma döngüsü (her iş için)

```
1. Kuyruktan sıradaki işi al; "Kabul" satırını oku.
2. Dokunacağın dosyaların BUGÜNKÜ hâlini oku (varsayma).
3. Uygula. Yalnız o işin dosyalarına dokun.
4. Kapıları koştur (§0). Kırmızıysa düzelt; kapıyı gevşetme.
5. Hassas yola dokunduysan aynı commit'e dossier + kanıt yaz (base_sha = ebeveyn, §0/5).
   Push'tan önce toplayıcıyı yenile; AGGREGATE=OK ise geç, WROTE ise son commit'e ekle.
6. Commit (Türkçe gövde, neden). Push. PR açıklamasına tek satır ekle:
   "[Faz X / İş N] <başlık> — kapılar: … — not-run: …"
7. Sıradakine geç. SORMA — yalnız §4'teki durumlarda dur.
```
Bir iş 2 saatten uzun sürüyorsa böl: çalışan kısmı commit'le, kalanını kuyruğa "N-b" olarak
yaz ve devam et. Bir kapı senin dışındaki sebeple kırmızıysa (ör. Groq kotası), kanıta
`not-run` + sebep yaz, işi bitmiş sayma, kuyrukta "engellendi" işaretle ve geç.

---

## §3 — İş kuyruğu (yukarıdan aşağı)

### FAZ A — Kapı ve kanıt hijyeni (ucuz, güveni açar)

**A1. `.release/test_*.py` ve rol-ajan mutasyon koşucusunu CI'a bağla.**
`.release/test_verify_checks.py`, `.release/test_validate_evidence.py` (26 test) ve
`scripts/role_agent_application_mutation_check.py` **hiçbir workflow'da koşmuyor** (grep ile
doğrulandı). `ci.yml`'e ADIM olarak ekle (İŞ ekleme — `.release/verify_checks.py` görünen iş
adlarını tam sayıyor; iş eklersen release kabulü kırılır).
Kabul: üçü CI'da koşuyor, yerelde yeşil, `scripts/workflow_policy_check.py` PASS.

**A2. Kapı dosyalarını hassas yol yap.** `.ai/policy.json` bugün yalnız `ai-quality.yml` ve
`ai_sdlc_check.py`'yi koruyor; `ci.yml`, `security.yml`, `release-candidate.yml`,
`.release/**`, `scripts/migration_check.py`, `scripts/workflow_policy_check.py` **korunmuyor** —
yani kapıyı zayıflatan bir commit dossier istemiyor. Bunları R2 olarak ekle (policy.json'un
kendisi de hassas; bu iş dossier ister).
Kabul: `ai_sdlc_check` bu dosyalardan birine dokunan dossier'siz commit'te UNCOVERED veriyor
(bir deneme commit'iyle göster, sonra düzelt).

**A3. `workflow_policy_check.py`'ye iki kontrol ekle:** (a) `continue-on-error: true` ve
`|| true` ile yutulan adımlar, (b) `permissions:` genişlemesi (`write` verilen scope'lar
listelenir, beklenen kümeyle karşılaştırılır). Testleriyle (`scripts/test_workflow_policy_check.py`).
Kabul: bilerek bozuk bir workflow parçasıyla kırmızı, mevcut dosyalarla yeşil.

**A4. E2E'de kusuru "atlama"ya çeviren 4 vaka.** `apps/web/e2e/flows.spec.ts:645,730,761,797`
`test.skip(havuz.taslaklar.length < 2, …)` — soru üretimi başarısız olunca test **kırmızı
değil sarı**. Sahte sağlayıcı artık soru üretiyor (test-report bunu yazıyor); skip gerekçesi
bayat. Skip'i kaldır; üretim başarısızsa test **düşsün**.
Kabul: `--workers=1` ile 4 vaka geçiyor; skip yok.

**A5. Bir şey kanıtlamayan testler.** Ölçülmüş dört örnek:
- `tests/test_guardrails.py:466-471` "yardımcının kendisi sınanır" diyor, yardımcının hiçbir
  kodunu çağırmıyor → gerçekten çağır.
- `tests/test_user_rights.py:481-497` yalnız `status_code == 200`; gövde boşalsa yeşil → içerik iddiası ekle.
- `tests/test_bake_model_materialize.py:67-73` metin sayımı tanım satırını da sayıyor → çağrı sayımını doğru ölç.
- `test_exam_workspace.py:490-493` ve benzeri: `pytest.raises(AssertionError)` içinde iki satır
  önce zaten çürütülen ifade → totoloji; gerçek mutasyon kur.
Kabul: her biri üretim kodu bilerek bozulunca kırmızı (mutasyon notu commit gövdesinde).

**A6. Ölü kod.** Ölçülmüş: `_RETRYABLE_EXCEPTIONS` (`llm.py:48`, kullanılmıyor, bir üyesi
litellm'de yok), `provider_config_digest()` (çağrılmıyor), `SocraticState.is_final_stage`
(okunmuyor), `pipeline.utcnow()` (ölü), `EvidenceVerdict.refusal_status` OUT_OF_SCOPE kolu
(hiçbir testte koşmuyor), `POST /sources/inspect` sunucu mantığı (`inspection.py:41-50`, tek test
mock'luyor). Her biri için: ya kullanan gerçek bir yol + test, ya da sil (docstring'ini de).
Kabul: `grep` ile sıfır çağrılı public sembol kalmıyor **veya** her biri için test var.

**A7. Sınav arayüzü 017 düzeltmeleri birim testsiz.** `components/exam/{running,finished}-exam.tsx`
ipucu limiti/boş küme/bayat sonuç mantığı yalnız koşulmamış Playwright'ta. `lib/exam.ts`'e
saf fonksiyon olarak çıkar, `bun test` ile sabitle.
Kabul: `bun test lib/` yeni testleri kapsıyor; tsc temiz.

### FAZ B — API'de var, arayüzde yok (danışman gereksinimleri)

Hepsi ölçüldü; her biri kullanıcıya söz verilmiş ama teslim edilmemiş yetenek.

**B1. Öğrenme çıktısı `topic_id`.** `LearningOutcomeCreate.topic_id` (`schemas/blueprint.py:27`)
arayüz hiç göndermiyor → her çıktı kalıcı olarak **"Konusuz"**, ekran bunun için uyarı çiziyor
ama kullanıcı düzeltemiyor. Blueprint sayfasındaki çıktı formuna konu seçici ekle.
Kabul: yeni çıktı konuyla kaydolur, yenilemede görünür, `topic_distribution` "Konusuz" göstermez.

**B2. Sınav başlatmada blueprint ve konu seçimi.** `ExamStartRequest.blueprint_id` ve
`topic_id` API'de var, `apps/web/lib/types.ts`'te **yok** → öğrenci web'den yalnız `{mode}`
gönderiyor; blueprint sınavına ve konuya göre çalışmaya arayüzden ulaşılamıyor.
Kabul: exam sayfasında yayınlanmış blueprint listesi + konu seçici; başlatılan oturum seçimi
kullanıyor (API yanıtında `blueprint_id`/`topic_id` görünür); E2E vakası.

**B3. "Neden yanlış?" açık uçlu ve kod sorularında.** MCQ/kısa cevapta çelişen kaynak var;
`open`/`code_trace`/`bug_hunt` tiplerinde yok, rubrik kırılımı kod tiplerinde üretilmiyor.
`grading.py` üzerinden kaynak bağlama + ekran gösterimi.
Kabul: her soru tipi için grading testi kaynak gösteriyor; `code_trace`/`bug_hunt` için **en az
bir puanlama testi** (bugün sıfır).

**B4. Sohbet oturumu silme (KVKK/FR-200).** `privacy.py:61` (tek oturum) ve `:81` (ders
geçmişi) uçları var; arayüzde yalnız "tüm geçmişi sil". Sohbet listesine onaylı tek-oturum
silme + ders ayarlarına ders-geçmişi silme ekle.
Kabul: doğru oturum kimliğine gider, başka oturum silinmez, API hatasında başarı gösterilmez.

**B5. AI politikası denetim geçmişi.** `GET /courses/{cid}/ai-policy/history` (`policy.py:151`)
hiçbir ekran okumuyor; kim-neyi-ne zaman verisi birikiyor. Ders ayarları sayfasına salt-okunur
geçmiş paneli.
Kabul: sayfa geçmişi listeler; `0020` sonrası ders silindiğinde yetim satır kalmadığı test edildi.

**B6. Feature flag tutarsızlığı.** `QUESTION_AUTHORING_ENABLED=false` iken (varsayılan) sınıflandırma
kontrolleri gizli ama blueprint sekmesi, hücre kurma, sürüm açma ve **"Yayımla"** düğmesi açık —
oysa yayınlama yapısal olarak imkânsız. Ya bayrak kapalıyken bu yüzeyleri dürüstçe gizle/kilitle
("Bu özellik bu ortamda kapalı" metniyle), ya da bayrağı kaldır. **Karar: gizle/kilitle.**
Kabul: bayrak kapalıyken ölü düğme yok; açıkken akış eskisi gibi.

**B7. Soru havuzu süzgeçleri sunucuya bağlansın.** `GET /questions?status=&topic_id=` var,
ekran yalnız yüklenmiş sayfayı süzüyor ve bunu itiraf eden bir not gösteriyor.
Kabul: süzgeç sunucuya gider, "yalnız yüklenenler" notu kalkar, sayfalama korunur.

### FAZ C — Retrieval: HNSW yolunu geri getir (`0021`, dossier)

**C1.** `dense.py` CTE'de yalnız saf operatörle sırala, eşitlik bozmayı dış sorguda ve
içerikten türeyen anahtarla (`documents.file_hash`) yap, `candidate_limit = limit × 8`
(`config.py` yeni alan `retrieval_dense_candidate_multiplier`), aynı işlemde
`SET LOCAL hnsw.iterative_scan = relaxed_order`. `MATERIALIZED` CTE'yi `EXPLAIN` ile ölç ve
hangisini seçtiğini raporla.
```sql
WITH nearest AS (
    SELECT c.id, c.document_id, c.chunk_index, c.page_number, c.slide_number,
           c.section_title, c.text, c.embedding_space,
           c.embedding <=> CAST(:query_vector AS vector) AS distance
    FROM chunks c
    WHERE c.course_id = :course_id
      AND (NOT CAST(:filter_documents AS boolean) OR c.document_id = ANY(CAST(:document_ids AS uuid[])))
      AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> CAST(:query_vector AS vector)   -- HNSW yalnız saf ifadeyi sıralar
    LIMIT :candidate_limit
)
SELECT n.id, n.document_id, d.file_name, n.page_number, n.slide_number,
       n.section_title, n.text, n.embedding_space, 1 - n.distance AS similarity
FROM nearest n JOIN documents d ON d.id = n.document_id
ORDER BY n.distance, d.file_hash, n.chunk_index
LIMIT :limit
```
**Neden:** HNSW **sıralama** işlecidir; `ORDER BY`'a indeksin bilmediği sütun eklemek ANN
yolunu iptal eder. `fts.py`'de aynı ekleme bedava (GIN süzme işleci). `documents.id` de
`gen_random_uuid()` → "içerikten türüyor" iddiası belgeler arası yanlış; `file_hash` doğru anahtar.
Ölçüm: ön-getirme 4× yetmedi, 8× yetti; `ef_search=40` ile `LIMIT 192` sessizce 62'de tükeniyor →
`iterative_scan` şart.
Kabul: (1) **yapısal test** `str(_SQL)` üzerinde (`test_fts.py:336` deseni); (2) davranışsal:
`limit=3`, 10 aynı metin, 2 belge, iki ingest **aynı sonuç**; (3) pencere testi: aday sayısı
`candidate_limit` kadar; (4) plan ölçümü A/B/C RLS'siz ve `SET ROLE dou_app` ile, medyan n≥7,
**gerçekçi korpus** (≥20k satır, farklı vektörler — tek vektörlü korpus yanlış sonuç verir);
(5) hibrit füzyona etki: fake holdout Recall@5/MRR önce/sonra.

**C2. `0021_hnsw_build_guard.sql`.** Ölçüldü: `maintenance_work_mem` taşarak kurulan indeks
(`NOTICE: hnsw graph no longer fits`) **varsayılan `ef_search=40` ile** top-8 recall %0 verdi,
`ef_search=100` ile düzeldi, 2 GB ile yeniden kurulunca varsayılanda %100. İddiayı bu üç
koşulla yaz (pgvector belgesi taşmayı "yavaşlama" diye anlatır, genelleme). Göç: bellek notu +
kurulum sonrası duman testi fonksiyonu. `0001`'e dokunma.
Kabul: fonksiyon var, testi var, `migration_check` PASS.

**C3.** `docs/test-report.md`'ye plan ölçümü bölümü; `dense.py` docstring'indeki "korpus
büyüyünce iterative_scan" notu güncellenir. Dossier: "ölçülmüş kusurun düzeltmesi" değil,
"ölçülmemiş kenar durumun sertleştirilmesi + ANN yolunun geri kazanılması" diye konumlandır
(test-report:291 dense kolunun etkilenmediğini yazıyor).

### FAZ D — Gözlemlenebilirlik ve operasyon (`0023`, dossier)

**D1. Paylaşılan kota deposu.** `core/rate_limit.py` `SlidingWindowLimiter` süreç belleğinde;
çok worker'da her süreç kendi penceresi. PostgreSQL'e taşı (`0023_shared_rate_limit.sql`:
`app.rate_limit_windows` + TTL) ya da `ai_token_reservations` üzerine birleştir — ölçerek seç.
Kabul: `uvicorn --workers 2`, limit L iken 2L istek → tam L kabul. `chat.py:121-148` testleri okunup uyarlanır.

**D2. Worker dayanıklılığı.** Üstel geri çekilme + jitter, N deneme, ölü-mektup, `SIGTERM`'de
güvenli bırakma. Eğitmen "yeniden çalıştır" ucu varsa doğrula, yoksa yaz.
Kabul: bilerek bozulan belge → N deneme → `failed` + ölü-mektup; SIGTERM testi.

**D3. Yedek/geri yükleme tatbikatı.** `scripts/backup.sh` (`pg_dump -Fc`) + `restore.sh`.
Tatbikat: dolu DB → yedek → boş DB → satır sayıları **ve bir dense arama sonucu** birebir aynı.
pgvector uzantısının restore hedefinde önce kurulması gerekebilir — kontrol et.
Kabul: `docs/runbook.md` §Yedek ölçümle; betikler CI'da kuru koşu.

**D4. OTel.** `opentelemetry-sdk` + FastAPI/SQLAlchemy/httpx enstrümantasyonu; exporter env
boşsa kapalı. Span'da prompt/cevap metni **yok** (KVKK). **Bağımlılık → §4.** Onay gelene kadar
tasarım + testleri hazırla, işi "engellendi" işaretle, D5'e geç.
**D5. Metrikler + `/internal/metrics`** (mevcut `internal.py` yetki deseni) + alarm kuralları
belgesi (`ops/alerts.yml`, `docs/runbook.md`; "uygulandı" deme).
**D6. Belge düzeltmeleri:** `ARCHITECTURE.md:535`, `docs/security.md:278-280` `/internal/drain`'i
"uygulanmadı" sayıyor (uç var, Compose'da kablolu); `ARCHITECTURE.md:422-425,542` "Compose'da
RLS devrede değil, superuser" diyor (yanlış, `dou_app` kullanılıyor).

### FAZ E — Gerçek model değerlendirmesi (`evaluation/**` R3, dossier + insan çıpası)

**E1. Sağlayıcı koşucusu.** `evaluate.py --provider groq --model <geçerli>` uçtan uca; sonuç
`results/<ts>-holdout-<provider>-<model>.json` `provider/model/prompt_revision` damgalı; yanıt
önbelleği `evaluation/cache/` (gitignore); kota dolarsa **kısmi sonuç**, "tamamlandı" deme.
**Groq anahtarı §4 — Murat'tan.** Anahtar gelene kadar koşucuyu fake sağlayıcıyla uçtan uca
test et, işi "engellendi: anahtar" işaretle.
**E2. Holdout koşusu** (anahtar gelince): faithfulness, citation precision, kapsam-dışı ret,
abstention, Sokratik sızıntı; ≥25 örnek `faithfulness/sample_template.md`.
**E3. Kabul paketi:** `prepare_packet.py --sample` ile bağla; iki etiketleyici kopyası; etiketler
**boş** kalır ("insan girdisi bekliyor").
**E4. Soru üretimi kalitesi** (biçim, cevap anahtarı tutarlılığı, çeldirici tekrarı) ve
**injection** seti gerçek modelle.
**E5. CI `eval-fake` işi** `ai-quality.yml`'e (`ci.yml`'e değil): fake + hashing holdout,
eşik `calibration.md`'den. Gerçek sağlayıcı CI'da koşmaz; `workflow_dispatch` şablonu.
**E6. Korpus kurulum güvenliği:** eval korpusu HNSW'yi yeterli `maintenance_work_mem` ile kurar +
duman testi. `EMBEDDING_PROVIDER=fastembed` şart (hashing korpusu E5 sorgusuna sessizce yanlış döner).
Kabul: `docs/test-report.md` yeni bölüm "Gerçek sağlayıcı koşusu — <tarih>" (n, CI, önbellek
isabeti, token). README'ye dokunma (Faz I).

### FAZ F — Gerçek Auth + private Storage (`0022`, dossier; sırlar §4)

**Önce ölç, sonra yap:** fail-closed kontroller **zaten var** ve lifespan'de değil `Settings`
doğrulayıcısında (`config.py:348-354, 365, 381-396, 412`): prod'da `DEV_AUTH_ENABLED` yasak,
dev-auth kapalıyken `SUPABASE_JWT_SECRET` zorunlu, sahte sağlayıcı prod'da yasak, eval runtime
prod'da yasak, `STORAGE_BACKEND=supabase` için URL+service_role zorunlu. `create_app()`
gerçekten `ValidationError` fırlatıyor (denendi). JWT algoritma listesi kapalı
(`jwt_algorithms=["HS256"]`, `security.py:59`), jetondan alınmıyor.

**F1. JWT negatif testleri** (sahte imza, süresi dolmuş, yanlış issuer/audience, `alg: none`,
imzasız → 401 + `error.code`) — varsa doğrula, eksikleri tamamla.
**F2. ES256/JWKS kararı → §4.** Supabase yeni projelerde asimetrik imzaya geçebilir; JWKS ile
doğrulayıcı secret bilmez. HS256 için secret; ES256 için issuer + anahtar kaynağı zorunluluğu
**ayrılmalı** — kabul koşulu değişir, Murat karar verir. Karar gelene kadar HS256 yolunu bitir.
**F3. Web oturumu:** Supabase Auth ile giriş/şifre sıfırlama/e-posta doğrulama/refresh, 401'de
tek yerden çıkış; `dev:` girişi yalnız `NEXT_PUBLIC_DEV_AUTH=true` iken. Dev yolunu **silme**.
**F4. Private Storage (`0022`):** `STORAGE_BACKEND=supabase`, imzalı URL, `storage.objects` RLS.
**KRİTİK — ölçüldü:** `ingestion/storage.py:97` `service_role` anahtarını `authorization`
başlığında taşıyor; Supabase Storage'da bu **RLS'i atlar**. Dolayısıyla "politika yazdık"
uygulamanın gerçek erişim yolunda kanıt değildir. Tasarım kararı: sunucu tarafı üyelik
kontrolü **asıl** yetki katmanıdır (bugün böyle); Storage RLS'i savunma-derinliği. Testler
ikisini **ayrı** sınar: API üyelik reddi ayrı; gerçek kullanıcı jetonuyla Storage
listeleme/indirme/silme reddi ayrı (service_role ile değil).
**F5. `supabase/tests/rls_storage.sql`** + mutasyon betiği: politika bozulunca kırmızı.
`psql -X -v ON_ERROR_STOP=1` ile koş; ekrana FAIL yazmak SQL hatası değildir.
**F6. Yerel Supabase yığınıyla E2E** (gerçek JWT). Gerçek proje: yalnız Murat anahtar verdiyse;
yoksa `not-run`.

### FAZ G — Deploy ve uçtan uca CI/CD (bulut hedefi §4)

**Bugün:** `ci.yml` (api, image, web, docs, e2e), `ai-quality.yml`, `security.yml`,
`release-candidate.yml` (kimlik-bağlı kabul, **deploy adımı yok**), `keepalive.yml`.
`.release/verify_checks.py` **görünen iş adlarını** tam sayar (`Workflow dependency policy`,
`CodeQL (javascript-typescript)`, `CodeQL (python)`); `Dependency review` yalnız PR'da, kabul
listesinde yok. **Keepalive'ın kırmızısı kasıtlı:** `KEEPALIVE_API_URL`/`KEEPALIVE_DATABASE_URL`
sırları yok → `KEEPALIVE_NOT_CONFIGURED`; "yeşil görünmesin" bilinçli karar. Düzeltme değil
karar: staging varsa sırları tanımla, yoksa `schedule`'ı kaldır, `workflow_dispatch` bırak,
eksik sırda hata vermeyi **koru** (`continue-on-error`/`exit 0` örtmedir).

**G1. İmaj → GHCR** (`ghcr.io/muratcan-ates/dou-synapse-api:<sha>`, SBOM, `type=gha` cache);
`--network none` duman testini koru. Action'lar **SHA ile pin'li**, `@v4` yazma.
**G2. `scripts/migrate.sh` + `test_migrate.sh`:** sıralı, `ON_ERROR_STOP`, `app.schema_migrations`
kaydı (`CREATE TABLE IF NOT EXISTS`, runner açar — **Murat onayı §4**), idempotent, kuru koşu;
temiz DB / N-1→N / ikinci koşum no-op.
**G3. `deploy-staging.yml`:** `workflow_run` (ci ok) + main; sır doğrulama (`DEV_AUTH_ENABLED`
staging'de false, değilse düş), migrate, deploy, `/health/ready` (**`/openapi.json` değil** —
yönetici kapısı 401), duman testi, başarısızlıkta önceki imaj. Hedef seçilmeden **iki sağlayıcı
şablonu** (`if: false` ile pasif).
**G4. `rollback-staging.yml`** + runbook "15 dk geri alma" + göç geri alma politikası.
**G5. Web:** `vercel.json` **veya** `apps/web/Dockerfile` (standalone); ikisi hazır, biri aktif.
**G6. `docs/deployment.md`:** branch protection, required check adları (release-candidate'in
beklediği tam adlar), environment reviewers — Murat GitHub UI'da yapar.

### FAZ H — Frontend olgunluğu: erişilebilirlik, ağ koruması, E2E

**H1. T307 turu:** her sayfa 375px + koyu + yalnız klavye; odak sırası/halkası, dialog
`aria-modal`/label/focus trap+return, canlı bölgeler, `aria-describedby`. `@axe-core/playwright`
→ **bağımlılık §4**; onaysız `package.json`'a dokunma, `getByRole` iddialarıyla ilerle.
`docs/accessibility.md`: yapılanı yaz, yapılmayanı "yapılmadı" bırak. Axe manuel incelemenin
yerine geçmez; ikisi ayrı kaydedilir.
**H2. T309 ağ koruması:** aktif sınavda asistan ucuna doğrudan istek → 4xx **gerçek sunucudan**
(`route.fulfill` ile sahte 403 kanıt değildir; `route.continue` + gerçek yanıt); kill-switch
(`COURSE_AGENT_ENABLED=false`) arayüz gizler **ve** API reddeder; sınav öncesi soru gövdesi ağda yok.
Yanlış kimlik/URL/gövdeden gelen herhangi bir 4xx "kilit çalışıyor" sayılmaz — sebebi `error.code`.
**H3. Güvenilirlik UX (T401–T406 kalanı):** süre bütçesi sözlüğü, `classifyError`, `Loading`
4 sn ikinci satır, `ErrorNote` yeniden dene — kodda eksik olanı yap, olanı test et.
**H4. Ekran görüntüleri** `EKRAN=1 … --grep @ekran` ile **seed verisiyle** (canlı DB'den değil);
`docs/images/` güncelle, README gömülerine dokunma (Faz I).
Kabul: `bun test lib/ && bunx tsc --noEmit && node scripts/contrast.mjs && bun run build` +
E2E `--workers=1` kararlı (paralelde LLM'e dokunan testler 409 verebilir).

### FAZ I — Belgeler, rapor, kılavuzlar (EN SON; sayaçlar burada ölçülür)

**I1. Yanlış iddialar** (ölçüldü): `ARCHITECTURE.md:34,533-535` var olan kapıları "uygulanmadı"
gösteriyor; `docs/security.md:288-296,309-316` §8 üç madde kodla ters (`allow_credentials`
`main.py`'de False); `docs/security.md:22,24,53,110,118,208,262,275,277,305` kod bağlantıları
yanlış satır/dosya; `docs/security.md:169-175` §3 listesi yanlış; `docs/runbook.md:143-147`
"27 tablo / 15 değilse eksik" çelişkisi; `runbook.md:155,191` + `PLAN.md:175` "sahte sağlayıcı
soru üretmiyor" (üretiyor, testi var); `runbook.md:236-241` Plan C'de LLM teşhisi sessiz;
`docs/completion-program.md:7,9` bir dal geride; `README.md:508-527` göç tablosu 0016/0018/0019/0020'yi
anlatmıyor; `specs/001-…/quickstart.md:99` göç sayısı cümlesi yanlış.
**I2. Kılavuzlar** ekran ekran bugünkü arayüzle: blueprint, AI politikası, AI kalite, kaynak
laboratuvarı, sınav kilidi, Ders Koçu, materyal sürümleme, açık uçlu rubrik, Profil→Verilerim.
Yeni: `docs/admin-guide.md` (danışman "yönetici kılavuzu" dedi).
**I3. Başarı testi raporu** jüriye sunulabilir: en üste özet tablo, bölüm başına
"ölçüldü/koşulmadı" + tarih, şerit jargonu ayıklanır.
**I4. Kutucuk eşitleme:** `specs/00[1-5]/tasks.md` ~45 kutucuk "açık" ama dosyası var. Her biri
için kod kanıtı → `[x]` + not, ya da "neden açık". Kapanan sayısını **say**.
**I5. Dossier numara çakışması:** `.ai/changes/` altında iki `010-*` (branded-api-docs +
dense-tiebreak). Eskiyi silme (append-only); `ai_sdlc_check.py`'ye "aynı sayısal önek iki kez
kullanılamaz" kontrolü + testi (`migration_check.py` deseni), mevcut çifti bilinçli istisna
olarak belgele.
**I6. `openapi.json` export** (uçlar değiştiyse) + kırık bağlantı taraması (`scripts/check_links.mjs`).
**I7. Sayaçlar:** web bağımlılıkları + `bunx playwright install chromium` kurulu → `node scripts/docs_check.mjs --duzelt`.
Rozet dili: `backend.tests` metriği **toplanan** testi sayar; "geçti" yalnız koşulmuş pytest'e
bağlanır. Tarihsel ölçümü silme; `scripts/docs_check.mjs` dosyasının başındaki "tarihsel"
işaret biçimiyle (değer + tarih) etiketle — biçimi oradan kopyala, kendi yazma.

---

## §4 — Murat'a sorulacaklar (dur, yaz, sıradakine geç)

| Ne | Hangi iş | Neden Codex karar veremez |
|---|---|---|
| Groq/Gemini anahtarı (`.env`'e / GitHub Secrets'a) | E1–E4 | sır |
| Supabase proje URL + anon/service_role/JWT secret | F3–F6 | sır |
| HS256 mi ES256/JWKS mi | F2 | kabul koşulunu değiştirir |
| Bulut hedefi (Azure Container Apps / Fly.io / Render) + Vercel | G3, G5 | hesap + maliyet |
| `app.schema_migrations` tablosunu runner'ın açması | G2 | şema kararı |
| Bağımlılık ekleme: `opentelemetry-sdk`, `@axe-core/playwright` | D4, H1 | manifest kilidi |
| GitHub branch protection / environment reviewers | G6 | UI'dan yapılır |
| Staging var mı → keepalive kararı | G | ortam |

Her madde için yazacağın format: **ne istiyorum · neden · alternatifim · beklerken ne yapıyorum.**

---

## §5 — Rapor biçimi (her push'ta PR açıklamasına)

```
[Faz X / İş N] <başlık>
Yapılan: <2-3 cümle, neden dahil>
Kapılar: pytest <n> · web <n> · tsc ✓ · ruff ✓ · mypy ✓ · docs_check ✓ · migration_check ✓ · ai_sdlc ✓
Not-run: <ne, neden>
Dossier: <NNN-…-r1> (varsa)
Engel: <§4 maddesi> (varsa)
```
Sayı yazıyorsan koştuğun komutun çıktısından. Yazamıyorsan "koşulmadı".
