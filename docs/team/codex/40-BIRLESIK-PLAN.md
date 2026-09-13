# 40 — Birleşik Plan: karar günlüğü (13 Eylül 2026)

> Kaynak: 6 Gemini + 10 ChatGPT hakem raporu (yerel arşiv `v4-arastirma/sonuc/`, depoda değil), değerlendirme `sonuc/00-DEGERLENDIRME.md`,
> depo ölçümleri. Plana yalnız **iki kaynağın uyuştuğu ya da birincil kaynak/depo ölçümüyle kanıtlanan**
> maddeler girdi. Yürütülebilir kuyruk: `docs/team/codex/CODEX-RUNBOOK.md` (v2). Bu dosya "neden böyle karar verdik" kaydıdır.

## 1. Kesinleşen kararlar

| Alan | Karar | Kanıt | Reddedilen |
|---|---|---|---|
| Barındırma Gün-1 | Azure for Students, `Standard_B2s_v2` (2 vCPU / 8 GiB), Linux, Docker Compose | 20/23-chatgpt; fiyat ölçümüm: 70–77 USD/ay → 100 USD kredi ≈ 6 hafta | ACA/Cloud Run (resident worker için 360k GiB-s ≈ 12,5 sa/ay), Koyeb/Render/Fly (RAM/ücret), Oracle A1 kritik yol (kapasite + ARM) |
| Barındırma sonrası | Peak RSS ölçümünden sonra: int8 e5 (562 MB) → Arm `B2pls_v2` 4 GiB (~30 USD) **veya** Oracle A1 2/12 (0 USD) **veya** Hetzner CX33 (~10 USD) | 20/23/24-chatgpt | 8 GiB VM'i dönem boyu kullanmak |
| Veritabanı | Staging: **Supabase Free** (500 MB, 7 gün uyku, **PITR yok** → haftalık export + restore tatbikatı) | 23/22-chatgpt | Neon (ikinci sağlayıcı), VM içi Postgres (veri kaybı riski) |
| Web | Next.js `output: "standalone"` aynı VM'de; Vercel Hobby yalnız kişisel/ticari olmayan kapsam kanıtlanırsa | 20/23-chatgpt | Cloudflare OpenNext (replatform) |
| Göç runner | `yeni dosya: scripts/migrate.sh` (ON_ERROR_STOP, `app.schema_migrations`, advisory lock, dry-run) | 23-chatgpt | dbmate (dosyalara işaret ister; geçmiş 19 göç değişmez) |
| Deploy hattı | `yeni dosya: .github/workflows/deploy.yml` ayrı; `workflow_run` yalnız trusted `main` sonucu; OIDC federated credential; GHCR **digest** promotion; rollback = önceki digest | 20/23-chatgpt | Mevcut PR workflow'una iş eklemek (`verify_checks` sözleşmesi) |
| Keepalive | `schedule` kaldır, `workflow_dispatch` kalsın; sahte trafik yok | 23-chatgpt + 23-gemini | `continue-on-error` |
| Tedarik zinciri | Trivy + `actions/attest` + CycloneDX, hepsi **tam SHA pin**; 2026 Trivy olayı | 22/23-chatgpt | floating tag |
| B7 | İki aşamalı sorgu: iç `ORDER BY embedding <=> q LIMIT candidate` (yetki/RLS filtresi **içte**), dış `ORDER BY distance, file_hash, chunk_index`; kabul = `EXPLAIN` planında `Index Scan using chunks_embedding_idx` | depo ölçümü + 20/22/24-chatgpt | `hnsw.iterative_scan` tek başına (22-gemini) |
| B7 GUC | `strict_order` önce, `relaxed_order`/`ef_search` yalnız eval ile; `MATERIALIZED` gerekirse | 22/24-chatgpt | süre rakamını kabul ölçütü yapmak |
| Embedding | `multilingual-e5-large` korunur (fastembed kaydı 2,24 GB) | 24-chatgpt/gemini | bge-m3/jina-v3 göçü |
| Reranker | Yalnız deney: `jinaai/jina-reranker-v2-base-multilingual` (fastembed 0.8.0'da var; **CC-BY-NC-4.0**, 1,11 GB) | ölçüm + 24-chatgpt | `bge-reranker-v2-m3` fastembed'de yok (24-gemini) |
| Kota | PostgreSQL sabit pencere `date_bin` + koşullu `INSERT … ON CONFLICT DO UPDATE … WHERE`; rezervasyon audit; iki-worker testi; göç `0023` | 22-chatgpt (Gemini SQL'i hatalıydı: `clock_timestamp` pencere) | Redis, PgQueuer Gün-1 |
| RLS + havuz | `SET LOCAL` yalnız açık transaction içinde; Supavisor transaction modunda session `SET`/LISTEN yok | 22/23-chatgpt | session-level SET |
| LLM sağlayıcı | Groq `gpt-oss-120b` birincil (free: 30 RPM / 1.000 RPD / 8.000 TPM / **200.000 TPD**); yedek **Cerebras** aynı model (hesap gerek); Qwen Groq'ta üçüncü; **ZDR aç** | 20/24/25-chatgpt | Gemini free (veri ürün geliştirmede), yerel LLM (2 vCPU) |
| Eval | Gerçek sağlayıcı yalnız `workflow_dispatch`; PR'da promptfoo yerel Python provider (exit 100); gold set 30–50; insan etiketleme (kappa); Sokratik sızıntı kategorisi | 21/24-chatgpt | Ragas + Groq her PR'da (25-gemini) |
| Kimlik | HS256 Gün-1'de kalır (negatif testler); JWKS/asimetrik 2 haftaya; Supabase Auth + Entra **tenant kısıtı**; rol e-posta alan adından **değil**, enrollment tablosundan | 20/25-chatgpt | ES256'ya Gün-1 geçiş |
| Kalite kapıları | actionlint + zizmor; `git grep` ile `test.skip/fixme` yasağı; `shell: bash` (pipefail) tüm psql adımlarında; diff-cover **%85** (100 değil); mutmut 3.7 diff-wrapper **gecelik**; kanıt-betiği erişilebilirlik kontrolü `ai_sdlc_check`'e; `scripts/test_quality_check.py` (AST) | 21-chatgpt | eslint-plugin-playwright sırf skip için; `--fail-under=100` |
| Ajan bağlamı | `AGENTS.md` tek anayasa; `CLAUDE.md` = `@AGENTS.md`; `.ai/agent-queue.md`; `.cursorrules` yok | 21-chatgpt | Langfuse registry (canlı ortam yokken) |
| Lint | Gün-1 yok; hafta 1 ESLint 10 flat config (Next 16 `next lint` kaldırıldı) | 22-chatgpt | Biome (Playwright kuralı doğrulanmadı) |
| Gözlem | Tek platform, hafta 1; Logfire (EU bölgesi) aday; prompt/öğrenci metni span dışı | 22-chatgpt | Üç platformu birden |
| Ürün Gün-1 | B1 blueprint sınav girişi + konu seçici; B2 açık uçlu/kod "neden yanlış" (kanıt yoksa açıklama yok); `learning_events` (göç `0024`) + mini eğitmen özeti; 429 → **etiketli** fixture; kapsam dışı ret demosu | 25-chatgpt ×5 | LTI, FSRS, ses/video Gün-1 |
| Jüri | 10 dk senaryo: iki bilinçli başarısızlık (kanıt yok → sus; 429 → etiketli fallback); yalnız ölçülmüş sayı; "Verified Learning Loop" metriği | 25-chatgpt | "%94 faithfulness" gibi kurgu |
| Dış gerçekler | YÖK rehberi **7 May 2024** (araştırma/yayın kapsamı); TÜBİTAK 2209-A 12k / 2209-B 16k TL, **2026 çağrısı ilan edilmedi**; BiGG **1812**, 1,35M TL / %3 (30 Eyl 2026'ya kadar); KVKK aktarım: standart sözleşme vb., yalnız açık rıza değil; ZDR aktarımı ortadan kaldırmaz | 25-chatgpt ×5 | Gemini'nin 18 Nis / 900k / "Ekim çağrısı" |
| AI Act | Annex III 3(b) yönü; Art. 6(3) istisnası; yüksek-risk yükümlülükleri konsolide metinde **2 Ara 2027**; "sınav provası nota girmez" varsayımı belgeye yazılır; uyumluluk iddiası yok | 21-chatgpt | "compliant/certified" dili |
| Doğuş | OBS, DouOnline/DOUZEM, Perculus, M365, `öğrencino@dogus.edu.tr` doğrulandı; **LTI dış araç: bilinmiyor** (DOUZEM/BİM'e 3 soru) | 25-chatgpt ×5 | LTI'yi ürün vaadi yapmak |

## 2. Çelişkilerin çözümü (Gemini → ChatGPT)

Groq modeli/limitleri · Supabase Storage 1 GB/5 GB · Neon 100 CU-sa · Oracle 2/12 (tarih kanıtsız) · ACA grant doğru ama
resident için yetersiz · PyMuPDF AGPL → Docling MIT ama Docling **ertelendi** · mutmut 3.7.0 · CodeRabbit 1–8/sa, 150 dosya ·
Piston kapanmadı, anahtar ister · e5 2,24 GB FP32 / 562 MB int8 · PyLTI1p3 FastAPI'ye uymaz, ltitoolkit erken ·
Supabase yeni proje asimetrik anahtar (1 Eki 2025), "kesin ES256" doğrulanamadı.

## 3. Açık kalanlar (plana "doğrulanmadı" olarak girer)

e5-large + API + worker **peak RSS** (Gün-1'de ölçülür) · hedef Supabase projesinde `pg_extension` vector sürümü ·
Knip sürüm pini · Docling boyut/hız · Doğuş LTI ve Entra tenant · Groq hesabında ZDR'nin açık olduğunun kanıtı ·
Azure VM İstanbul RTT · İlk GHCR push süresi · EU AI Act kesin sınıflandırma (intended use'a bağlı).

## 4. Murat'tan kararlar (blokaj değil; Codex sıradakine geçer)

1. **Bağımlılık onayları:** `actionlint`, `zizmor`, `diff-cover` (+`pytest-cov`, ikisi de **kurulu değil**), `promptfoo` (npm),
   `mutmut`, `vulture`, `knip`, `@axe-core/playwright`, ESLint 10 (hafta 1), Logfire SDK (hafta 1). Öneri: ilk beşini onayla.
2. **Azure for Students** aktivasyonu + `B2s_v2` VM + OIDC için Entra app kaydı; **Supabase** projesi (URL, anon, service_role, JWT secret) →
   GitHub Secrets (değerler sohbete yazılmaz).
3. **Groq** konsolunda ZDR aç; **Cerebras** hesabı (yedek sağlayıcı).
4. **JWT:** HS256 Gün-1'de kalır (onay); JWKS 2 haftada.
5. **Sınav provası sonuçları hiçbir zaman nota/geçme-kalmaya girmez** (AI Act 6(3) varsayımı) — onay.
6. **DOUZEM/BİM'e üç soru:** LTI 1.3 dış araç kaydı var mı; kim yapıyor; test kiracısı/Moodle var mı. Entra tenant ID.
7. **Hetzner/Oracle** yedek planı için hesap açılsın mı (kredi bittiğinde).
