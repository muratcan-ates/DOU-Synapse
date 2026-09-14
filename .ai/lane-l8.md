# L8 — atanmamış iş şeridi (unassigned backlog lane)

Dal: `018-l8-unassigned` · Hedef: `018-codex-production-line` · Dossier aralığı: **120–129** · Göç: **yok**

## Neden bu şerit var

`.ai/agent-queue.md` L1–L7 şeritlerini sahiplendirir, ama altı işi açıkça **"atanmamış"**
bırakır: `E2`, `E3`, `E4`, `E6`, `D5'`, `H5` ve iki atlanan iş `A8'`, `A9`. Kuyruk bunlar
için "entegratör ataması olmadan başka şeridin yüzeyi alınmaz" der; bu şerit o atamayı
alır ve **yalnız** atanmamış işlerin, hiçbir L1–L7 dosyasına dokunmadan yapılabilen
kısmını üretir.

## Dossier numarası neden 120'den başlıyor

Bu şerit ilk kurulduğunda 110–119 aralığını aldı. Sonradan `018-l9-evaluation` şeridi
`110-test-quality-gate-r1` kaydını entegrasyon dalına yazdı; `scripts/ai_sdlc_check.py`
aynı sayısal öneki reddediyor (kuyruk işi `I5`). Çakışmayı önlemek için aralık
**120–129**'a taşındı. Rezervasyon bir ölçüm değil, bir sözleşmedir; ilk gelen alır.

## Yüzeyin

Yalnız **yeni dosyalar**. Var olan bir dosyayı değiştirmek, ancak ve ancak bu şeridin
bulduğu gerçek bir kusurun düzeltmesi olduğunda ve PR raporunda ayrıca belirtildiğinde
yapılır (AGENTS.md kuralı 13).

| Yol | Amaç |
|---|---|
| `apps/api/app/modules/assessment/quality.py` | E4 — MCQ tekrar/yanılgı ve rubrik ikinci doğrulayıcı mekanizması |
| `apps/api/app/modules/assessment/agreement.py` | E4 — QWK/Cohen kappa hesabı (eşik insan ölçümüne bırakılır) |
| `apps/api/tests/test_assessment_quality.py` | E4 kabulü (L2'nin `test_assessment.py` dosyasına dokunulmaz) |
| `apps/api/tests/test_rater_agreement.py` | E4 anlaşma istatistiği kabulü |
| `scripts/dead_code_check.py` + `scripts/test_dead_code_check.py` | A9 — `vulture`/`knip` yerine stdlib `ast` ile bağımlılıksız ölü kod kapısı |
| `scripts/unused_exports_check.mjs` | A9 — `knip` yerine bağımlılıksız TS/TSX kullanılmayan export kapısı |
| `scripts/diff_coverage_check.py` + testi | A8' — `pytest-cov`/`diff-cover` yerine stdlib ile değişen satır kapsamı |
| `evaluation/acceptance/packet_offline.py` + testi | E3 — gerçek sağlayıcı olmadan tekrar üretilebilir kabul paketi |
| `docs/l8-unassigned-report.md` | Ölçülen/koşulmayan sonuçların tek kaydı |

## Dokunma

- `apps/web/**` ürün kodu (L2/L6/L7), `apps/web/e2e/**` (L6), `playwright.config.ts` (L6).
- `.github/workflows/**` (L1/L3), `.release/**` (L1/L3), `Dockerfile`, `docker-compose.yml` (L3).
- `supabase/migrations/**` — bu şeride göç numarası **ayrılmadı**, yeni göç yazılmaz.
- `README.md`, `ARCHITECTURE.md`, `DESIGN.md`, `AGENTS.md`, `.ai/agent-queue.md` — ortak
  belgeler; L1/L6 sahibidir. Bu şerit yalnız kendi raporunu yazar.
- `pyproject.toml`, `uv.lock`, `package.json`, `bun.lock` — hiçbir koşulda.

## Bağımlılık duruşu

Bu şeridin varlık nedeni **yeni bağımlılık eklemeden** engellenmiş işin yapılabilir
kısmını üretmektir. `vulture`, `knip`, `pytest-cov`, `diff-cover`, `promptfoo`,
`@axe-core/playwright`, `ESLint 10`, Logfire SDK — hiçbiri kurulmaz. Yerlerine yalnız
Python 3.12 standart kütüphanesi (`ast`, `symtable`, `trace`, `sys.monitoring`) ve
Node'un yerleşik modülleri kullanılır.

## Hâlâ ENGEL olan ve bu şeritte yapılmayan

- `E2` — gerçek sağlayıcı e2e değerlendirmesi: Groq/Cerebras anahtarı ve ZDR kararı gerekir.
- `E3` gerçek koşusu — ≥25 gerçek örnek ve iki bağımsız insan etiketleyici gerekir.
  Bu şerit yalnız **çevrimdışı tekrar üretilebilir paket üretimini** ve skor hesabını yapar.
- `E4` eşiği — QWK eşiği insan-insan uyumundan türetilir; ölçüm yokken **eşik yazılmaz**,
  hesap mekanizması ve testi yazılır.
- `E6` — izole üç DSN, HNSW kurulumu ve gerçek bellek kanıtı gerekir.
- `D5'` — tek gözlem platformu / Logfire SDK kararı gerekir.
- `H5` — ESLint 10 bağımlılık onayı gerekir.

## Kapılar

AGENTS.md'deki ortak kapılar, `SERIT=l8` (`TEST_DB_NAME=dou_l8`). Yerel ortamda Docker
yok; PostgreSQL 16 Homebrew servisinden gelir. Koşulamayan her kapı rapora `not-run`
ve nedeniyle yazılır.
