# DOU-Synapse — ajan çalışma sözleşmesi

## Otorite ve şeritler
- Depo: `github.com/muratcan-ates/DOU-Synapse`; entegrasyon dalı `018-codex-production-line`.
- Önce atanmış şerit talimatını, sonra `docs/team/codex/CODEX-RUNBOOK.md` §0–§4'ü oku.
- Karar gerekçeleri: `docs/team/codex/40-BIRLESIK-PLAN.md`; iş envanteri: `.ai/agent-queue.md`.
- Şerit talimatı eski runbook'un dal, sıra, numara, yüzey ve toplayıcı hükümlerini günceller.
- Dal adı, dossier aralığı, göç numarası, “Yüzeyin”, “Dokunma” ve “Başla” sırası şerit talimatından alınır.
- Şerit dalında çalış; `018-codex-production-line` hedefli draft PR aç. Entegrasyon/main dalına doğrudan yazma.
- Şeritler: L1 kapılar; L2 ürün; L3 deploy; L4 retrieval/operasyon; L5 auth/storage; L6 frontend/belge; L7 UX.
- Dosya sahipliği özeti `.ai/agent-queue.md` içindedir; özet başka şeridin yüzeyini açmaz.

## Pazarlık edilmeyen kurallar
1. Ölçmediğini yazma: geçti/çalışıyor yalnız çalıştırılan komut çıktısıyla; çalıştırılamayan `not-run` + neden.
2. Sayı, SHA, dosya adı uydurma; henüz olmayan çıktıyı `yeni dosya:` diye işaretle.
3. Beklenen çıktı sayısı yerine kontrol koşulu yaz; eski ölçümü yeni adayın kanıtı sayma.
4. Kaynak yoksa cevap yok; kanıt eşiği gevşetilmez.
5. Sunucu üyelik kontrolü ve aynı işlemde PostgreSQL RLS birlikte korunur; mutasyon kanıtı kırmızı yanabilmeli.
6. Geçmiş göç dosyası değişmez; 0021–0023 boş kalır. Yeni göç yalnız şeride ayrılan numarada.
7. Kod ve dosya adları İngilizce; yorum, UI metni ve commit gövdesi Türkçe; conventional başlık, gövdede neden.
8. `Co-Authored-By` hiçbir commit'e eklenmez.
9. `.env` oluşturma. Anahtar değerini hiçbir yere yazma; yalnız sır adlarını kullan.
10. `DESIGN.md` tek tasarım otoritesi; ikon kütüphanesi yok; açık/koyu temada AA.
11. `pyproject.toml`, `uv.lock`, `package.json`, `bun.lock` değişmez; bağımlılık gereğinde `ENGEL: bağımlılık <ad>`.
12. Tam 40 karakter SHA ile pinlenmiş GitHub Action eklemek serbesttir; hassas değişiklik dossier gerektirir.
13. Başka şeridin yüzeyine dokunma; README/ci.yml gibi ortak dosyada zorunlu değişikliği küçült ve PR'da belirt.
14. İnsan kararı gereken işi `ENGEL:` ile kaydet, sıradaki bağımsız işe geç; onay varsayma.
15. Runbook §4'teki bağımlılık, hesap, sır, kimlik, dış paylaşım ve ürün kararı engellerini aynı biçimde raporla.
16. İki saati aşan işi böl; dış nedenle koşulamayan kapı varsa işi DONE sayma.

## Kurulum
```bash
git clone https://github.com/muratcan-ates/DOU-Synapse
cd DOU-Synapse
git fetch origin
git checkout 018-codex-production-line
git pull --ff-only
# DAL değerini atanmış şerit talimatındaki gerçek dal adıyla belirle.
git checkout -b "$DAL"
# Dal zaten varsa: git checkout "$DAL" && git pull --ff-only
cd apps/api && uv sync --extra dev --frozen
cd ../web && bun install
cd ../..
# PostgreSQL 16 + pgvector: docker compose up -d db; yoksa DB kapıları not-run.
```
Testler `.env` istemez; yerel geliştirme gerektiğinde `DEV_AUTH_ENABLED=true EMBEDDING_PROVIDER=hashing`.
Kilit dosyası kurulurken değişirse commit'e alma; bağımlılık kararı gerektiriyorsa işi engelle.

## Dosya haritası
| Yol | Amaç |
|---|---|
| `apps/api/app/api/`, `modules/`, `core/` | API, ürün/RAG iş mantığı, yetki ve altyapı |
| `apps/api/tests/` | API, yetki, sağlayıcı, retrieval ve worker testleri |
| `apps/web/app/`, `components/`, `lib/` | Rotalar, arayüz ve web sözleşmeleri |
| `apps/web/e2e/`, `playwright.config.ts` | Gerçek tarayıcı kabulü ve izolasyonu |
| `supabase/migrations/`, `supabase/tests/` | Değişmez SQL göçleri, RLS ve negatif mutasyon kanıtı |
| `.github/workflows/`, `scripts/`, `.release/` | CI, kapılar, işletim ve release doğrulaması |
| `evaluation/` | Kalibrasyon/holdout, injection, ölçüm ve insan kabulü |
| `.ai/policy.json`, `.ai/changes/`, `.ai/evidence/` | Risk politikası, append-only dossier ve kanıt |
| `docs/`, `specs/`, `README.md`, `ARCHITECTURE.md` | Belgeler, kapsam, kabul ve güncel sayaçlar |

## Her işin döngüsü ve kapıları
Şerit sırasındaki READY işi al; bugünkü dosyaları oku; yalnız sahip olunan yüzeye uygula.
Aşağıdaki kapıları her commit öncesinde çalıştır; `SERIT` atanmış küçük harfli şerit kodudur (ör. `l1`).
```bash
KOK="$(git rev-parse --show-toplevel)"
cd "$KOK/apps/api" && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
TEST_DB_NAME="dou_${SERIT}" .venv/bin/python -m pytest -q
cd "$KOK/apps/web" && bun test lib/ && bunx tsc --noEmit && node scripts/contrast.mjs
cd "$KOK" && node scripts/docs_check.mjs
python3 scripts/migration_check.py --allow-gap 0017 --allow-gap 0021 --allow-gap 0022 --allow-gap 0023
apps/api/.venv/bin/python scripts/workflow_policy_check.py
```
Yeni testte sayaçlar: web bağımlılıkları ve Chromium hazırken `node scripts/docs_check.mjs --duzelt`.
Kusur bulduğunda önce onu yakalayan kapıyı güçlendir. Tüm sonuçları ve not-run nedenlerini kaydet.

## Hassas commit ve dossier
- `.ai/policy.json`'daki hassas yola dokunan her commit aynı commit'te kendi dossier ve kanıtını taşır.
- Yeni kayıtlar: `.ai/changes/<NNN>-<topic>-r1.json` ve `.ai/evidence/<NNN>-<topic>-r1.json`.
- Şablonlar: `.ai/changes/example.json`, `.ai/changes/037-codeql-hardening-r1.json`.
- NNN yalnız şeridin ayrılan aralığından sırayla; var olan kayıtlar append-only, düzenlenmez.
- `base_sha` üstüne inşa edilen commit'in tam SHA'sı; `candidate_sha: "SELF"`; `status: "evidence-ready"`.
- `artifacts[].sha256` ve `evidence[0].report_sha256` gerçek dosyalardan hesaplanır.
- `result: "pass"` yalnız çalıştırılmış başarılı komutlara dayanır; başarısız/koşulmamış sonuç örtülmez.
- `evaluation.calibration_ref`, `holdout_ref`, `human_anchor_ref` gerçekten var olan dosyalardır.
- Şeritler `scripts/refresh_aggregate_dossier.py` ÇALIŞTIRMAZ; toplayıcı yalnız entegratörün işidir.
- Toplayıcı nedeniyle PR'daki “Govern reviewed AI diff” kırmızı kalabilir; ebeveyn denetiminin yerini tutmaz.
- Commit sonrası temiz ağaçta kendi commit'ini doğrula:
```bash
python3 scripts/ai_sdlc_check.py --base-sha "$(git rev-parse HEAD~1)" --head-sha "$(git rev-parse HEAD)"
```

## Commit, push ve rapor
Her tamamlanan işte commit + push; ilk push'ta entegrasyon hedefli draft PR, başlık `[<ŞERİT>] <iş>`.
Her push'ta PR açıklamasına ilgili işin bu raporunu ekle/güncelle:
```text
[<ŞERİT> / İş N] <başlık>
Yapılan: <2-3 cümle, neden dahil>
Kapılar: pytest rc · bun rc · tsc rc · ruff rc · mypy rc · docs_check rc · migration_check rc · workflow_policy · ai_sdlc(ebeveyn) rc
Not-run: <ne, neden> · Dossier: <NNN> · ENGEL: <varsa>
```
Kuyruğu gerçek kanıtla güncelle; fake/hash ölçümü gerçek model kalitesi veya üretim hazır oluşu değildir.
