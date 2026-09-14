# Murat — 3 gün, sırayla yapılacaklar (13–16 Eylül 2026)

**Kural:** anahtar/şifre **değeri** hiçbir sohbete (ChatGPT, Codex, Claude) yazılmaz. Değerler yalnız iki yere gider:
yerel `apps/api/.env` (bugün Groq anahtarının durduğu dosya, gitignore'da) ve GitHub → repo → Settings → Secrets and variables → Actions.
Sohbetlere yalnız **adı** yazılır ("SUPABASE_URL eklendi").

**Durum:** PR #26 (`018-codex-production-line` → 017) 13 check'in 13'ü yeşil. Kalan iş kuyruğu `docs/team/codex/CODEX-RUNBOOK.md` v2 §3.
İş bölümü: **sen** hesap/anahtar/onay + ChatGPT/Codex sohbetlerini sürersin; **ben** burada kontrol: lane PR'larını denetler, birleştirir, toplayıcı dossier'i yazar, 018 → 017 → main akışını götürürüm.

---

## 1. ŞİMDİ — evden çıkmadan, telefondan (15 dk)

1. **Codex sohbetine cevap ver:** 9 Eylül'de sordu: "S9/S10 kodu + sentetik kanıt arşivi herkese açık depoya gönderilsin mi?"
   Cevap yaz: **"Evet, paylaşılabilir; sentetik veridir."** (Hayır dersen o dilim kapalı kalır.)
2. **GitHub → Security → Dependabot alerts:** main'de **2 kritik** uyarı var. Paket adlarını bana yaz (değer/anahtar değil, paket adı).
3. **Bağımlılık onayı** (bana tek mesaj): `actionlint, zizmor, pytest-cov, diff-cover, promptfoo (npm), mutmut, vulture, knip, @axe-core/playwright, ESLint 10, Logfire SDK`.
   Önerim: hepsine **evet**, Logfire hafta 1.
4. **Kararları onayla** (tek satır yeter): Azure Students `B2s_v2` 8 GiB VM · Supabase Free · HS256 Gün-1'de kalır, JWKS sonra ·
   "sınav provası nota girmez" · LTI vaat edilmez · reranker yalnız deney · gerçek eval yalnız `workflow_dispatch`.

## 2. HESAPLAR VE ANAHTARLAR — laptop (1,5–2 saat, bugün)

### A. Supabase (supabase.com) — Faz F, staging DB
- New project → **Free**, bölge **Frankfurt (eu-central-1)**, güçlü DB şifresi (şifre yöneticisine).
- Project Settings → **API**: `SUPABASE_URL` (Secrets + `.env` + web'de `NEXT_PUBLIC_SUPABASE_URL`), **anon** key → `NEXT_PUBLIC_SUPABASE_ANON_KEY` (Variables), **service_role** → `SUPABASE_SERVICE_ROLE_KEY` (Secrets, asla web'e).
- Project Settings → **JWT Keys**: legacy **JWT secret** varsa → `SUPABASE_JWT_SECRET`; yalnız asimetrik anahtar (ES256) görünüyorsa **bana yaz** ("yeni proje JWKS") — F2 kararı buna bağlı. `SUPABASE_JWT_ISSUER` = `https://<proje-ref>.supabase.co/auth/v1`.
- **Connect → Direct connection** (port 5432, Supavisor değil) → `DATABASE_URL` ve `WORKER_DATABASE_URL` (aynı host; roller `dou_app`/`dou_worker` göç adımında oluşturulur).
- **Storage** → New bucket `course-materials`, **Private** → `SUPABASE_STORAGE_BUCKET=course-materials`; `STORAGE_BACKEND=supabase` (staging'de).
- Authentication → Providers → **Azure (Microsoft)**: Entra app ile (D adımı) — 2. gün.

### B. Groq (console.groq.com)
- Settings → **Data Controls → Zero Data Retention: aç** (ekran görüntüsünü kanıt klasörüne).
- Mevcut anahtar `.env`'de kalır. GitHub Secrets'a **ayrı** bir anahtar: `EVAL_LLM_API_KEY` (+ Variable `EVAL_LLM_PROVIDER=groq`) — yalnız `workflow_dispatch` gerçek eval için. Staging için `GROQ_API_KEY` Secrets'a.

### C. Cerebras (cloud.cerebras.ai) — yedek sağlayıcı
- Hesap aç, API key → Secrets `CEREBRAS_API_KEY` ve `.env`. (Kodda `cerebras/` router'ı E2 işinde eklenecek.)

### D. Azure for Students (azure.microsoft.com/free/students) — Faz G
1. Okul e-postasıyla aktive et → **Subscription ID** not al.
2. **Microsoft Entra ID → App registrations → New**: `dou-synapse-deploy` → **Certificates & secrets → Federated credentials → GitHub Actions**:
   repo `muratcan-ates/DOU-Synapse`, entity **Branch** `main` (ve **Environment** `staging`) → `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` → GitHub Secrets. Parola/istemci sırrı **oluşturma** (OIDC yeter).
3. Resource group `dou-synapse-rg` (Germany West Central ya da West Europe) → VM **`Standard_B2s_v2`**, Ubuntu 24.04 LTS, SSH anahtarı (yeni üret, özel anahtar → Secrets `STAGING_SSH_KEY`, kullanıcı `azureuser`), port 22/80/443. Adı `dou-synapse-staging`. Public IP'yi bana yaz (sır değil).
4. App registration'a RG üzerinde **Contributor** rolü; **Cost Management → Budget** 80 USD uyarı (kredi ~6 hafta).
5. Çalışmadığı saatlerde VM'i **deallocate** et (kredi kurtarır).

### E. GitHub (repo Settings)
- **Secrets** (değer gir, adı bana yaz): `SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, DATABASE_URL, WORKER_DATABASE_URL, GROQ_API_KEY, EVAL_LLM_API_KEY, CEREBRAS_API_KEY, AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, STAGING_SSH_KEY`; staging canlı olunca `KEEPALIVE_API_URL, KEEPALIVE_DATABASE_URL`.
- **Variables**: `NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL, EVAL_LLM_PROVIDER=groq`.
- **Environments → `staging`**: required reviewer = sen.
- **Branches → main protection**: PR zorunlu, required checks: `API — lint, tip, test`, `Web — lint, tip`, `Belgeler — canlı sayı kapısı`, `API imajı — build + ağsız embedding kanıtı`, `Uçtan uca — gerçek API + tarayıcı`, `Govern reviewed AI diff`, `Verify gold-set integrity`, `Workflow dependency policy`, `CodeQL (python)`, `CodeQL (javascript-typescript)`; **"Allow squash/rebase" kapat** (yalnız merge commit).
- Copilot planın var mı bak (Settings → Copilot); yoksa CodeRabbit OSS yeterli (isteğe bağlı).

### F. DOUZEM / Bilgi İşlem'e e-posta (5 dk, cevabı 2 hafta)
> Merhaba, COME 491/492 bitirme projemiz DOU-Synapse için üç sorumuz var: (1) DouOnline/LMS'imize LTI 1.3 Advantage dış araç
> kaydı yapılabiliyor mu, yapılıyorsa kim yapıyor? (2) Test amaçlı bir Moodle/LMS kiracısı var mı? (3) Kurumsal Microsoft Entra
> tenant kimliğini ve öğrenci hesaplarıyla OAuth uygulama kaydı politikasını öğrenebilir miyiz? Teşekkürler.

### G. Yerel hijyen (bana bırak, sen onayla)
- `~/Documents/ChatGPT/DOU-Synapse/readme-final` ve `~/Documents/Codex/2026-08-09/…` **iCloud altında worktree** (anayasa §7/3'e aykırı).
  "Kaldır" dersen `git worktree remove` ile temizlerim; dallar kalır.

---

## 3. PARALEL SOHBETLER — şerit planı (ChatGPT/Codex)

Her sohbet **kendi dalında** çalışır; dosya yüzeyleri çakışmaz; **toplayıcı dossier yazmaz** (onu ben yazarım); PR hedefi `018-codex-production-line`.
Lane PR'ında "Govern reviewed AI diff" kırmızı olabilir — **normal**, entegrasyonda kapanır. Dossier numaraları çakışmasın diye aralık verildi.

| Şerit | Dal | Runbook v2 işleri | Dossier | Göç | Anahtar gerekir mi |
|---|---|---|---|---|---|
| **L1 Kapılar + eval kablosu** | `018-l1-gates` | A0, A3', A4', A5', A6', A8', A9, E1, E5 | 040–049 | — | Hayır (bağımlılık onayı §1/3) |
| **L2 Ürün** | `018-l2-product` | B3' (learning_events), B4', B9 | 050–059 | **0027** | Hayır |
| **L3 Deploy** | `018-l3-deploy` | G1, G2, G3 (`if: false` ile başla), G4, G5, G6, D4' | 060–069 | — | Azure/Supabase (2. gün) |
| **L4 Retrieval + ops** | `018-l4-retrieval-ops` | C1-FTS, C2, C3, C4, D1', D2', D3', D6' | 070–079 | **0028** | Hayır |
| **L5 Kimlik + Storage** | `018-l5-auth` | F1 (anahtarsız), F2–F6 | 080–089 | **0029** | Supabase (2. gün) |
| **L6 Frontend + belgeler** | `018-l6-frontend-docs` | H1–H7, I1–I8 | 090–099 | — | Hayır |
| **E2/E3 gerçek eval** | ben, `workflow_dispatch` | — | — | — | `EVAL_LLM_API_KEY` |

**Her lane sohbetine ilk mesaj (şablonu doldur):**
```
Depo: muratcan-ates/DOU-Synapse. `git checkout 018-codex-production-line && git pull --ff-only && git checkout -b <DAL>`.
Önce docs/team/codex/CODEX-RUNBOOK.md (v2) §0 kurallar + §2 döngü + §3'ten YALNIZ şu işler: <İŞLER>. Başka işe dokunma.
Yönetişim: hassas yola dokunan her commit kendi dossier'ini taşır (numara aralığın <ARALIK>, base_sha = ebeveyn commit, candidate SELF);
refresh_aggregate_dossier.py KOŞTURMA (entegrasyonda yazılır). Göç gerekiyorsa numaran <GÖÇ>. Bağımlılık yalnız onaylı liste: <LİSTE>.
Her commit'ten önce §0 kapıları; ölçmediğini yazma, koşamadığına not-run. Co-Authored-By yok, .env yok, sır yok.
Bitirdiğin her işte push + `018-codex-production-line` hedefli draft PR (başlık "[L?] …"); PR açıklamasına §5 raporu.
Sorun/karar gerekirse PR açıklamasına "ENGEL:" yaz ve sıradaki işe geç.
```

**Bana her gün gönder:** PR numaraları, eklediğin Secret **adları**, onayladığın kararlar, DOUZEM cevabı geldiyse.

---

## 4. ÜÇ GÜN

| Gün | Sen | Ben (kontrol) |
|---|---|---|
| **1 — bugün** | §1 (15 dk) · §2 A–E (Supabase, Groq ZDR, Cerebras, Azure, Secrets) · L1, L2, L4, L6 sohbetlerini başlat | Lane PR'larını denetle/birleştir; 037/038 sonrası toplayıcı; PR #26'yı 017'ye birleştirmeye hazırla; Documents worktree'lerini temizle (onayınla) |
| **2** | L3 ve L5'i anahtarlarla başlat · Azure VM açık · DOUZEM e-postası | 017'ye merge (merge commit) · 017 → main PR · staging: `/health/ready` 200 · E2 gerçek eval `workflow_dispatch` · başarı raporu bölümü |
| **3** | Jüri provası ×2 (I8 senaryosu) · kılavuzları oku · freeze onayı | L6 birleştir · README/test-report son sayaçlar · main yeşil · etiket/RC · kapanış raporu |

**Gün-1 sonunda görmen gerekenler:** PR #26 yeşil kalıyor; L1/L2/L4/L6 PR'ları açık; Secrets adları eklendi; ZDR açık; Azure VM oluşturuldu.
**Kırmızı çizgiler:** squash/rebase merge yok · `--workers=1` tüm suite'e uygulanmaz · gerçek Groq PR'da koşmaz · "production-ready / KVKK uyumlu / LTI hazır" denmez · ölçülmemiş sayı slayta girmez.
