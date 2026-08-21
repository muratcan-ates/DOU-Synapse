# Gold set biçimi

İki dosya var ve **asla karışmazlar**:

| Dosya | Ne için | Metrik raporlanır mı |
|---|---|---|
| `calibration.json` | Eşik ayarı (T043) | **Hayır** |
| `holdout.json` | Metriklerin ölçüldüğü set (T044-T047) | **Evet** |

Ayrım projenin akademik omurgasıdır: eşik holdout'ta ayarlanırsa "yani ölçtüğünüz
sette ayar yaptınız" denir ve ölçüm bölümünün tamamı düşer (Anayasa III).
`verify_gold_set.py` her koşudan önce id ve normalize edilmiş soru metni üzerinden
kesişim arar.

## Kayıt biçimi

```json
{
  "id": "H-001",
  "question": "Bir süreç hangi durumda 'blocked' durumuna geçer?",
  "category": "direct",
  "expected_sources": [{ "file_name": "01-processes.pdf", "page_number": 1 }],
  "expected_chunk_ids": [],
  "expected_behavior": "answered",
  "notes": "Beklenen cevabın çekirdeği — insan doğrulaması için."
}
```

| Alan | Zorunlu | Açıklama |
|---|---|---|
| `id` | evet | Set içinde tekil. Kalibrasyon `C-`, holdout `H-` önekli |
| `question` | evet | Kullanıcının soracağı metin, birebir |
| `category` | evet | `direct` · `multi_chunk` · `technical_term` · `out_of_scope` · `injection` · `code_review` · `socratic_leak` |
| `expected_behavior` | evet | `answered` · `insufficient_context` · `out_of_scope` · `ignore_injection` · `no_leak` |
| `expected_sources` | `answered` ise | Beklenen kaynaklar (aşağıya bakınız) |
| `expected_chunk_ids` | — | **Her zaman boş.** Gerekçe aşağıda |
| `question_type` | `code_review` ise | `code_trace` \| `bug_hunt` |
| `pattern_family` | `injection` ise | Kalıp ailesi: `direct_override`, `role_change`, `language_switch`, `in_document_instruction`, `encoded_instruction`, … |
| `leak_vector` | `socratic_leak` ise | `unfenced_code`, `pseudocode`, `verbal_solution`, `persistent_student`, … |
| `r2_case_ref` | — | R2'nin `evaluation/injection/cases.json` kaydına referans; birleştirmede doldurulur |
| `notes` | — | Beklenen cevabın çekirdeği; insan doğrulamasının dayanağı |

`expected_behavior` `answered` değilse `expected_sources` **boş olmalıdır** —
reddedilmesi beklenen bir sorunun beklenen kaynağı olmaz. Doğrulayıcı bunu zorlar.

## `expected_sources` — kalıcı kimlik

`chunks.id` bir UUID'dir ve **her ingest'te `gen_random_uuid()` ile yeniden
üretilir.** Gold set'e elle UUID yazılırsa set bir sonraki yüklemede sessizce kopar
ve bunu ancak metrikler sıfırlanınca fark edersin. Bu yüzden kalıcı kimlik
`(file_name, konum)` çiftidir; chunk id'leri koşu anında çözülür.

Daraltma alanları (hepsi opsiyonel, birlikte kullanılabilir):

| Alan | Ne zaman |
|---|---|
| `page_number` | PDF |
| `slide_number` | PPTX |
| `section_title` | Markdown bölümü |
| `text_contains` | Chunk metninde birebir geçmesi beklenen çapa |

**Hiçbiri verilmezse eşleşme dosya düzeyindedir**: o dosyanın herhangi bir chunk'ı
isabet sayılır. Kod dosyalarında (`producer_consumer.py`, `fork_example.c`) bilinçli
tercih budur — kod chunk'larının sayfa numarası yoktur ve `section_title`'ları
chunking'in küçük blok birleştirmesiyle kayabilir (`chunking.py`). Dosya düzeyi
eşleşme, kırılgan bir eşleşmeye kıyasla daha az bilgi verir ama **yanlış bilgi
vermez.**

Bir sayfa birden çok chunk'a bölünmüş olabilir; sayfadaki chunk'lardan **herhangi
biri** isabet sayılır. Bu, `evaluate.py` için de geçerlidir.

## Recall hangi sorularda ölçülür

Yalnız `direct`, `multi_chunk`, `technical_term`, `code_review` kategorilerinde ve
yalnız `expected_sources` doluysa. `out_of_scope`/`injection`/`socratic_leak`
sorularının beklenen kaynağı yoktur; Recall'a katılırlarsa metriği yapay olarak
düşürürler. Bu ayrım `goldset.RETRIEVAL_CATEGORIES` içinde tek yerde tanımlıdır.

## Doğrulama

```bash
cd apps/api && uv run python ../../evaluation/verify_gold_set.py
```

Üç şeyi ayrı ayrı denetler: yapısal bütünlük, kalibrasyon-holdout ayrıklığı, ve her
`expected_sources` girdisinin materyalde gerçekten karşılığı olup olmadığı. Üçüncüsü
materyali **üretim ayrıştırıcısıyla** (`app.modules.ingestion.parsers.parse`) okur,
yani sayfa numaraları ingest'in gerçekten üreteceği numaralardır — tahmin değil.

İngest sonrası gerçek korpusa karşı da doğrulanabilir:

```bash
cd apps/api && uv run python ../../evaluation/verify_gold_set.py --db --course-id <uuid>
```

İkisi farklı soruları yanıtlar: ilki ingest'in ne **üreteceğini**, ikincisi neyin
gerçekten **üretildiğini** doğrular. Dosya hiç yüklenmemişse veya işleme yarıda
kalmışsa yalnız ikincisi yakalar.

## İnsan doğrulaması — atlanamaz

Soruların taslağı asistanla üretilebilir, ama `expected_sources` eşlemesinin
**içerik** doğrulaması insan işidir (koordinasyon §8). Doğrulayıcı sayfanın var
olduğunu kanıtlar; **o sayfanın gerçekten o sorunun cevabını içerdiğini kanıtlamaz.**
Her iki dosyanın `verification` bloğunda bu ayrım kayıtlıdır ve doğrulama
tamamlandığında tarihiyle güncellenir.
