# Şerit 4 — şema kararları ve gruba notlar

> 9 Ağustos 2026 · Branch `feat/questions-exams` · Görevler T029-T033 (+T037)
> `04_SORU_SINAV.md` "Önce yapılacak: üç şema kararı" maddesinin cevabı.

Kararların ortak kısıtı şu: **hiçbiri migration açmıyor.** `0005` numarası Şerit
5'te ve `main`'e girmiş bir migration yerinde değiştirilemez (00_OKU_ONCE §8). Bu
yüzden her karar, "bugün `0004` ile ne yapılabilir" ile "0005 gelirse ne
sağlamlaşır" olarak ikiye ayrıldı. İkinci sütun gruptan istenenler listesindedir.

---

## Karar 1 — `answers` UPDATE politikası: **eklenmeyecek, cevap satırı yazılıp bitirilir**

Handoff üç seçenek sunuyordu: (a) öğrenciye kendi cevabı için UPDATE, (b) puanlama
yazımını `SECURITY DEFINER` fonksiyona taşımak, (c) `dou_worker` rolüne vermek.
Önerilen (b) idi.

**Seçilen: hiçbiri.** Cevap satırı **tek seferde, puanıyla birlikte** yazılır
(write-once). Puanlama cevabın kaydedildiği anda koşar; `/finish` yalnızca okur ve
toplar.

Gerekçe:

1. `0004`'te `answers` tablosunun UPDATE politikası **yok** ve tablo FORCE RLS
   taşıyor. Yani bugün `dou_app` bir cevap satırını hiçbir şekilde güncelleyemez.
   Bu bir eksik değil, bedava bir güvenlik özelliği: **öğrenci kendi puanını
   sonradan değiştiremez, çünkü değiştirebilecek bir yol veritabanında yok.**
   (b) şıkkı aynı garantiyi bir fonksiyon katmanı ekleyerek kurardı; hiç yazmamak
   daha ucuz ve daha az kod.
2. "Geri bildirim sınav sonunda" kuralı puanın *ne zaman hesaplandığıyla* değil,
   *ne zaman gösterildiğiyle* ilgilidir. `exam` modunda cevap ucu yalnızca
   `{"recorded": true}` döner; puan satıra yazılır ama `/finish`'e kadar
   gösterilmez. Kısıt sunucuda, tek yerde.
3. `UNIQUE (session_id, question_id)` zaten "soru başına tek deneme"yi veritabanı
   seviyesinde zorluyor. Write-once bu kısıtla aynı yönde; UPDATE eklemek onu
   delerdi.

**Bedeli — dürüstçe:** LLM değerlendirmesi anlık olarak başarısız olursa (açık uçlu
soruda sağlayıcı hatası) o cevap `score=NULL`, `feedback={"status":"failed"}` ile
kalır ve **yeniden puanlanamaz**; `/finish` onu "değerlendirilemedi" olarak
raporlar ve **puana katmaz**. Bu FR-020'ye uygundur (uydurma puan gösterilmez) ama
öğrenci o sorudan puan alamaz. Yeniden puanlama isteniyorsa `0005`'te
`answers_self_update` yerine bir `app.grade_answer()` SECURITY DEFINER fonksiyonu
gerekir — gruptan istenenler listesinde.

## Karar 2 — Öğrencinin kendi `score`/`expires_at`'ini yazabilmesi: **uygulama katmanında kapatıldı, RLS'te açık kaldı**

`exam_sessions_self_update` sütun kısıtsız. RLS yapısal olarak sütun kısıtı veremez;
gerçek çözüm kolon bazlı GRANT, BEFORE UPDATE trigger ya da `app.finish_exam()`
SECURITY DEFINER fonksiyonudur. **Üçü de migration ister, üçü de bugün yapılamaz.**

Bugün yapılan iki şey, açığın **somut sömürüsünü** kapatıyor:

1. **Süre uzatma daraltıldı** (kapatılmadı — aşağıdaki sınıra dikkat). Kalan süre
   asla ham `expires_at`'ten okunmuyor:

   ```
   etkin_bitiş = min(expires_at, started_at + EXAM_DURATION_MINUTES)
   ```

   Öğrenci satırdaki `expires_at`'i doğrudan SQL ile bir güne çekse bile sunucu
   `started_at + 20dk`'ya kırpar.

   **Sınır, açıkça:** `started_at` de aynı politikayla yazılabilir. İkisini birden
   ileri atan biri süreyi yine uzatır; kırpma yalnız tek sütunlu kurcalamayı
   kapatır. Tam kapanış `0005`'teki kolon bazlı GRANT'tir. Bunu "çözüldü" diye
   yazmıyorum çünkü çözülmedi (Anayasa III).

   **Bugünkü gerçek risk düzeyi:** API'de `exam_sessions`'ın `started_at` ya da
   `expires_at` sütununa yazan **hiçbir uç yok** — `/finish` yalnız `finished_at`
   ve `score` yazar. Yani sömürü HTTP üzerinden ulaşılabilir değil; doğrudan
   veritabanı bağlantısı ister. Bu bir savunma derinliği açığıdır, canlı bir
   istismar yolu değil.

2. **Puan uydurma kapandı.** `exam_sessions.score` **hiçbir yanıtta okunmuyor.**
   Gösterilen puan her istekte `answers` satırlarından yeniden hesaplanıyor —
   ve `answers` write-once (Karar 1), yani öğrencinin yazamayacağı tek yer orası.
   Sütun yine de yazılıyor; **kaydın kendisi olarak, Şerit 5'in analitiği için.**

**Şerit 5'e uyarı:** `exam_sessions.score` sütunu bugün *tavsiye niteliğinde*.
Analitikte ona güveneceksen `0005` sütun kilidini bekle ya da puanı `answers`'tan
türet — API'nin yaptığı bu.

Ayrıca zaman kaynağı: kalan süre hesabında **hiçbir yerde Python saati
kullanılmıyor.** Her istekte `SELECT now()` ile veritabanı saati okunur; işlem
içinde sabit olduğu için aynı istekteki iki karşılaştırma tutarlıdır.

## Karar 3 — `questions.source_chunk_id ON DELETE RESTRICT`: **doğrulandı, düzeltmesi şeridimin dışında**

`DELETE /courses/{id}/documents/{doc_id}` `main`'de canlı. Belge silinince chunk'lar
CASCADE ile düşüyor; o chunk'tan üretilmiş soru varsa `RESTRICT` patlıyor ve uç
`IntegrityError` yakalamadığı için kullanıcı **409 yerine 500** görüyor. T029 havuza
soru yazan ilk yol olduğu için bu hata bugünden itibaren **ulaşılabilir**.

Handoff iki yol veriyordu; **(b) seçildi**: `delete_document` açık `409` döndürsün +
`questions`'a eğitmen DELETE politikası eklensin. (a) şıkkı (`SET NULL` + nullable)
reddedildi çünkü `source_chunk_id` "Kaynak yoksa cevap yok"un ölçme ayağıdır;
nullable yapmak, kaynağı olmayan sorunun havuzda kalmasına izin vermek demektir —
alıntıyı payload'a kopyalamak bunu telafi etmez, çünkü kopyalanan alıntı artık
hiçbir chunk'a karşı doğrulanamaz (Anayasa I set-membership'i kaybeder).

**Ama ikisi de benim dosyalarım değil:** `documents.py` Şerit 4'ün listesinde yok,
DELETE politikası migration ister. İkisi de gruptan istenenler listesinde, hazır
yamayla.

**Bu arada ne yapılıyor:** hiçbir şey gizlenmiyor. Havuzda sorusu olan bir belgeyi
silmek bugün 500 döndürür. Bu bir Şerit 4 kusuru değil ama Şerit 4 tetikliyor, o
yüzden burada yazılı.

## Karar 4 — `short_answer` (FR-036): **`open`'ın alt türü, beşinci enum değeri değil**

Hocanın istediği üç biçim — test / klasik / kısa cevap — şöyle karşılanıyor:

| Hocanın dediği | `question_type` | `payload.format` |
|---|---|---|
| test | `mcq` | — |
| klasik | `open` | `essay` (varsayılan) |
| kısa cevap | `open` | `short_answer` |

Gerekçe (handoff "kararını gerekçelendir" diyor):

1. Beşinci enum değeri `question_type`'ı değiştirir → migration → `0005` → başka
   şeridin numarası → bugün yapılamaz. Alt tür `payload` içinde bir alandır ve
   migration istemez. Bu tek başına yeterli sebep değil ama eşitliği bozar.
2. **Asıl sebep: değerlendirme mantığındaki fark zaten `payload`'a bakıyor.**
   Klasik cevap `rubric` + `key_points` ile LLM'e değerlendirtilir; kısa cevap
   `accepted_answers` listesiyle **deterministik** eşleştirilir. İki yolu ayıran
   şey sorunun tipi değil, payload'ında hangi anahtarın dolu olduğudur. `format`
   alanı bu ayrımı açıkça isimlendirir; ayrı bir enum değeri aynı bilgiyi iki
   yerde tutardı (Anayasa XI).
3. Kısa cevabın deterministik olması bir kazanç, kayıp değil: puanı LLM vermez,
   dolayısıyla "ölçmeden iddia etme" açısından savunması kolaydır.

Kısa cevap eşleştirmesi Türkçeye göre normalize edilir: noktalama atılır, boşluk
sadeleşir ve **`upper()` kullanılmadan** `İ→i`, `I→ı` eşlemesiyle küçültülür
(Anayasa V — `uppercase` dönüşümü i/İ'yi bozar). Öğrenci cevabı kabul edilen
karşılıklardan birini içeriyorsa 100, aksi halde 0; "neden yanlış" kaynak
chunk'tan gelir.

---

## RLS kanıtı — iki katman ayrı ayrı sınandı

Anayasa II "RLS'in gerçekten tetiklendiği, politika bilerek bozularak kanıtlanır"
diyor. T033 vaka 2 için bu üç adımda yapıldı. Temiz bir veritabanına migration'lar
uygulandı, bir ders + bir eğitmen + bir öğrenci + bir **taslak** soru kuruldu.

**1. Politika sağlamken, uygulama katmanı hiç devrede değilken.** Ham SQL:
`SET ROLE dou_app` + öğrencinin `app.current_user_id`'si + `SELECT count(*) FROM questions`.

```
1. POLITIKA SAGLAM  · ogrenci kac taslak goruyor -> 0
```

**2. Politika bozulduğunda.** `questions_read` düşürülüp `AND status = 'approved'`
olmadan yeniden kuruldu. Aynı sorgu:

```
2. POLITIKA BOZUK   · ogrenci kac taslak goruyor -> 1
```

Yani `test_rls_katmani_tek_basina_da_taslagi_gizler` bu durumda **kırmızı yanar**.
Testin yeşilliği politikadan geliyor, tesadüften değil.

**3. Politika bozuk bırakılıp gerçek uygulama aynı veritabanına bağlandığında.**
Uygulama katmanının tek başına tuttuğunun kontrolü:

```
3. RLS BOZUK, UYGULAMA KATMANI ACIK · ogrenci kac soru goruyor -> 0 (HTTP 200)
3. RLS BOZUK, UYGULAMA KATMANI ACIK · egitmen kac soru goruyor -> 1 (HTTP 200)
4. RLS BOZUK, ogrenci ?status=draft ile istiyor -> 0
```

İki katman da tek başına yeterli; ikisi birden "iki katmanlı izolasyon"dur. Kanıt
veritabanı üretilebilir olduğu için kurulum betiği kalıcı olarak saklanmadı, ama
adımlar yukarıda birebir yazılı.

---

## Gruptan istenenler

Aşağıdakiler Şerit 4'ün dışında. Hiçbiri Şerit 4'ü bloke etmiyor — hepsinin
uygulama katmanında bir karşılığı zaten yazıldı — ama yapısal kapanış bunları
bekliyor.

### 1. Lider / `documents.py` (Karar 3, tek dosya, migration istemez)

`delete_document` gövdesinde `session.flush()` çağrısını sar:

```python
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "Bu belgeden üretilmiş sorular havuzda olduğu için belge silinemiyor. "
            "Önce ilgili soruları kaldırın."
        ) from exc
```

(`from sqlalchemy.exc import IntegrityError` ve `ConflictError` importu gerekir.)

### 2. `0005` migration (Şerit 5'in numarası) — üç madde

```sql
-- (a) Karar 3'ün ikinci yarısı: eğitmen havuzdan soru silebilsin.
CREATE POLICY questions_instructor_delete ON questions
    FOR DELETE USING (app.is_instructor(course_id));

-- (b) Karar 2: öğrenci kendi oturumunun score/expires_at'ini yazamasın.
--     RLS sütun kısıtı veremediği için kolon bazlı GRANT:
REVOKE UPDATE ON exam_sessions FROM dou_app;
GRANT  UPDATE (finished_at) ON exam_sessions TO dou_app;
--     (finish akışında yazılan tek sütun budur; score artık answers'tan türetiliyor.)

-- (c) Karar 1'in bedeli: başarısız LLM değerlendirmesinin yeniden denenebilmesi.
--     İstenirse; istenmezse (c) hiç yapılmasın, bugünkü davranış FR-020 uyumlu.
CREATE FUNCTION app.grade_answer(...) SECURITY DEFINER ...
```

(b)'nin yan etkisi: `exam_sessions.score` API tarafından yazılamaz hâle gelir.
Bugünkü kod zaten puanı `answers`'tan türetiyor, dolayısıyla kırılan bir şey yok —
ama Şerit 5 analitiği o sütunu okuyorsa önce haberleşelim.

### 3. Şerit 1 (retrieval) ve Şerit 2 (generation) — iki imza

Soru üretimi (T029) iki modülü de kullanıyor ve ikisi de henüz `main`'de değil.
`contracts.py`'deki `Retriever` protokolü doğrudan kullanıldı, **değiştirilmedi**.
Ama `Generator` protokolü soru üretimine uymuyor: `generate(...) -> GeneratedAnswer`
bir *sohbet cevabı* üretir; soru üretimi ve açık uçlu değerlendirme ise **şemalı
JSON** ister.

Bu yüzden `question_gen.py` içinde dar bir protokol tanımlandı:

```python
class StructuredCompletion(Protocol):
    """Şemalı JSON isteyen çağrılar için tek yüzey. Ham metin döner; doğrulama çağırana ait."""
    async def complete(self, *, system: str, user: str) -> str: ...
```

**Şerit 2'den istenen:** LLM servisiniz bu imzayı karşılayan bir sınıf/fonksiyon
dışa versin (litellm sarmalayıcınızın üzerine 5 satır). O gelince
`app/api/questions.py`'deki `get_structured_completion()` ve
`get_retriever()` sağlayıcıları tek satırla gerçek uygulamaya bağlanır; sahte
uygulamalar testlerde kalır.

**Bugünkü davranış:** ikisi de bağlı değilken `POST /questions/generate`
**503 + Türkçe mesaj** döner (fail-closed; sahte soru üretilmez). Havuz uçları,
puanlama ve sınav akışının tamamı bu bağımlılıktan **etkilenmez** ve bugün çalışır.

`contracts.py`'ye bir alan eklenmesi gerekmedi.

### 4. Uç adlandırma sapması — bilinçli

`tasks.md` T030 `PATCH .../approve|reject` diyor; `04_SORU_SINAV.md` `POST` diyor.
Handoff daha yeni ve daha ayrıntılı olduğu için **`POST` uygulandı**. Frontend bu
uçları bağlarken `POST` beklesin.
