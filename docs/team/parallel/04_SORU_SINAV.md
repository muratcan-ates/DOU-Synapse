# Şerit 4 — Soru üretimi + sınav provası

> **Önce `00_OKU_ONCE.md` dosyasını oku.** Bu belge yalnız senin şeridini anlatır.
> Branch: `feat/questions-exams` · Görevler: T029-T033
> Bağımlılık: Şerit 2'nin **imzası** (gövdesi değil) · Şema: **`0004` zaten hazır**

---

## Neden bu şerit danışmanın en çok istediği şey

6 Ağustos toplantısında hoca ısrarla şunu söyledi: *"Yapay zeka müfredattan,
kitaptan başlayıp örnek sorular üretsin; öğrenciyi cevabı vermeden yönlendirsin."*
Ve çerçeveyi eğitmenin kurmasını istedi: **test / klasik / kısa cevap** biçimini
eğitmen seçsin, isterse bir-iki örnek soru versin, sistem o üslupta devam etsin.

Senin şeridin bu isteğin tamamı. Ve pazarlıksız bir kural var: **eğitmen
onaylamadan hiçbir soru öğrenciye görünmez.**

Şema hazır: `0004_assessment.sql` `questions` tablosunu `status`
(draft|approved|rejected), `reviewed_by`, `reviewed_at` ile kurdu, RLS de
öğrencinin yalnız `approved` görmesini zorluyor. Sen üstüne uç yazıyorsun.

## Sahiplendiğin dosyalar

```
apps/api/app/modules/assessment/question_gen.py  YENİ
apps/api/app/modules/assessment/grading.py       YENİ
apps/api/app/api/questions.py                    MEVCUT — genişlet (topics ucu var)
apps/api/app/api/exams.py                        iskelet hazır, gövdeyi sen yaz
apps/api/app/schemas/assessment.py               MEVCUT — genişlet
apps/api/tests/test_assessment.py                MEVCUT — genişlet
apps/api/tests/test_exams.py                     YENİ
specs/001-course-assistant-mvp/tasks.md          yalnız T029-T033 satırları
```

`app/api/exams.py` **zaten var ve `main.py`'ye kayıtlı**. `main.py`'ye dokunma.

## Önce yapılacak: üç şema kararı

Bunlar `0004`'ten sonra ortaya çıkan açıklar. **Kod yazmadan önce karar ver ve
gruba yaz** — üçü de `0005` migration gerektirebilir (numara Şerit 5'te, ona sor).

### Karar 1 — `answers` tablosunda UPDATE politikası yok

Puanlama ve ipucu sayacı cevap satırına yazmak zorunda ama bu yol tanımsız.
Seçenekler: (a) öğrenciye kendi cevabı için UPDATE politikası ver, (b) puanlama
yazımını `SECURITY DEFINER` fonksiyona taşı, (c) `dou_worker` rolüne ver.

**Öneri: (b).** Öğrenci kendi puanını yazabilmemeli.

### Karar 2 — Öğrenci kendi puanını yazabiliyor

`exam_sessions_self_update` ve `mastery_self_update` sütun kısıtsız: öğrenci kendi
`score`'unu ve `expires_at`'ini (sınav süresi uzatma) doğrudan yazabilir. RLS
yapısal olarak sütun kısıtı veremez; çözüm kolon bazlı GRANT, BEFORE UPDATE
trigger ya da `app.finish_exam()` gibi bir SECURITY DEFINER fonksiyon.

**Bu karar T032'yi yazmadan önce verilmeli** — sonra vermek, yazdığın kodu
yeniden yazmak demek.

### Karar 3 — `questions.source_chunk_id ON DELETE RESTRICT` belge silmeyi kilitliyor

`DELETE /courses/{id}/documents/{doc_id}` `main`'de **zaten canlı**. Belge silme
chunk'ları CASCADE ile düşürüyor; o chunk'tan üretilmiş soru varsa RESTRICT
patlıyor ve uç IntegrityError yakalamadığı için kullanıcı **409 yerine 500**
görüyor.

Bugün ulaşılamaz çünkü soru yazan yol yok. **Sen T029'u yazdığın an ulaşılabilir
oluyor.** İki yol: (a) `SET NULL` + nullable yap ve kaynak bilgisini payload'a
kopyalanan alıntıyla telafi et, (b) `delete_document`'te açık 409 `ConflictError`
+ `questions`'a eğitmen DELETE politikası.

Not: `documents.py` senin listende değil. (b)'yi seçersen gruba yaz, lider halleder.

## Ne inşa ediyorsun

### T029 — Soru üretici (`question_gen.py`)

Dört tip: `mcq`, `open`, `code_trace`, `bug_hunt`. Hocanın istediği **kısa cevap**
biçimi için `FR-036` eklendi (RAD'da) — `short_answer`'ı beşinci tip olarak mı,
`open`'ın alt türü olarak mı ekleyeceğine karar ver. Beşinci tip `question_type`
enum'unu değiştirir, yani migration gerektirir; alt tür `payload` içinde bir alan
olur ve migration gerektirmez. **İkincisi daha ucuz, ama değerlendirme mantığı
farklı** (kısa cevapta anahtar kelime eşleştirme, klasikte rubrik) — kararını
gerekçelendir.

Eğitmen çerçevesi girdi olarak alınır: `topic_id`, `format`, opsiyonel
`example_questions`. Sistem materyalden **o biçimde ve o üslupta** üretir.

**Fail-closed kural:** model, retrieve edilmemiş bir chunk'a atıf yaparsa soru
havuza **hiç yazılmaz**. `source_chunk_id` uydurulamaz.

Şemaya uymayan çıktı bir kez yeniden denenir; yine uymazsa o soru atlanır
(SC-009: şema geçerliliği ≥ %98).

Üretim `question_generation_batch` (varsayılan 5) kadar soruyu bir turda üretir.

### T030 — Soru uçlarının kalanı (`api/questions.py`)

`topics` uçları **zaten var**. Ekleyeceklerin:

- `POST /courses/{id}/questions/generate` — üretimi tetikler (eğitmen)
- `GET /courses/{id}/questions` — eğitmen hepsini, öğrenci **yalnız approved**
- `POST /courses/{id}/questions/{qid}/approve` — `status`, `reviewed_by`, `reviewed_at`
- `POST /courses/{id}/questions/{qid}/reject`

`questions_reviewed_consistency` CHECK'i `reviewed_by`/`reviewed_at` alanlarını
zorunlu tutuyor — onaylarken ikisini de yaz, yoksa kısıt patlar.

**Bu uçların LLM'e ihtiyacı yok** (üretim hariç). Şerit 2'yi beklemeden yazabilir
ve test edebilirsin — fixture'da elle `INSERT` ederek.

### T031 — Puanlama (`grading.py`)

**MCQ deterministiktir, LLM gerekmez.** `payload.answer_key` ile karşılaştır.
"Neden yanlış": `distractor_sources` üzerinden çeldiricinin çeliştiği kaynak
bölümünü göster (FR-021).

**Açık uçlu değerlendirme LLM'lidir**: rubrik + cevap anahtarı + kaynak parçalar.
Çıktı şemaya uymalı (`GradedAnswer` `app/contracts.py`'de hazır:
`score` 0-100, `missing_points`, `evidence_chunk_id`).

MCQ kısmını önce yaz, hemen yeşil alırsın.

### T032 — Sınav uçları (`api/exams.py`)

- `POST /courses/{id}/exams` — oturum açar
- `GET /courses/{id}/exams/{sid}` — kalan süreyle birlikte durum
- `POST /courses/{id}/exams/{sid}/answers` — cevap kaydeder
- `POST /courses/{id}/exams/{sid}/finish` — puanlar ve bitirir

**Kurallar (spec FR-017, `0004` şeması):**

- **Süre sunucudan hesaplanır**, istemci saatine asla güvenilmez. `expires_at`
  `started_at + exam_duration_minutes` (config'de hazır)
- Sınav modunda **ipucu kapalı**, soru başına **tek deneme**
  (`answers` tablosunda `UNIQUE (session_id, question_id)` bunu DB seviyesinde zorluyor)
- Süre dolunca cevapsız sorular **boş** sayılır (yanlış değil, puana katılmaz)
- Geri bildirim **sınav bitiminde**; practice modunda süresiz + anında geri bildirim
- Oturum açılırken sorular **sabitlenir** (`question_ids`); sonradan onay/red
  başlamış sınavı değiştirmez
- **Boş havuzda sınav reddedilir** — onaylı soru yoksa 409

### T033 — Testler

tasks.md sekiz vaka sayıyor:
1. Şema geçerliliği
2. Draft görünmezliği — öğrenci taslak soruyu **göremez**
3. Exam modunda ipucu reddi
4. Süre dolunca boş cevap davranışı
5. MCQ "neden yanlış"
6. Boş havuzda sınav reddi
7. Oturuma dönüş (bağlantı koparsa kalan süreyle devam)
8. Practice modu

**Vaka 2 kritik:** `0004`'ün en önemli RLS politikası bu ve bugün hiçbir otomatik
testi yok. Politikayı bozup testin kırmızı yandığını da göster.

## Sıra önerisi

1. Üç şema kararını ver, gruba yaz
2. T030'un onay/red uçları — LLM'siz, hızlı yeşil
3. T031 MCQ puanlama — deterministik, hızlı yeşil
4. T032 sınav oturumu iskeleti — süre ve tek deneme
5. T029 soru üretici — Şerit 2 inince ya da sahte `Generator` ile
6. T031 açık uçlu rubrik — en son
7. T033 sekiz vaka

## Bitti sayılma ölçütü

- [ ] `pytest -q` yeşil, `ruff` temiz
- [ ] **Öğrenci taslak soruyu göremiyor** — testle ve psql ile kanıtlı
- [ ] Süre sunucudan hesaplanıyor; istemci saati değiştirilse bile sınav uzamıyor
- [ ] Aynı soruya ikinci cevap 409 alıyor
- [ ] Boş havuzda sınav 409 alıyor
- [ ] Üç şema kararı verildi ve gerekçesi yazıldı
- [ ] OpenAPI sözleşmesi oturumun sonunda yeniden export edildi
- [ ] `tasks.md`'de T029-T033 `[x]` + tarihli DONE notu

## Bittiğinde

Gruba haber ver: **soru havuzu ve sınav uçları hazır.** Lider frontend'i buna
bağlayacak — `apps/web`'e dokunma, oradaki soru havuzu ve sınav ekranları
hazır durumda bekliyor.

Vaktin kalırsa: **T037** mastery entegrasyonu (`exams.py`'de puanlama sonrası
`record_answer` çağrısı). `mastery/service.py` yazılı ve testli, imzası hazır.
