# AGENTS.md — DOU-Synapse ajan sözleşmesi

Depoda çalışan her ajan oturumunun tek giriş noktası. Anlatım değil, bağlayıcı kural listesidir.
Kaynaklar: `docs/team/codex/CODEX-RUNBOOK.md` §0, `.specify/memory/constitution.md`,
`docs/team/parallel/00_OKU_ONCE.md`, `.ai/README.md`. Sıradaki iş: `.ai/agent-queue.md`.
Frontend'e dokunuyorsan ayrıca `apps/web/AGENTS.md` (Next.js sürüm uyarısı).

## 1. Taban

- Depo `github.com/muratcan-ates/DOU-Synapse`; ürün ucu dalı `017-completion-integration`. Kendi dalını açma.
- `.env` yok ve olmayacak. Testler `.env` istemez: `DEV_AUTH_ENABLED=true EMBEDDING_PROVIDER=hashing`.
- PostgreSQL 16 + pgvector gerekir (`docker compose up -d db`). Yoksa DB kapıları `not-run`.
- Kurulum: `cd apps/api && uv sync --extra dev --frozen`, sonra `cd apps/web && bun install`.
- Her oturum kendi `git worktree` klasöründe ve kendi `TEST_DB_NAME` değeriyle koşar; paylaşılan
  veritabanında eşzamanlı `pytest` koşumları birbirini siler (9 Ağu 2026'da fiilen yaşandı).

## 2. Pazarlık edilmeyen kurallar

1. **Ölçmediğini yazma.** "Geçti/çalışıyor/kanıtlandı" yalnız koşturduğun komutun çıktısıyla söylenir;
   koşamadıysan `not-run` + sebep. Sayı, SHA, dosya adı uydurma. Beklenen çıktı sayısı değil kontrol
   koşulu yaz (`rc=0`; plan `Index Scan using chunks_embedding_idx` içerir). (Anayasa III)
2. **Kaynak yoksa cevap yok.** Atıf `chunk_id` set-üyelik kontrolünden geçer; dosya adı ve sayfa
   chunk metadata'sından gelir, model metninden değil. Kanıt eşiği altındaki sorgu LLM'e gitmeden
   ret döner; eşiği gevşetme. (Anayasa I)
3. **İki katmanlı izolasyon.** İstemciden gelen `course_id` asla yetki değildir; kendi üyelik sorgunu
   yazma, `CourseMemberDep` / `CourseInstructorDep` kullan. Aynı işlemde PostgreSQL RLS de vardır ve
   mutasyon betikleriyle kırmızı yanabilmelidir. Testler `dou_app` rolüyle koşar; superuser'a geçirme,
   RLS sessizce atlanır ve test hiçbir şey kanıtlamaz. (Anayasa II)
4. **Fail-closed.** Belirsizlikte kapan: oturum bağlamı yoksa RLS satır göstermez, kanıt eşiği
   aşılamazsa abstention, embedding üretilemezse belge `completed` işaretlenmez. `DEV_AUTH` üretimde
   açılamaz. (Anayasa IV)
5. **Göçler.** Düz SQL, dosya adı sırası; geçmiş göç yerinde değişmez (dbmate yok). `0021`–`0023`
   bilerek boş kalır, `0024`–`0026` kullanıldı; yeni göç sıradaki boş numaradan açılır ve önce
   `supabase/migrations` listelenerek doğrulanır. Kapı: `scripts/migration_check.py` (§5'teki bayraklarla).
6. **Yönetişim (`.ai/`).** `.ai/policy.json`'daki hassas yola dokunan commit, aynı commit'te dossier
   (`.ai/changes/`) + kanıt (`.ai/evidence/`) taşır. Kayıtlar append-only: düzeltme yeni kayıttır,
   eskisi yeniden yazılmaz. Dossier numarası = mevcut en büyük + 1 (`ls .ai/changes` ile bak, sayı
   ezberleme). `base_sha` = ebeveyn commit, `candidate_sha: "SELF"`. **Her push'tan önce**
   `apps/api/.venv/bin/python scripts/refresh_aggregate_dossier.py --target origin/017-completion-integration`
   → `WROTE` ise toplayıcıyı push'lanacak son commit'e ekle; atlanırsa PR'daki "Govern reviewed AI diff" kırmızı yanar.
7. **Dil.** Kod, değişken ve fonksiyon adları İngilizce; yorum, docstring, UI metni, hata mesajı ve
   commit gövdesi Türkçe. Türkçe metinde `.upper()` / `toUpperCase()` / `text-transform: uppercase`
   yasak (i/İ bozulur) — `apps/api/app/core/text_tr.py` yardımcılarını kullan. UI metninde em dash yok.
8. **Git disiplini.** Conventional commit başlığı; gövde "ne"yi değil "neden"i anlatır.
   `Co-Authored-By` ve "Generated with" izleri **asla** yazılmaz. Commit öncesi sızıntı taraması.
9. **Bağımlılık eklenmez.** `pyproject.toml` / `package.json` / `uv.lock` / `bun.lock` onaysız
   değişmez. Gerekiyorsa ekleme; gerekçe + alternatif yaz, işi bağımlılıksız bitir, `.ai/agent-queue.md`
   B-kodu sütununa ⛔ koy ve raporunda bildir.
10. **Sır yazılmaz.** Anahtar değeri hiçbir dosyaya, log'a veya span'a girmez; yalnız GitHub
    Secrets / OIDC **adları** yazılır. Log ve kanıtta öğrenci içeriği bulunmaz.
11. **Tasarım.** Tek kaynak `DESIGN.md`; bileşende ham hex yok, ikon kütüphanesi yok, iki temada AA
    kontrast. Durum renk + metin ile işaretlenir; renk tek başına bilgi taşımaz. (Anayasa VII)
12. **Modülerlik.** Aynı davranış üçüncü kez yazılıyorsa ortak modüle çıkar. Etkin görünüp iş yapmayan
    buton/uç kusurdur; ölü kod, ölü export ve ulaşılamayan dal commit'te temizlenir. (Anayasa XI)
13. **Sahiplik.** Yalnız şeridine verilen dosyaları değiştir. Başka dosya gerekiyorsa değiştirme:
    gerekli diff'i handoff notuna yaz ve raporunda bildir. `apps/api/app/contracts.py` tek taraflı
    değişmez — ona karşı yazılmış modülleri aynı anda kırar.

## 3. Dosya haritası

```
apps/api/app/api/          HTTP uçları: chat, exams, questions, blueprints, policy, privacy, admin,
                           courses, documents, sources, dashboard, analytics, feedback, health, internal
apps/api/app/core/         config, db, errors, security, rate_limit, request_quota, text_tr,
                           vector_space, llm_json, logging, warmup, readiness, provider_config
apps/api/app/models/       SQLAlchemy modelleri      apps/api/app/schemas/  Pydantic şemaları
apps/api/app/modules/      agent · assessment · chat · generation · guardrails · ingestion ·
                           mastery · policy · retrieval
apps/api/app/contracts.py  modüller arası tipler (Retriever, Generator, Guardrail, ...) — dokunulmaz
apps/api/app/main.py       uygulama kurulumu        apps/api/app/worker.py  arka plan işçisi
apps/api/tests/            pytest suiti; conftest.py `dou_app` rolüyle bağlanır
apps/web/app/              Next.js App Router ekranları (courses, admin, dashboard, account, profile, kvkk)
apps/web/components/       arayüz bileşenleri       apps/web/lib/  istemci mantığı + `*.test.ts` birim testleri
apps/web/e2e/              Playwright               apps/web/scripts/contrast.mjs  kontrast kapısı
supabase/migrations/       düz SQL göçler           supabase/tests/  RLS testleri + mutasyon betikleri
.ai/                       policy.json · schema.json · changes/ (dossier) · evidence/ · quarantine/
.ai/agent-queue.md         kalan iş kuyruğu — sıradaki işi buradan al
.github/workflows/         ci · security · ai-quality · release-candidate · agent-skills · keepalive
scripts/                   kapı betikleri: docs_check.mjs · ai_sdlc_check.py · migration_check.py ·
                           workflow_policy_check.py · refresh_aggregate_dossier.py · recovery.py
.release/                  sürüm kanıtı: verify_checks.py · validate_evidence.py · evidence.schema.json
evaluation/                gold_set · faithfulness · injection · acceptance · calibration.md  (R3)
specs/                     şartname ve görev defterleri   docs/  ürün, güvenlik ve operasyon belgeleri
.specify/memory/constitution.md   anayasa   DESIGN.md   ARCHITECTURE.md   PLAN.md   README.md
```

## 4. Döngü

1. `.ai/agent-queue.md`'den sıradaki READY işi al. 2. Dosyaların bugünkü hâlini `git grep` ile oku.
3. Uygula; yalnız o işin dosyaları. 4. Kapıları koştur (§5); kusur bulursan önce onu geçiren kapıyı
güçlendir. 5. Hassas yol → dossier; push'tan önce toplayıcı. 6. Türkçe commit + rapor. 7. Sıradaki iş.
İş iki saati aşarsa böl. Dış sebeple kırmızı kapı → `not-run` + sebep; iş bitmiş sayılmaz.

## 5. Kapılar — her commit'ten önce

```bash
KOK="$(git rev-parse --show-toplevel)"
cd "$KOK/apps/api" && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
TEST_DB_NAME=dou_codex .venv/bin/python -m pytest -q
cd "$KOK/apps/web" && bun test lib/ && bunx tsc --noEmit && node scripts/contrast.mjs
cd "$KOK" && node scripts/docs_check.mjs
python3 scripts/migration_check.py --allow-gap 0017 --allow-gap 0021 --allow-gap 0022 --allow-gap 0023
apps/api/.venv/bin/python scripts/workflow_policy_check.py
python3 scripts/ai_sdlc_check.py --base-sha "$(git merge-base origin/017-completion-integration HEAD)" --head-sha "$(git rev-parse HEAD)"   # commit sonrası, temiz ağaç
```

`TEST_DB_NAME=dou_codex` tek oturum içindir: paralel şeritlerde her oturum kendi adını verir.
`macOS`'ta önce `export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"` (Postgres 16 keg-only).
Python 3.12 pinlidir (onnxruntime/fastembed 3.13+ desteklemiyor).
