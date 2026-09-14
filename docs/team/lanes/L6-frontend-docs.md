# ŞERİT L6 — Frontend kararlılığı, erişilebilirlik, belgeler, jüri
**Dal:** `018-l6-frontend-docs` · **Dossier aralığı:** 090–099 · **Göç:** yok · **PR başlığı:** `[L6] …`
**Yüzeyin:** `apps/web/e2e/**` (projects, fixtures, snapshot, ağ koruması), `apps/web/playwright.config.ts`, `apps/web/next.config.*` (yalnız CSP report-only), `docs/**` (L3'ün `deployment.md`/`runbook.md` ve L4'ün satırları hariç), `README.md`, `specs/**/tasks.md`, `docs/images/**`, `specs/001-course-assistant-mvp/contracts/openapi.json`, `scripts/check_links.mjs`.
**Dokunma:** `apps/api/**`, `apps/web/app|components|lib` (yalnız erişilebilirlik için `aria-*`/odak düzeltmeleri, DESIGN.md içinde), workflow'lar, `scripts/*check*`.

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

**I8. `yeni dosya: docs/jury-demo.md`.** 10 dakikalık senaryo (zaman damgalı): ders/konu seç → blueprint sınav → yanlış cevap → "neden yanlış" + kaynak → **bilinçli başarısızlık 1:** kaynakta olmayan soru → sus → **bilinçli başarısızlık 2:** 429 simülasyonu → etiketli fallback → eğitmen özeti → yol haritası. Ekranda yalnız **ölçülmüş** sayılar (boş şablon: `citation coverage __/__`, `abstention __/__`, `scope-leak __/__`, `fallback __/__`); "KVKK uyumlu / production-ready / LTI hazır" **denmez**; jüri soruları için 15 sn cevaplar (ChatGPT farkı, Khanmigo, Canvas/Moodle, LLM yanlışsa, KVKK, LTI neden yok, ölçek, kopya). Dış gerçekler: YÖK rehberi 7 May 2024 (araştırma/yayın kapsamı); TÜBİTAK 2209-A 12k / 2209-B 16k TL, 2026 çağrısı ilan edilmedi; BiGG 1812 1,35M TL / %3; AI Act: sınav provası nota girmez varsayımı + Art. 6(3) + yüksek-risk yükümlülükleri 2 Ara 2027.

**H1. Playwright izolasyonu.** LLM'e dokunan testler ayrı `project`; worker-scoped fixture ile benzersiz kullanıcı/oturum; global `--workers=1` **kaldır**; flaky karantina politikası (retry ≤1, issue+sahip+son tarih, gecelik hat; kalıcı skip yok) `docs/testing.md`'ye. Kabul: E2E `--workers=2` kararlı (3 ardışık koşu).

**H2. Görsel regresyon.** Kritik 5 ekran için `toHaveScreenshot()`; baseline aynı Linux CI imajında (yerel Mac baseline'ı commit'leme; CI'da üret). Argos/Chromatic yok.

**H4. Ağ koruması E2E.** Aktif sınavda asistan ucuna doğrudan istek → **gerçek sunucudan** 4xx (`route.fulfill` kanıt değil; `route.continue` + gerçek yanıt); kill-switch (`COURSE_AGENT_ENABLED=false`) UI gizler **ve** API reddeder; sınav öncesi soru gövdesi ağda yok. `error.code` doğrulanır.

**H3 (hazırlık).** `@axe-core/playwright` onay bekliyor → `ENGEL`. Onaysız yapılacak: manuel klavye/odak turu protokolü `docs/accessibility.md` (375px + koyu + yalnız klavye; her sayfa için bulgular tablosu; yapılmayanı "yapılmadı" bırak); `getByRole` iddialarıyla odak/`aria-*` E2E vakaları.

**H6.** CSP `report-only` başlığı (nonce yok; dinamik rota etkisi belgelenir). **H7.** Ekran görüntüleri seed verisiyle (`EKRAN=1 … --grep @ekran`), `docs/images/` güncelle.

**I1. Yanlış iddialar.** `ARCHITECTURE.md:34,533-534` (var olan CI kapıları "uygulanmadı"); `docs/security.md:288-296,309-316` (§8 kodla ters; `allow_credentials` `main.py`'de False); `docs/security.md:22,24,53,110,118,208,262,275,277,305` bağlantılar; `:169-175` §3; `docs/runbook.md:143-147` (27/15 çelişkisi), `:155,191` + `PLAN.md:175` ("sahte sağlayıcı soru üretmiyor" — üretiyor); `docs/completion-program.md:7,9`; `README.md:508-527` göç tablosu (0024–0027); `specs/001-…/quickstart.md:99`. Her düzeltme kod okunarak.

**I3.** `docs/test-report.md`: en üste özet tablo; her bölüm "ölçüldü/koşulmadı" + tarih; şerit jargonu ayıklanır; gerçek sağlayıcı bölümü yalnız koşulduysa. **I4.** `specs/00[1-5]/tasks.md` ~45 kutucuk: kod kanıtı → `[x]` + not, ya da "neden açık"; sayısını yaz. **I6.** OpenAPI export (uçlar değiştiyse) + `scripts/check_links.mjs` kırık bağlantı. **I7.** Sayaçlar `docs_check --duzelt` (web deps + Playwright kurulu). **I2.** Kılavuzlar: Codex'in güncellediği öğrenci/eğitmen/BİM kılavuzlarını bugünkü arayüzle ekran ekran doğrula; eksikleri tamamla.

**Başla:** I8 → H1 → H4 → I1 → I3 → H2 → H3(belge) → I4 → I6 → I7 → H6 → H7 → I2.
