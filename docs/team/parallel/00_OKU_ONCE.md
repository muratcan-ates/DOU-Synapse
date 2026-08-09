# Paralel geliştirme — önce bunu oku

> **9 Ağustos 2026.** Beş oturum aynı anda çalışacak. Bu belge hepsi için ortaktır;
> kendi handoff'unu okumadan önce burayı bitir.

---

## 1. Neden beş oturum ve neden çakışmayacaklar

Proje 24 Ağustos'ta teslim ediliyor ve cevap üretim hattı (retrieval → LLM →
guardrail) henüz yazılmadı. Bu hat bitmeden Sokratik mod, sınav provası ve
değerlendirme altyapısı da başlayamıyor. Sıralı gitmek takvime sığmıyor, o yüzden
iş beş şeride bölündü.

Paralel çalışmanın tek gerçek riski **aynı dosyaya iki elin dokunması.** Bu risk
oturumlar başlamadan önce kaldırıldı:

| Sıcak dosya | Ne yapıldı |
|---|---|
| `app/main.py` | Beş router **önden kaydedildi**. Modüller boş ama kayıtlı; sen yalnız kendi dosyanın gövdesini yazarsın, `main.py`'ye dokunmazsın |
| `app/core/config.py` | Retrieval, LLM ve Sokratik ayarları **önden eklendi**. Yeni alan gerekiyorsa gruba yaz |
| `pyproject.toml` | `litellm` **önden eklendi** |
| `app/contracts.py` | Modüller arası tipler **önden sabitlendi** — bu dosyayı yalnız lider değiştirir |
| `apps/web/**` | Tamamı liderde. Hiçbir oturum frontend'e dokunmaz |

Bu yüzden şeridine bak: **sahiplendiğin dosyalar listesi dışına çıkma.** Bir
dosyaya ihtiyacın varsa ve listende değilse, gruba yaz; kendin düzenleme.

## 2. Sözleşme dosyası — `app/contracts.py`

Modüller birbirinin **imzasına** karşı yazılır, gövdesine değil. Yani retrieval
henüz yazılmamışken bile onu çağıran kod derlenir ve test edilir.

Oku: `apps/api/app/contracts.py`. İçinde `RetrievedChunk`, `Retriever`,
`GeneratedAnswer`, `Generator`, `Citation`, `GuardrailVerdict`, `Guardrail`,
`AnswerStatus`, `ChatMode`, `SocraticStage`, `GradedAnswer` var.

**Bu dosyayı değiştirme.** Bir alan eksikse gruba yaz. Tek taraflı bir değişiklik,
ona karşı yazılmış üç modülü aynı anda kırar.

Bağımlı olduğun modül henüz yazılmadıysa, testinde `Protocol`'ü uygulayan basit
bir sahte sınıf yaz. Örnek:

```python
class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    async def search(self, *, course_id, query, limit=8):
        return self._chunks[:limit]
```

## 3. Pazarlıksız kurallar

`.specify/memory/constitution.md` on bir ilke tanımlar. Kod yazmadan önce oku.
En sık ihlal edilenler:

**I — Kaynak yoksa cevap yok.** Atıflar `chunk_id` set-membership kontrolünden
geçer; model retrieve edilmemiş bir kaynağa atıf yapamaz. Dosya adı ve sayfa
numarası **model metninden değil** chunk metadata'sından üretilir.

**II — İki katmanlı izolasyon.** İstemciden gelen `course_id` asla yetki değildir.
Kendi üyelik sorgunu YAZMA; `CourseMemberDep` / `CourseInstructorDep` kullan.
Testler `dou_app` rolüyle koşar — superuser'a geçirme, RLS sessizce atlanır ve
testin hiçbir şey kanıtlamaz.

**III — Ölçmeden iddia etme.** Koşturmadığın deney için sonuç yazma. Eşikler
kalibrasyon setiyle ayarlanır, metrikler holdout sette raporlanır. "Deterministik"
ve "garanti" sözcükleri yalnız gerçekten deterministik mekanizmalar için.

**IV — Fail-closed.** Belirsizlikte kapan, açma. Kanıt eşiği aşılamazsa abstention;
pedagojik filtre ihlali regen'le çözülmezse şablon ipucu; doğrulanamayan çıktı
gösterilmez.

**V — Türkçe birinci sınıf.** Kullanıcıya dönen her metin Türkçe. `uppercase`
dönüşümü yasak (i/İ bozulur). Backend anlaşılır Türkçe üretir, frontend kendi
metnini uydurmaz.

**VIII — Doğrulama bitmeden "bitti" yok.** Testler yeşil, lint temiz ve davranış
gerçek ortamda gözlenmiş olmadan commit mesajına "çalışıyor" yazılmaz.

**XI — Modülerlik ve tekrarsızlık.** Aynı davranış üçüncü kez yazılıyorsa ortak
modüle çıkarılır. Etkin görünüp iş yapmayan buton/uç kusurdur. Ölü kod commit'te
temizlenir. Durdurulmayan polling, aynı veriyi iki kez çekme: kusur.

## 4. Kurulum

```bash
cd ~/code/DOU-Synapse
git pull origin main

export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
createdb dou_synapse 2>/dev/null || true
for f in supabase/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -d dou_synapse -f "$f"; done
psql -d dou_synapse -f supabase/local_dev_setup.sql
psql -d dou_synapse -f supabase/seed_demo.sql

cd apps/api
uv venv --python 3.12
uv pip install -e ".[dev]"
cp ../../.env.example .env
uv run pytest -q        # 92 test yeşil olmalı
```

92 yeşil görmeden kod yazmaya başlama. Görmüyorsan sorun sende değil, kurulumda;
`specs/001-course-assistant-mvp/quickstart.md` tam anlatımı içerir.

## 5. Git akışı — ÖNCE KENDİ ÇALIŞMA AĞACINI AÇ

**Bu bölümü atlama.** Beş oturum aynı makinede, aynı klasörde çalışıyor. `git
checkout -b` çalıştırırsan dalı YALNIZ kendin için değil, o klasörü kullanan
herkes için değiştirirsin: başka bir oturum farkında olmadan senin dalında
çalışmaya başlar ve commit'siz işi senin dalının üstünde birikir.

Bu 9 Ağustos'ta fiilen yaşandı — lider, farkında olmadan Şerit 3'ün dalında
çalışıyordu. İş kaybolmadı ama kurtarmak vakit aldı. Çözüm: **git worktree.**
Her oturum kendi klasöründe, kendi dalında, aynı depoyu paylaşarak çalışır.

**İlk iş — kendi çalışma ağacını aç:**

```bash
cd ~/code/DOU-Synapse
git fetch origin
git worktree add ~/code/dou-<serit-adi> -b feat/<serit-adi> origin/main
cd ~/code/dou-<serit-adi>
```

Örnek: Şerit 1 için `git worktree add ~/code/dou-retrieval -b feat/retrieval origin/main`

Bundan sonra **hep o klasörde** çalış. `~/code/DOU-Synapse` klasörüne dokunma.

Kurulum o klasörde bir kez tekrarlanır (venv ve node_modules paylaşılmaz):

```bash
cd apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cp ../../.env.example .env
```

Veritabanı paylaşılır, yeniden kurmana gerek yok.

Sonra: kendi commit'lerini at, **kendin push et**. İzin sorma.

```bash
git push origin feat/<serit-adi>
```

`main`'e birleştirmeden önce:

```bash
git fetch origin && git rebase origin/main
cd apps/api && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Rebase'te çakışma çıkarsa: senin şeridine ait dosyalarda çakışma çıkmamalı. Çıktıysa
biri şeridinin dışına taşmış demektir — çözmeden önce gruba yaz.

**Commit kuralları (Anayasa IX):**
- Gövde "ne"yi değil **"neden"i** anlatır
- `Co-Authored-By` / "Generated with" izleri **asla** eklenmez
- Her görev kendi commit'iyle kapanır
- Commit öncesi sızıntı taraması: `.env`, anahtar, token repoya girmez

## 6. `tasks.md` protokolü

`specs/001-course-assistant-mvp/tasks.md` beş oturumun da dokunacağı tek dosya.
Kural: **yalnız kendi görev satırlarını** düzenle, `[ ]` → `[x]` yap ve tarihli
DONE notu düş:

```
- [x] T006 ... **DONE (2026-08-09):** hybrid retrieval RRF ile; izolasyon testi eklendi.
```

Başka bir görevin satırına, başlıklara veya bağımlılık notlarına dokunma. Böyle
yapılırsa git satır bazında birleştirir ve çakışma çıkmaz.

## 7. OpenAPI sözleşmesi

Yeni uç ekleyen oturum, sözleşmeyi **oturumun sonunda bir kez** yeniden export
eder — her uçta değil:

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

Rebase'ten sonra çakışırsa: dosyayı `git checkout --theirs` ile al, sonra komutu
tekrar koştur. Elle düzenleme yok.

## 8. Migration numaraları — ayrılmış

| No | Kim | Konu |
|---|---|---|
| `0001` | (bitti) | çekirdek şema + RLS |
| `0002` | ayrılmış | Supabase Auth köprüsü |
| `0003` | **Şerit 3** | chat_sessions, chat_messages, answer_cache |
| `0004` | (bitti) | assessment |
| `0005` | **Şerit 5** | analytics/eval için gerekirse |
| `0006+` | boş | gerekirse gruba yaz |

**`main`'e girmiş bir migration yerinde değiştirilmez**, yeni numara açılır.
Kendi numaran dışına çıkma.

## 9. Beş şerit

| Şerit | Alan | Bağımlılık | Handoff |
|---|---|---|---|
| 1 | Retrieval hattı (T003-T007) | yok — hemen tam hız | `01_RETRIEVAL.md` |
| 2 | Generation + guardrails (T008-T016) | yok — sahte retrieval'la | `02_GENERATION.md` |
| 3 | Chat API + Sokratik (T017-T020, T026-T028) | 1+2'nin **imzası** | `03_CHAT_SOKRATIK.md` |
| 4 | Soru üretimi + sınav (T029-T033) | 2'nin **imzası** | `04_SORU_SINAV.md` |
| 5 | Analitik + değerlendirme (T037-T047) | yok | `05_ANALITIK_EVAL.md` |
| — | Frontend + RLS kanıtı + CI | — | lider (bu oturum değil) |

Şerit 3 ve 4, bağımlı oldukları modüller henüz yazılmamışken **sahte
uygulamalarla** ilerler. Gerçek modül `main`'e inince rebase alıp sahteyi
testlerde bırakır, üretim yolunda gerçeğe geçer.

## 9.1 Zaten başlamış oturumlar için

Şerit 2 ve 3 çalışmaya `~/code/DOU-Synapse` içinde başladı. İşiniz kaybolmaz,
ama devam etmeden önce kendi ağacınıza taşıyın:

```bash
cd ~/code/DOU-Synapse
git status                      # commit'siz iş var mı?
git stash push -u -m "gecis"    # varsa sakla
git worktree add ~/code/dou-<serit-adi> feat/<serit-adi>
cd ~/code/dou-<serit-adi>
git stash pop                   # sakladıysan geri al
```

Dalınız zaten push'landıysa `-b` olmadan yazın (yukarıdaki gibi); dal yeni
oluşturulacaksa `-b feat/<serit-adi> origin/main` ekleyin.

## 10. Ne zaman durursun

Durmadan çalış. Şu üç durumda dur ve gruba yaz:

1. **Şeridinin dışındaki bir dosyayı değiştirmen gerekiyorsa.**
2. **`app/contracts.py`'de eksik bir alan varsa.**
3. **Bir kararın başka bir şeridi etkileyeceğini fark edersen** (ör. şema
   değişikliği, ortak bir davranış kuralı).

Bunun dışında: kendi başına karar ver, yaz, test et, commit'le, push et.

## 11. Bilinen tuzaklar

1. **Superuser'la test koşma** — RLS sessizce atlanır, izolasyon testin hiçbir şey
   kanıtlamaz. `conftest.py` zaten `dou_app` ile bağlanıyor; bozma.
2. **Python 3.12 pinli** — onnxruntime/fastembed 3.13+ desteklemiyor.
3. **Postgres 16 keg-only** — `PATH`'e `/opt/homebrew/opt/postgresql@16/bin` ekle.
4. **`.test` TLD'li e-postalar** — email-validator reddeder; testlerde `@dogus.edu.tr`.
5. **FTS altyapısı 0001'de ZATEN VAR** (`chunks.fts` + GIN) — yeniden inşa etme.
6. **E5 embedding `query:`/`passage:` öneki zorunlu** ve fastembed bunu EKLEMEZ —
   bizim kodda, testle sabit (`test_embedding_prefix.py`).
7. **Next.js 16 + Tailwind v4 eğitim verinden farklı** — frontend'e dokunmuyorsun
   ama okuman gerekirse `apps/web/AGENTS.md` var.
