# PR incelemesi — 6 Ağustos 2026

> İnceleyen: Muratcan (R4 + lead) · Açan: Metehan Alphan (R3 + R5)
> İncelenen dallar: `feat/T024-assessment-migration`, `feat/T036-mastery-service`,
> `feat/T002-sample-data` — üçü de `main@60b3107` üzerine, her biri tek commit.
>
> **Sonuç: üçü de birleştirilebilir, blocker yok.** Merge öncesi 3 kalem, sonrasına
> bırakılabilir 4 major takip görevi var. Aşağıdaki her iddia bu makinede fiilen
> koşturularak doğrulandı; koşturulamayan hiçbir iddia rapora alınmadı.

---

## 1. Karar tablosu

| PR | Dal | Karar | Gerekçe |
|---|---|---|---|
| #1 | `feat/T024-assessment-migration` | küçük düzeltmeyle birleştir | Şema ve RLS deseni 0001'e sadık; topics ucu doğru çalışıyor. Kalem 1 ve 2 düzeltilsin. |
| #2 | `feat/T036-mastery-service` | **birleştir** | EWMA, ipucu çarpanları ve seviye eşikleri şartnameyle birebir; mutasyon testiyle kilitli olduğu kanıtlandı. Düzeltme gerekmiyor. |
| #3 | `feat/T002-sample-data` | küçük düzeltmeyle birleştir | 14 dosyanın tamamı projenin kendi parser'ından geçiyor; kalem 3 düzeltilsin. |

**Birleştirme sırası zorunlu: #1 → #2 → #3.**
PR #2 hem `app.models.assessment.Mastery`'yi import ediyor hem test fixture'ında
`POST /courses/{id}/topics` ucunu çağırıyor — PR #1 olmadan import bile edilemiyor.
PR #3 tamamen bağımsız (`sample_data/` + `tasks.md`), metin düzeltmesi diğer ikisini
bekletmesin.

## 2. Doğrulanan sağlık durumu

Üçü birlikte merge edilmiş bir çalışma ağacında:

| Kontrol | Sonuç |
|---|---|
| `uv run pytest -q` | **90 geçti** (main'de 68 idi, +22 yeni) |
| `uv run ruff check .` | temiz |
| `uv run ruff format --check .` | 48 dosya biçimli |
| `uv run mypy app` | yalnız önceden var olan 2 hata (`parsers.py:63` — bu PR'larda dokunulmamış dosya) |
| `0001` + `0004` sıfırdan uygulama | hatasız |
| `supabase/tests/rls_isolation.sql` | 8/8 PASS |
| Git çakışması | yok — üçü de `tasks.md`'ye dokunuyor ama farklı satırlarda |
| Gizli anahtar / büyük dosya | yok; en büyük yeni dosya 65 KB PDF |
| Dosya sahipliği ihlali | **yok** — Metehan yalnız R3/R5 dosyalarına yazmış, sıcak dosyaları protokole uygun kullanmış |

---

## 3. Merge öncesi düzeltilecek 3 kalem

### Kalem 1 — OpenAPI sözleşmesi güncellenmemiş `[major]` · PR #1

**Dosya:** `specs/001-course-assistant-mvp/contracts/openapi.json`

Kodda 10 yol var, sözleşmede 9. Eksik olan tam da yeni eklenen
`/courses/{course_id}/topics`. Ölçüm:

```
kodda 10 yol, sözleşmede 9 yol
sözleşmede EKSİK: ['/courses/{course_id}/topics']
sözleşmede FAZLA: []
```

main'de sözleşme koda birebir eşitti; ayrışmayı bu PR yaratıyor. Kural üç ayrı yerde
yazılı: `tasks.md:225`, `00_TAKIM_KOORDINASYON.md:137` ("**Elle düzenleme.** Yeniden
export et ve aynı commit'te gönder"), `03_ASSESSMENT_BRIEF.md` kural 9.

**Düzeltme** — brief §7.3'teki komut, elle düzenleme yok:

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

Sonuç 159 satır ekleme, 0 silme — yan hasar yok.

---

### Kalem 2 — Denormalize `course_id` INSERT politikalarında doğrulanmıyor `[major]` · PR #1

**Dosya:** `supabase/migrations/0004_assessment.sql` (satır 201-207 `answers_self_insert`,
215-218 `mastery_self_insert`/`mastery_self_update`)

`mastery_self_insert` yalnız `user_id = app.current_user_id()` şartına bakıyor;
satırın `course_id`'sinin kullanıcının üye olduğu bir derse ait olup olmadığına hiç
bakmıyor. Temiz bir veritabanında kanıtlandı:

- Burak yalnız **B dersinin** öğrencisi, A dersine üye değil.
- Burak, A dersinin konusuna mastery satırı yazdı → `INSERT 0 1` (geçti).
- A dersinin eğitmeni Ayşe, analitiğinde o satırı görüyor → `1 satır`.

Yani üye olunmayan bir dersin eğitmeninin analitik görünümüne satır enjekte edilebiliyor.
Aynı boşluk `answers_self_insert`'te de var (oturumun `course_id`'si ile cevabın
`course_id`'si karşılaştırılmıyor), ve `mastery_self_update` mevcut bir satırın yabancı
bir derse taşınmasına izin veriyor.

Bu, 0001'in kendi deseninden sapma: `exam_sessions_self_insert` üyeliği kontrol ediyor
(`user_id = app.current_user_id() AND app.is_member(course_id)`), `mastery_self_insert`
etmiyor.

**Düzeltme:**

```sql
-- answers_self_insert WITH CHECK'ine:
AND s.course_id = answers.course_id

-- mastery_self_insert ve mastery_self_update WITH CHECK'ine:
AND app.is_member(course_id)
```

**Neden şimdi:** yalnız `0001` dondurulmuş durumda. `0004` henüz hiçbir ortama
(lokal demo dahil) uygulanmadı, dolayısıyla dosya yerinde düzeltilebilir. Merge
sonrasında aynı düzeltme `0005_*.sql` maliyeti çıkarır. Düzeltme denendi: üç enjeksiyon
yolu da kapandı, 90/90 test yeşil kaldı.

**Aynı commit'te önerilir (ayrıca doğrulanmadı, Metehan koştursun):**
`exam_sessions_self_update`'e `WITH CHECK (user_id = app.current_user_id() AND
app.is_member(course_id))` — oturumun üye olunmayan bir derse taşınmasını kapatır.

---

### Kalem 3 — `bug_hunt` cevap anahtarında olgusal hata `[major]` · PR #3

**Dosyalar:** `sample_data/isletim-sistemleri/04-synchronization.md:85-89` ve `106-107`,
aynı cümlenin girdiği `04-synchronization.pdf` (yeniden üretilmeli),
`producer_consumer.py:9-11` (docstring), `sample_data/README.md:35-36`

Metin, `producer_consumer.py`'deki kasıtlı hatayı şöyle açıklıyor:

> "…`wait()` ve `signal()` çağrıları yanlış sırada olduğunda tamponun taşması (overflow)
> veya taşınması (underflow) da mümkün hale gelir, çünkü sayaç semaforları artık gerçek
> boş/dolu yuva sayısını doğru yansıtmaz."

Bu yanlış. Dosya 30 kez çalıştırıldı (3 sn zaman aşımıyla):

```
{'ASILDI (deadlock)': 30}
```

30/30 yalnızca deadlock; tek bir overflow ya da underflow yok. Verilen mekanizma
açıklaması da hatalı: `wait(empty)`'yi mutex'in içine almak sayaç semaforlarının boş/dolu
yuva sayımını bozmaz — yalnızca kilitlenme üretir. Taşma/taşınma ayrı bir hatanın
(`signal(full)`'ün append'den önce çağrılması) sonucudur.

**Not:** metnin deadlock kısmı **doğru** ve `producer_consumer.py:7-9`'daki deadlock
açıklaması da **doğru** — onlara dokunulmasın. Yalnızca taşma/taşınma ve "sayaçlar gerçek
yuva sayısını yansıtmaz" cümleleri çıkarılsın, tek sonuç "deadlock" olarak yazılsın.

**Neden acil:** T041-a kalibrasyon seti G4'te (7 Ağu) tam olarak bu metinden türeyecek ve
`05_DATA_EVAL_BRIEF.md` "bug_hunt değerlendirmesi tamamen cevap anahtarına dayanır, kod
ASLA çalıştırılmaz" dediği için sistemde bu hatayı sonradan yakalayacak hiçbir mekanizma
yok. Yanlış cevap anahtarı doğrudan yanlış gold set demek.

---

## 4. Takip görevleri (merge'i bloklamaz)

### 4.1 `0004`'ün 15 RLS politikasının hiçbirinin otomatik kanıtı yok `[major]`

**Dosyalar:** `supabase/tests/rls_isolation.sql`, `.github/workflows/ci.yml`

Mutasyonla ölçüldü: `questions_read` politikasından `AND status = 'approved'`
düşürüldüğünde **90 test yeşil**, `rls_isolation.sql` **8/8 PASS**, `ci.yml`'deki
`grep -q FAIL` kapısı **geçiyor** — aynı anda psql'de öğrenci taslak sınav sorusunu
görüyor. Ölçme katmanının tüm politikaları `USING(true)` yapıldığında bile CI tamamen
yeşil kalıyor.

Politikalar **doğru çalışıyor** (elle psql ile kanıtlandı); eksik olan **kanıt**. Projenin
tezi tam olarak buydu: "iki katmanlı izolasyon, kanıtlı".

**Sahiplik uyarısı:** `supabase/tests/` R2'nin (Eren) dosyası — Metehan çapraz düzenleme
yapamaz. İki seçenek: (a) hazır SQL bloğunu Eren'e yazılı ver, (b) ayrı bir
`supabase/tests/rls_assessment.sql` aç ve `ci.yml`'ye ekle.

**T033 ve T051 bu boşluğu kapatmıyor:** T033 HTTP düzeyinde koşuyor ve uygulama katmanı
aynı filtreyi zaten zorunlu tuttuğu için bir RLS gevşemesini maskeler; T051 tek seferlik
bir prod gösterisi.

**Ucuz ek:** `test_mastery.py`'deki entegrasyon testi eğitmen personasıyla koşuyor
(Ayşe hem eğitmen hem satır sahibi), dolayısıyla mastery politikalarının **öğrenci kolunu
hiç sınamıyor**. Öğrenci versiyonu yazıldı, aynı skorlarla geçiyor — testi öğrenciye
çevirmek yeterli.

### 4.2 `questions.source_chunk_id ON DELETE RESTRICT` canlı belge silme ucunu kilitliyor `[major]`

**Dosyalar:** `supabase/migrations/0004_assessment.sql:55`, `apps/api/app/api/documents.py:157`

`DELETE /courses/{id}/documents/{doc_id}` main'de **zaten canlı**. Belge silme chunk'ları
CASCADE ile düşürüyor; o chunk'tan üretilmiş bir soru varsa RESTRICT patlıyor ve uç
IntegrityError yakalamadığı için kullanıcı 409 yerine **500** görüyor
(`foreign_key_violation` psql'de tetiklendi). Endpoint'in kendi docstring garantisiyle de
çelişiyor.

Bugün ulaşılamaz (soru yazan kod yolu yok) ama **T029 iner inmez patlar**, ve
`test_silinen_belgenin_chunklari_da_gider` 204 bekleyerek yeşil geçtiği için T029'u yazan
kişinin `documents.py`'ye bakmak için sebebi olmayacak.

**Karar T029'dan ÖNCE verilmeli.** İki yol: (a) `SET NULL` + nullable yap (kaynak
bilgisini payload'a kopyalanan alıntıyla telafi et), (b) `delete_document`'te açık 409
`ConflictError` + `questions`'a eğitmen DELETE politikası.

### 4.3 Öğrenci kendi puanını ve sınav süresini yazabiliyor `[major]`

**Dosya:** `supabase/migrations/0004_assessment.sql`

`exam_sessions_self_update` ve `mastery_self_update` sütun kısıtsız: öğrenci kendi
`score`, `expires_at` (sınav süresi uzatma) ve `mastery.score` alanlarını doğrudan
yazabiliyor. İkinci izolasyon katmanı ayrıcalık yükseltmeye karşı boş.

RLS yapısal olarak sütun kısıtı veremez — çözüm kolon bazlı GRANT, BEFORE UPDATE trigger
ya da SECURITY DEFINER fonksiyon (`app.finish_exam()`) veya puanlama yazımını `dou_worker`
rolüne taşımak. **Karar T032/T037 yazılmadan önce verilmeli.**

### 4.4 `answers` tablosunda hiç UPDATE politikası yok `[major]`

Puanlama (T031/T032) ve ipucu sayacı cevap satırına yazmak zorunda; şu an bu yol
tanımsız. T031 başlamadan önce karara bağlanmalı.

### 4.5 Küçük kalemler `[minor/nit]`

- **`Settings.mastery_alpha` ölü ayar** — `config.py`'ye eklenmiş ama
  `mastery/service.py` onu hiç okumuyor; servis kendi `DEFAULT_ALPHA` sabitini
  kullanıyor. Docstring ise okuduğunu söylüyor (`Settings.mastery_alpha`). İkisinden biri
  düzeltilsin: ya servis ayarı okusun, ya docstring düzeltilsin.
- **`mastery.updated_at` hiç güncellenmiyor** — sütun kalıcı olarak ilk cevabın zamanını
  gösteriyor. `record_answer` içinde `func.now()` atanmalı ya da trigger.
- **`questions.reviewed_by ON DELETE SET NULL`, `questions_reviewed_consistency` CHECK'i
  ile çelişiyor** — inceleyen eğitmenin profili silinirse CHECK ihlali doğar.
- **`questions`/`exam_sessions` için DELETE politikası yok** — eğitmen hatalı üretilmiş
  soruyu silemez.
- **`_hint_multiplier` fail-closed dalı, `raw_score` clamp satırı ve
  `previous_answer_count == 0` kolu testsiz** — üçü de kaldırılsa 90 test yeşil kalıyor.
  Davranışları doğru, kanıtları yok.
- **README içerik tablosu 13 dosyanın 8'ini listeliyor** — 5 `.md` kaynağı hiç geçmiyor.
  Ayrıca korpusta beş belge iki kez var (`.md` + `.pdf` ikizleri, ~%98,5 aynı içerik);
  retrieval'da yinelenen sonuç riski — bilinçli bir karar mı, README'de belirtilsin.
- **Canlı demo PDF'i 2 sayfa** — T002 kriteri 5-10 sayfa diyor
  (`05-deadlock-demo.pdf`). Sapma README'de farklı bir gerekçeyle kapatılmış.
- **PPTX belge metadata'sı üçüncü şahsa ait** — `last_modified_by = 'Steve Canny'`,
  `created = 2013-01-27` (python-pptx varsayılan şablonu). İçerik kendi üretimi ama
  metadata temizlenmeli; telif beyanıyla çelişkili görünüyor.
- **`tasks.md` işaretleme protokolü** — T024 ve T036 `[x]` ama tarihli DONE notu yok
  (koordinasyon belgesi:139 bunu istiyor). T030 fiilen kısmen yapıldı ama `[ ]` kaldı.
  T025'in "yerel Postgres olmadığı için canlı doğrulama Metehan tarafından yapılacak"
  notu artık güncel değil — bu makinede doğrulandı, 90/90 yeşil.
- **"Görev = commit = PR" kuralı** — PR #1 tek commit'te T024 + T025 + T030'un parçasını
  taşıyor. Bir dahakine ayrılsın.
- **Commit gövdelerinde ajan/sandbox izi var** ve bazı cümlelerden kelime düşmüş.
  Hiçbir dal push edilmiş bir merge'e girmediği için `--amend` ya da squash-merge şu anda
  bedava.

---

## 5. İnceleme sırasında ELENEN iddialar — yeniden açılmasın

Aşağıdakiler incelemede gündeme geldi ve **kanıtla çürütüldü**:

- **"T041 (gold set) hiç başlamamış"** → plan zaten G4'ü (7 Ağu) kalibrasyon seti günü
  olarak veriyor; `05_DATA_EVAL_BRIEF.md:723` G3'ü T002 günü sayıyor. Metehan planın
  önünde, gerisinde değil.
- **"T036 ölü kod, çağıran yok"** → T037 entegrasyonu ayrı bir görev ve brief bunu
  bilerek böyle sıralamış; imza R1'e yazılı verilecek.
- **"409 sonrası oturum bozuluyor / kısmi yazım kalıyor"** → koşturuldu: 409'dan sonra
  aynı istemciyle GET 200, POST 201 dönüyor, kısmi satır kalmıyor. Sorun yok.
- **"`Mastery.score` modelde `Float`, DB'de `double precision` — hassasiyet kaybı"** →
  koşturuldu: `0.2805` yazıldı, `0.2805` okundu, fark `0.00e+00`. Migration'lar elle
  yazıldığı için model tipi DDL üretmiyor. Sorun yok.
- **"EWMA formülü şartnameden sapıyor"** → `0.7×eski + 0.3×son` birebir doğrulandı.
- **"Geçersiz `hint_level` sessizce yutuluyor"** → `-1`, `5`, `99` üçü de `0.25`
  (en katı çarpan) döndürüyor; docstring'de yazdığı gibi fail-closed. Sorun yok.
- **"Dosya sahipliği ihlali var"** → yok. `main.py` yalnız `include_router` satırı,
  `config.py` kendi `# --- Assessment ---` bölümü, `tasks.md` yalnız kendi görev
  satırları — üçü de protokolün izin verdiği şekil.

---

## 6. Yöntem notu

İnceleme altı bağımsız mercekle yapıldı (SQL/RLS güvenliği, API+ORM, mastery matematiği,
spec/anayasa uyumu, sample_data telif+ingestion uyumu, test boşlukları), ardından her
bulgu onu **çürütmeye çalışan** bağımsız bir doğrulayıcıdan geçirildi. 36 bulgudan 9'u
çürütüldü, kalanlar şiddet derecesine göre yeniden sınıflandı.

Altı mercekten ikisi (API+ORM ve mastery) bağlantı hatasıyla yarıda düştü; onların alanı
elle kapatıldı — §5'teki elenen iddiaların dördü o kapsama girer.

RLS iddiaları mutasyon testiyle iki yönlü sınandı: politika bozulduğunda testin kırmızı
yanıp yanmadığı ölçüldü. Yeşil kalan her mutasyon §4.1'de kanıt boşluğu olarak raporlandı.

İnceleme boyunca hiçbir dala, `main`'e ya da uzak repoya yazılmadı; tüm deneyler ayrı
çalışma ağaçlarında ve geçici veritabanlarında yapıldı, sonrasında geri alındı.

---

# Tur 2 — 7 Ağustos 2026 (düzeltmelerin doğrulanması)

Metehan üç kalemin **üçünü de** düzeltti ve iki dalı güncelledi:

- `ae54870` — `fix(assessment): regenerate OpenAPI contract and close course-membership gap in RLS`
- `233d93d` — `fix(sample-data): correct false overflow/underflow claim in bug_hunt answer key`

## Doğrulama sonuçları

| Kalem | Durum | Kanıt |
|---|---|---|
| **1. OpenAPI sözleşmesi** | ✅ kapandı | Kodda 10 yol, sözleşmede 10 yol, yol kümeleri **birebir eşit** |
| **2. RLS `course_id` açığı** | ✅ kapandı | Dünkü saldırının aynısı koşturuldu: üye olmayan Burak'ın A dersine mastery yazma denemesi → `ERROR: new row violates row-level security policy`. Meşru yol (kendi dersi B) → `INSERT 0 1`. Satır taşıma → reddedildi. |
| **3. `bug_hunt` cevap anahtarı** | ✅ kapandı | `.md`, `.pdf` (yeniden üretilmiş, 3 sayfa), `producer_consumer.py` docstring'i ve `README` düzeltilmiş. Eski iddia (`sayaç semaforları artık gerçek…`) korpustan tamamen silinmiş. `producer_consumer.py` 20/20 koşumda hâlâ deadlock — docstring'in iddiası doğru. |

Metehan ayrıca istenmeyen ama önerilen kalemi de yaptı:
`exam_sessions_self_update`'e `WITH CHECK` eklendi — oturumun üye olunmayan bir derse
taşınması `ERROR: new row violates row-level security policy` ile reddediliyor (doğrulandı).
`answers_self_insert`'e `s.course_id = answers.course_id` eklendi — sahte `course_id`
ile cevap enjeksiyonu reddediliyor, doğru `course_id` ile `INSERT 0 1` (doğrulandı).

## Birleştirilmiş durumda sağlık

| Kontrol | Sonuç |
|---|---|
| `pytest` | **92 geçti** (dün 90) |
| `ruff check` / `format --check` | temiz |
| `mypy app` | yalnız önceden var olan 2 hata (`parsers.py:63`) |
| `rls_isolation.sql` | 8 PASS, 0 FAIL |

## Yeni testin gerçekliği (mutasyon testi)

`test_uye_olmayan_ders_icin_mastery_satiri_yazilamaz` **sahte yeşil değil**: politikadan
`AND app.is_member(course_id)` geri çıkarıldığında test kırmızı yanıyor
(`1 failed, 91 passed`). Ayrıca aşırıya kaçmadığını gösteren pozitif eşi de yazılmış.

## Kalan kanıt boşluğu

Üç RLS düzeltmesinden **yalnız biri** testle korunuyor. Mutasyonla ölçüldü:

| Düzeltme | Mutasyon sonucu |
|---|---|
| `mastery_self_insert` | **1 failed** ✅ korunuyor |
| `answers_self_insert` (`s.course_id = answers.course_id` → `true`) | 92 passed ❌ **testsiz** |
| `exam_sessions_self_update` (`WITH CHECK` kaldırıldı) | 92 passed ❌ **testsiz** |

İkisi de bugün ulaşılamaz (cevap/oturum yazan uç yok) ama T031/T032 inince canlı yola
girecek. §4.1'deki RLS kanıt görevi bu ikisini de kapsamalı.

## `0004`'ün yerinde değiştirilmesi — koordinasyon notu

`0004_assessment.sql` dün `a62ca41` ile `origin/main`'e girdi; düzeltme aynı dosyayı
**yerinde** değiştirdi (`0005` açılmadı). Bu, migration'ları **kalıcı** bir veritabanına
uygulamış olan herkesin düzeltmeyi almayacağı anlamına gelir — `psql -f` bir kez çalışır.

- Muratcan'ın lokal `dou_synapse` veritabanında assessment tabloları **yok** → etkilenmiyor.
- Test veritabanı her koşuda sıfırdan kuruluyor → etkilenmiyor.
- **Metehan kendi lokalinde eski `0004`'ü uyguladıysa** veritabanını yeniden kurmalı:
  `dropdb dou_synapse && createdb dou_synapse` + quickstart'taki üç `psql -f`.

Bundan sonrası için kural: `main`'e girmiş bir migration bir daha yerinde
değiştirilmez, `0005` açılır.
