# Faz 2 — beş yeni oturum, önce bunu oku

> **9 Ağustos 2026, ~15:00.** Bu belge beş oturumun tamamı için ortaktır.
> Kendi şerit belgeni (`11_` … `15_`) okumadan önce burayı bitir.
> Teslim **24 Ağustos**. Bugün elde çalışan bir sistem var; kalan iş onu
> savunulabilir, kurulabilir ve anlatılabilir hâle getirmek.

---

## 1. Bugün nerede duruyoruz

`main` = `e03e68f`. Beş şeridin **tamamı birleşti**, dalları silindi.

| Katman | Durum |
|---|---|
| Backend testleri | **473 geçiyor** |
| mypy | temiz, 59 dosya |
| ruff | temiz (check + format) |
| OpenAPI | kodla birebir, **24 yol** |
| Şema | `0001`, `0003`, `0004`, `0005` — 19 tablo |
| Frontend birim | 25 · uçtan uca 9 |

Çalışan hat: yükleme → parçalama → embedding → hibrit arama (RRF) → kanıt eşiği
→ LLM → guardrail zinciri (atıf/sızıntı/sanitize) → kaynaklı cevap ya da
gerekçeli ret. Sokratik merdiven, sınav provası, soru havuzu ve analitik uçları
da `main`'de. Canlı koşuda doğrulandı (9 Ağu 14:35): gerçek ders materyaliyle
kaynaklı cevap, kapsam dışı soruda nazik ret, merdiven "sadece söyle" dediğinde
ilerlemiyor, gerçek denemede ilerliyor.

**Bilmen gereken iki taze değişiklik:**

1. **Kanıt eşiği 0.35 → 0.81** (kalibre edildi, T043). Eski değer ölü bir kapıydı:
   ölçülen hiçbir dense skor 0.76'nın altına inmiyordu. Holdout kalibrasyonu
   DOĞRULAMADI (doğru ret %80, hedef %90) ve bu `config.py`'de yazılı duruyor.
2. **`SessionDep` artık `scope="function"`** — işlem, yanıt istemciye
   yazılmadan önce commit ediliyor. Bunun bir yan etkisi var: yükleme ucunun
   arka plan worker tetiği artık GERÇEKTEN çalışıyor (önceden boş kuyruk görüp
   sessizce sıfır dönüyordu). Yükleme testi yazıyorsan bunu hesaba kat.

## 2. Neden yine paralel ve bu sefer neyin farklı

9 Ağustos'ta beş oturum aynı klasörde çalıştı ve iki oturumun commit'i başka
şeridin dalına düştü. Sebep basitti: `git checkout -b` klasör genelinde etki
eder. Bu sefer kural pazarlıksız:

**İLK İŞİN, KOD OKUMADAN ÖNCE, KENDİ WORKTREE'Nİ AÇMAK.**

```bash
cd ~/code/dou-lead
git fetch origin
git worktree add ~/code/.dou-<serit-adi> -b feat/<serit-adi> origin/main
cd ~/code/.dou-<serit-adi>
cd apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cp ../../.env.example .env
```

Şerit adın kendi belgende yazılı. Bundan sonra **hep o klasörde** çalış.
`~/code/dou-lead` (lider) ve `~/code/DOU-Synapse` klasörlerine **dokunma**.

Veritabanı paylaşılır, yeniden kurmana gerek yok. Test veritabanı worktree
adından türetilir; `TEST_DB_NAME` vermene gerek YOK.

## 3. Dosya sahipliği — bu sefer daha katı

Geçen sefer çakışmalar "sıcak dosyalar"dan çıktı. Bu sefer o dosyalar **önden
düzenlendi ve kilitlendi.**

### Hiçbir şeridin dokunamayacağı dosyalar (LİDER)

```
apps/web/**                     ← TAMAMI liderde, istisnasız
apps/api/app/main.py            ← router'lar önden kayıtlı
apps/api/app/core/config.py     ← ihtiyacın olan alanlar önden eklendi
apps/api/app/core/errors.py
apps/api/app/contracts.py
apps/api/app/api/deps.py
apps/api/app/api/chat.py
apps/api/app/schemas/chat.py
apps/api/app/models/**
docs/team/parallel/**           ← kendi belgenin EN ALTINA rapor ekleyebilirsin
```

**`config.py`'de zaten var:** `eval_llm_api_key`, `worker_drain_secret`,
`evidence_threshold` (0.81), `llm_*`, `retrieval_*`, `socratic_max_stage`,
`chat_rate_limit_*`. Yeni bir ayar gerekiyorsa **gruba yaz, kendin ekleme.**

**`app/api/internal.py` zaten var ve `main.py`'ye kayıtlı** — boş bir router.
Faz G şeridi gövdeyi yazar, kayıt satırına dokunmaz.

### Paylaşılan ama çakışmayan iki dosya

`specs/001-course-assistant-mvp/tasks.md` — **yalnız kendi görev satırların.**
Başlıklara, bağımlılık notlarına, başka görevin satırına dokunma:

```
- [x] T045 ... **DONE (2026-08-XX):** ne ölçüldü, hangi sette, sonuç ne.
```

`specs/001-course-assistant-mvp/contracts/openapi.json` — yeni uç eklediysen
**oturumun sonunda BİR KEZ** yeniden export et, her uçta değil:

```bash
cd apps/api && uv run python -c "
import json, os
os.environ.setdefault('DEV_AUTH_ENABLED','true')
from app.main import create_app
spec = create_app().openapi()
open('../../specs/001-course-assistant-mvp/contracts/openapi.json','w').write(
    json.dumps(spec, ensure_ascii=False, indent=2))
print('güncellendi:', len(spec['paths']), 'yol')
"
```

Rebase'te çakışırsa: `git checkout --theirs <dosya>`, sonra komutu tekrar koştur.
**Elle düzenleme yok.**

## 4. Migration numaraları

| No | Durum |
|---|---|
| `0001` `0003` `0004` `0005` | **main'de — yerinde DEĞİŞTİRİLEMEZ** |
| `0002` | **R1'e ayrıldı** (Supabase Auth köprüsü) |
| `0006` | **R4'e ayrıldı** (gerekirse) |
| `0007` | **R3'e ayrıldı** (gerekirse) |
| `0008+` | boş — almadan önce gruba yaz |

`main`'e girmiş bir migration yerinde değiştirilmez, yeni numara açılır.

**Dev veritabanı uyarısı:** `dou_synapse` bugün `0003`'ü eksik koşuyordu ve
sohbet ekranı 500 veriyordu; lider elle uyguladı. Kendi worktree'nde bir şey
çalışmıyorsa önce şemayı doğrula:

```bash
psql -d dou_synapse -c "\dt"    # 19 tablo görmelisin
```

## 5. Pazarlıksız kurallar (Anayasa)

`.specify/memory/constitution.md` on bir ilke tanımlar. Kod yazmadan önce oku.
En sık ihlal edilen dördü:

**I — Kaynak yoksa cevap yok.** Atıflar `chunk_id` set-membership'ten geçer.
Dosya adı ve sayfa numarası **model metninden değil** chunk metadata'sından.

**II — İki katmanlı izolasyon.** İstemciden gelen `course_id` asla yetki
değildir. Kendi üyelik sorgunu YAZMA; `CourseMemberDep`/`CourseInstructorDep`
kullan. Testler `dou_app` rolüyle koşar — superuser'a geçirme, RLS sessizce
atlanır ve testin hiçbir şey kanıtlamaz.

**III — Ölçmeden iddia etme.** Koşturmadığın deney için sonuç yazma. Bir sayıyı
raporluyorsan onu üreten komut da yanında olsun. "Deterministik" ve "garanti"
sözcükleri yalnız gerçekten deterministik mekanizmalar için. **KOŞULMADI yazmak
tahmin yazmaktan iyidir** — Şerit 5 bunu yaptı ve raporu bu yüzden savunulabilir.

**IV — Fail-closed.** Belirsizlikte kapan. Sırsız uç açılmaz, doğrulanamayan
çıktı gösterilmez, eşik aşılamazsa abstention.

**V — Türkçe birinci sınıf.** Kullanıcıya dönen her metin Türkçe.
`uppercase` dönüşümü yasak (i/İ bozulur).

**VIII — Doğrulama bitmeden "bitti" yok.** Testler yeşil, lint temiz, davranış
gerçek ortamda gözlenmiş olmadan commit mesajına "çalışıyor" yazılmaz.

**XI — Modülerlik.** Aynı davranış üçüncü kez yazılıyorsa ortak modüle çıkar.
Etkin görünüp iş yapmayan buton/uç **kusurdur**. Ölü kod commit'te temizlenir.

## 6. Doğrulama — bitirmeden önce her seferinde

```bash
cd apps/api
uv run pytest -q                    # 473 + seninkiler, hepsi yeşil
uv run mypy app                     # temiz
uv run ruff check . && uv run ruff format --check .
```

**mypy'a özellikle bak.** Üç şeridin birleşiminde iki uyuşmazlığı testler değil
mypy yakaladı — o kod yolları hiçbir testte koşmuyordu.

## 7. Git akışı — tam yetkin var

```bash
git add <kendi dosyaların>
git commit          # gövde "ne"yi değil NEDEN'i anlatır
git push origin feat/<serit-adi>
```

**İzin sorma. Commit ve push için tam yetkin var.** Sık commit'le; her görev
kendi commit'iyle kapanır.

`main`'e sen birleştirme — lider birleştirir. Ama `main` ilerledikçe rebase al:

```bash
git fetch origin && git rebase origin/main
```

**Commit kuralları:**
- `Co-Authored-By` / "Generated with" izleri **asla** eklenmez
- Commit öncesi sızıntı taraması: `.env`, anahtar, token repoya girmez
- Gövde: neyi neden yaptığını, hangi ölçümün seni oraya götürdüğünü anlat

## 8. Ne zaman durursun

**Durmadan çalış.** Bir iş bitince belgenin sıradaki maddesine geç. Şu dört
durumda dur ve raporuna yaz (ama duruncaya kadar başka her şeyi bitir):

1. Sahipliğin dışındaki bir dosyayı değiştirmen gerekiyorsa
2. `contracts.py` ya da `config.py`'de eksik bir alan varsa
3. Bir kararın başka bir şeridi etkileyecekse
4. Gerçek bir dış anahtar/erişim gerekiyorsa (LLM API anahtarı, prod Supabase)

**4. madde önemli:** anahtar yokken duracak işler var. Onları en sona bırak ve
öncesinde anahtarsız yapılabilecek HER ŞEYİ bitir. Anahtar gerektiren işi
"anahtar yok" diye bırakmak meşrudur; anahtarsız yapılabilecek hazırlığı
yapmamak değildir.

## 9. Bilinen tuzaklar

1. **Superuser'la test koşma** — RLS sessizce atlanır. `conftest.py` `dou_app`
   ile bağlanıyor; bozma.
2. **Python 3.12 pinli** — onnxruntime/fastembed 3.13+ desteklemiyor.
3. **Postgres 16 keg-only** — `export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"`
4. **`.test` TLD'li e-postalar** — email-validator reddeder; testlerde
   `@dogus.edu.tr`.
5. **FTS altyapısı `0001`'de ZATEN VAR** — yeniden inşa etme.
6. **E5 embedding `query:`/`passage:` öneki zorunlu**, fastembed EKLEMEZ —
   bizim kodda, testle sabit.
7. **API anahtarı yokken LLM istemcisi deterministik sahteye düşer.**
   Bu yüzden "uç 200 döndü" ile "üretim çalışıyor" aynı şey DEĞİL. Sahte
   sağlayıcıyla gözlenen her şey "doğrulanması gereken şüphe"dir, kanıt değil.
8. **Lider `:8010`'da bir API çalıştırıyor.** Kendi sunucunu farklı bir portta
   aç (şerit belgende yazılı) ve `--port` vermeyi unutma.

## 10. Şeritler

| Şerit | Alan | Belge | Worktree / dal | Port |
|---|---|---|---|---|
| R1 | Kimlik + üretim güvenliği | `11_R1_KIMLIK.md` | `.dou-auth` / `feat/auth` | 8021 |
| R2 | Ölçüm koşuları (T045-T047) | `12_R2_OLCUM.md` | `.dou-eval` / `feat/eval-runs` | 8022 |
| R3 | Dağıtım + çevrimdışı dayanıklılık | `13_R3_DAGITIM.md` | `.dou-deploy` / `feat/deploy` | 8023 |
| R4 | Cevap kalitesi + guardrail | `14_R4_KALITE.md` | `.dou-quality` / `feat/answer-quality` | 8024 |
| R5 | Belgeler + teslim paketi | `15_R5_BELGELER.md` | `.dou-docs` / `feat/docs` | 8025 |
| — | **Frontend'in tamamı + entegrasyon** | — | lider | 8010 |

Frontend'e **hiçbir şerit dokunmaz.** Arayüzde bir şeye ihtiyacın varsa
raporuna yaz; lider yapar.
