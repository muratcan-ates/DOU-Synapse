# ŞERİT L2 — Ürün: jüri Gün-1 çekirdeği
**Dal:** `018-l2-product` · **Dossier aralığı:** 050–059 · **Göç:** `supabase/migrations/0027_learning_events.sql` (yalnız bu numara) · **PR başlığı:** `[L2] …`
**Yüzeyin:** `apps/web/app/**`, `apps/web/components/**`, `apps/web/lib/**`, `apps/web/e2e/**` (yeni vakalar), `apps/api/app/api/exams.py`, `apps/api/app/api/questions.py`, `apps/api/app/modules/assessment/**`, `apps/api/app/models/**`, `apps/api/app/schemas/**`, `apps/api/app/modules/agent/**` (429/fallback), `supabase/migrations/0027_*`, `supabase/tests/rls_learning_events.sql`, `apps/api/tests/**`.
**Dokunma:** `apps/api/app/modules/retrieval/**`, `rate_limit.py`, `request_quota.py`, `ingestion/**`, `.github/**`, `scripts/**` (test_quality hariç hiçbiri), `docs/**` (README sayaç hariç).

## ORTAK KURALLAR (her şerit için aynı — değiştirme)

**Depo:** `github.com/muratcan-ates/DOU-Synapse` (public). Entegrasyon dalı `018-codex-production-line` (PR #26 → 017). Sen kendi dalında çalışırsın.

```bash
git clone https://github.com/muratcan-ates/DOU-Synapse && cd DOU-Synapse
git fetch origin && git checkout 018-codex-production-line && git pull --ff-only
git checkout -b <DAL>            # şerit dosyasındaki dal adı; varsa: git checkout <DAL> && git pull --ff-only
cd apps/api && uv sync --extra dev --frozen && cd ../web && bun install && cd ../..
# PostgreSQL 16 + pgvector gerekir (docker compose up -d db). Yoksa DB isteyen kapılara "not-run" yaz.
```
Önce oku: `docs/team/codex/CODEX-RUNBOOK.md` (v2) §0 ve §2; kararların gerekçesi `docs/team/codex/40-BIRLESIK-PLAN.md`.

**Pazarlık edilmeyenler**
1. Ölçmediğini yazma. "Geçti/çalışıyor" yalnız koşturduğun komut çıktısıyla; koşamadıysan `not-run`. Sayı, SHA, dosya adı uydurma; var olmayan dosyayı `yeni dosya:` diye işaretle. Beklenen çıktı sayısı yazma, kontrol koşulu yaz.
2. Kaynak yoksa cevap yok (kanıt eşiği gevşetilmez). 3. İki katmanlı yetki: sunucu üyelik + PostgreSQL RLS. 4. Geçmiş göç dosyası değişmez; 0021–0023 boş kalır; yeni göç numaran şerit dosyasında.
5. `Co-Authored-By` asla. Kod/dosya adı İngilizce; yorum, UI metni, commit gövdesi Türkçe; conventional başlık; gövdede **neden**.
6. `.env` oluşturma, sır yazma (anahtar değeri hiçbir yere). 7. `DESIGN.md` tek tasarım otoritesi; ikon kütüphanesi yok; iki temada AA.
8. **Bağımlılık:** `pyproject.toml`, `uv.lock`, `package.json`, `bun.lock` **değiştirme** (lider onayı bekleniyor). Gerekiyorsa PR açıklamasına `ENGEL: bağımlılık <ad>` yaz, işi atla. SHA-pinli GitHub Action eklemek serbest (dossier ister).
9. **Başka şeridin yüzeyine dokunma** (şerit dosyasındaki "Dokunma" listesi). Ortak dosyaya (README, ci.yml) zorunlu dokunuşu en küçük tut ve PR açıklamasında belirt.
10. Sorma; §4 türü karar gerekirse `ENGEL:` yaz ve sıradaki işe geç.

**Kapılar — her commit'ten önce, hepsi yeşil**
```bash
KOK="$(git rev-parse --show-toplevel)"
cd "$KOK/apps/api" && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
TEST_DB_NAME=dou_<serit> .venv/bin/python -m pytest -q
cd "$KOK/apps/web" && bun test lib/ && bunx tsc --noEmit && node scripts/contrast.mjs
cd "$KOK" && node scripts/docs_check.mjs
python3 scripts/migration_check.py --allow-gap 0017 --allow-gap 0021 --allow-gap 0022 --allow-gap 0023
apps/api/.venv/bin/python scripts/workflow_policy_check.py
# commit SONRASI, temiz ağaçta (taban = ebeveyn commit; yalnız kendi dossier'in sınanır):
python3 scripts/ai_sdlc_check.py --base-sha "$(git rev-parse HEAD~1)" --head-sha "$(git rev-parse HEAD)"
```
Yeni test eklediysen belge sayaçları için `node scripts/docs_check.mjs --duzelt` (web bağımlılıkları + `bunx playwright install chromium` kuruluyken).

**Yönetişim (`.ai/`)** — `.ai/policy.json`'daki hassas yola (workflow'lar, `scripts/*check*`, `apps/api/app/modules/{assessment,retrieval,generation,guardrails,ingestion,agent,policy,mastery}/**`, `apps/api/app/api/{chat,policy,blueprints,exams,privacy,questions}.py`, `config.py`, `rate_limit.py`, `evaluation/**`, `apps/web/app/courses/**/chat/**`, `components/course-assistant/**` …) dokunan **her commit aynı commit'te** dossier + kanıt taşır:
`.ai/changes/<NNN>-<konu>-r1.json` + `.ai/evidence/<NNN>-<konu>-r1.json`; şablon `.ai/changes/example.json` ve `.ai/changes/037-codeql-hardening-r1.json`.
`NNN` = şerit dosyandaki **aralıktan** sırayla (başkasıyla çakışmasın diye). `base_sha` = üstüne inşa ettiğin commit'in tam SHA'sı, `candidate_sha: "SELF"`,
`artifacts[].sha256` = dosyanın gerçek özeti, `evidence[0].report_sha256` = kanıt dosyasının gerçek özeti, `status: "evidence-ready"`, kanıt `result: "pass"` yalnız koştuğun komutlarla.
`evaluation.calibration_ref/holdout_ref/human_anchor_ref` **gerçek dosya** olmalı. Kayıtlar append-only: var olanı düzenleme.
**`scripts/refresh_aggregate_dossier.py` KOŞTURMA** — toplayıcı kaydı entegrasyonda Claude yazar. PR'ında "Govern reviewed AI diff" bu yüzden kırmızı olabilir; **normaldir**.

**PR ve rapor** — Her iş bittiğinde commit + push; ilk push'ta `018-codex-production-line` hedefli **draft PR**, başlık `[<ŞERİT>] <iş>`. PR açıklamasına her push'ta:
```
[<ŞERİT> / İş N] <başlık>
Yapılan: <2-3 cümle, neden dahil>
Kapılar: pytest rc · bun rc · tsc rc · ruff rc · mypy rc · docs_check rc · migration_check rc · workflow_policy · ai_sdlc(ebeveyn) rc
Not-run: <ne, neden> · Dossier: <NNN> · ENGEL: <varsa>
```
İş 2 saati aşarsa böl. Dış sebeple (DB yok, kota) kırmızı kapı → `not-run` + sebep; işi bitmiş sayma.

## İŞLER (sırayla)

**B3'. `learning_events` + mini eğitmen özeti.** `yeni göç: supabase/migrations/0027_learning_events.sql`: tablo `learning_events(id uuid pk, occurred_at timestamptz, actor_pseudo_id uuid, course_id uuid, topic_id uuid null, session_id uuid null, event_type text, object_type text null, object_id text null, outcome_json jsonb null, evidence_chunk_ids uuid[] null, latency_ms int null, model_id text null, metadata_json jsonb null)` + indeksler (course_id, occurred_at) + **RLS**: öğrenci yalnız kendi `actor_pseudo_id`'sini, eğitmen kendi dersinin toplamını görür; `dou_worker` yazar. `actor_pseudo_id` gerçek kullanıcı kimliği **değil** (sunucu tarafı türetilmiş pseudo-id; e-posta/ad yok). Olay tipleri: `question_presented, answer_submitted, hint_requested, citation_opened, unsupported_refusal, provider_rate_limited`. Yazıcı: mevcut sınav/sohbet akışlarında (exams.py, agent) en az bu altı noktadan olay üret. Eğitmen özeti ucu `GET /courses/{cid}/learning-summary` (konu bazlı yanlış/ipucu/ret sayıları, son 7/30 gün) + ders ayarlarında salt-okunur panel; ham sohbet metni **yok**. `supabase/tests/rls_learning_events.sql` + mutasyon (`supabase/tests/rls_isolation_mutation_check.sh` deseni) — CI adımı L1'in yüzeyi → PR açıklamasına "L1: adım ekle" notu. "xAPI'ye eşlenebilir", xAPI değil.
Kabul: `migration_check` PASS; RLS betiği yeşil ve mutasyonda kırmızı; API testleri; `bun test lib/`; tsc; E2E: bir çalışma oturumu ≥4 olay üretir.

**B4'. 429 → etiketli fallback + kapsam dışı ret demosu.** Sağlayıcı adaptörüne test bayrağı (`LLM_FAKE_PROVIDER` benzeri, ayrı ad: `LLM_SIMULATE_RATE_LIMIT=1`) → ilk çağrı 429 + `Retry-After`; bir kontrollü tekrar; hâlâ başarısızsa UI'da **"Önceden kaydedilmiş demo yanıtı"** etiketli fixture (canlı yanıt gibi gösterilmez); sessiz model değişimi yok; kaynak kartları korunur; `provider_rate_limited` olayı yazılır. Kapsam dışı soruda LLM çağrısı **0** (mevcut ret yolu) — E2E ile kanıtla.
Kabul: E2E'de etiket görünür; API testi: 429 simülasyonunda fallback yanıtı `fixture: true` alanı taşır; kapsam dışı vakada sağlayıcı çağrı sayacı 0.

**B9. "Neden yanlış" kanıt kapısı doğrulaması.** Açık uçlu ve `code_trace`/`bug_hunt` cevabında **çelişen kaynak parçası + sonraki ipucu** gösterildiğini, kaynak yoksa açıklama üretilmeyip abstain edildiğini E2E ile doğrula; eksikse `grading.py` üzerinden tamamla. `code_trace`/`bug_hunt` için **deterministik oracle** (beklenen çıktı / AST / referans çalıştırma) testi ≥1; LLM yalnız açıklama.
Kabul: her soru tipi için grading testi; "kanıt yoksa açıklama yok" testi; E2E.

**Başla:** B3' (göç + RLS + yazıcılar) → B4' → B9.
