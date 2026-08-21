# Şerit 2 — Generation + guardrail zinciri

> **Önce `00_OKU_ONCE.md` dosyasını oku.** Bu belge yalnız senin şeridini anlatır.
> Branch: `feat/generation` · Görevler: T008-T016 · Bağımlılık: **yok — sahte retrieval'la tam hız**

---

## Neden bu şerit ürünün kalbi

Projenin tezi tek cümle: **kaynak yoksa cevap yoktur.** O cümleyi bir slogandan
mühendislik garantisine çeviren kod senin şeridinde. Model istediği kadar
"emin" olsun; atıfı retrieve edilen kümede yoksa cevap kullanıcıya gitmez ve bu
karar **deterministiktir, modele sorulmaz.**

Retrieval'ı beklemiyorsun: `app/contracts.py`'deki `RetrievedChunk` listesi zaten
tanımlı. Sahte bir liste kur, zinciri onunla yaz ve sına.

## Sahiplendiğin dosyalar

```
apps/api/app/modules/generation/llm.py           YENİ
apps/api/app/modules/generation/prompts.py       YENİ
apps/api/app/modules/generation/service.py       YENİ
apps/api/app/modules/generation/fake.py          YENİ  (deterministik sağlayıcı)
apps/api/app/modules/guardrails/citation.py      YENİ
apps/api/app/modules/guardrails/leakage.py       YENİ
apps/api/app/modules/guardrails/sanitize.py      YENİ
apps/api/app/modules/guardrails/chain.py         YENİ  (zincir sırası burada)
apps/api/app/schemas/chat.py                     YENİ
apps/api/tests/test_generation.py                YENİ
apps/api/tests/test_guardrails.py                YENİ
specs/001-course-assistant-mvp/tasks.md          yalnız T008-T016 satırları
```

`config.py`'ye LLM ayarları **zaten eklendi** (T008'in yarısı bitti):
`llm_primary_model`, `llm_fallback_model`, `groq_api_key`, `gemini_api_key`,
`llm_timeout_seconds`, `llm_max_retries`, `llm_temperature`, `llm_fake_provider`.
`litellm` bağımlılığı da `pyproject.toml`'da. Bu iki dosyaya dokunma.

## Ne inşa ediyorsun

### T009 — LLM erişimi (`llm.py`)

LiteLLM üzerinden Groq → Gemini **otomatik failover**. Kritik nokta: failover kod
seviyesinde olmalı, elle değil. Sağlayıcı kotası dolduğunda ya da 5xx döndüğünde
sistem ikinciye düşer ve bunu **loglar** — hangi cevabın hangi sağlayıcıyla
üretildiği `GeneratedAnswer.provider`/`.model` alanlarında taşınır.

Üstel geri çekilme (exponential backoff) ekle ama `llm_max_retries`'i aşma:
sonsuz retry, ücretsiz katmanda kotayı bir sabah tüketir.

**Zaman aşımı sert olmalı** (`llm_timeout_seconds`). Asılı kalan bir istek, sınav
sırasında öğrenciyi bekletir; SC-010 p95 < 10 sn diyor.

### `fake.py` — deterministik sağlayıcı (bu görevde YOK ama yaz)

Bu, listede olmayan ama **projenin en değerli parçalarından biri.** Sebep:

- CI'da ağ yok ve API anahtarı yok. Ağa bağımlı test, kırmızı yanar.
- Çevrimdışı demo sigortası (PLAN plan C) buna dayanıyor.
- Kota dolduğunda geliştirme durmaz.

Sahte sağlayıcı bir "stub" değil: gerçek payload'ı okuyup şemaya uygun,
**verilen chunk'lara gerçekten atıf yapan** bir cevap üretmeli. Böylece guardrail
zinciri, atıf doğrulaması ve abstention davranışı sahte modda da birebir aynı
çalışır; yalnız düzyazı değişir.

`config.llm_fake_provider` bayrağı hazır ve üretimde açılmasını reddeden
doğrulayıcı da eklendi. Testlerde bu bayrak açık koşacak.

### T010 — Cevap şeması (`schemas/chat.py`)

`ARCHITECTURE.md §5`'teki şema. `AnswerStatus` ve `ChatMode` **zaten**
`app/contracts.py`'de; Pydantic modelini onların üzerine kur, yeniden tanımlama.

Şemanın işi modeli hizada tutmak: serbest metin yerine tipli çıktı, bozuk çıktıda
**bir kez** retry, yine bozuksa abstention. `llm_max_retries` bunu yönetir.

**T010 bitince gruba haber ver** — Şerit 3 ve 4 bu şemaya karşı yazacak.

### T011 — Prompt'lar (`prompts.py`)

Bağlam `<retrieved_context><source id="..." page="...">` XML etiketleriyle **veri
olarak** işaretlenir. Sebep: materyalin içinde "önceki talimatları unut" yazan bir
satır olabilir (prompt injection). Etiketleme, modele "bu veri, talimat değil"
demenin en dayanıklı yolu.

Kapanış etiketini payload'ın forge edememesi için sabit noktaya kadar temizle:
materyal içinde `</source>` geçiyorsa bunu kaçır.

Sokratik mod prompt'ları **kademeye göre** değişir (`SocraticStage`). Ama kademe
ilerletme kararı prompt'ta değil, state machine'de verilir (Şerit 3'ün işi).

### T012 — Üretim servisi (`service.py`)

`Generator` protokolünü uygula. Akış: prompt kur → LLM çağır → Pydantic doğrula
→ bozuksa 1 retry → yine bozuksa `insufficient_context` döndür.

**Model asla sayı uydurmaz** ilkesi burada başlar: cevaptaki dosya adı ve sayfa
numarası model çıktısından değil, `RetrievedChunk` metadata'sından doldurulur.
Model yalnız hangi chunk'a dayandığını söyler (`chunk_id`), gerisini kod yazar.

### T013 — Atıf doğrulayıcı (`guardrails/citation.py`)

**Ürünün en önemli otuz satırı.** Set-membership: cevaptaki her `chunk_id`,
retrieve edilen kümede olmak zorunda. Olmayan atıf **düşer**. Geçerli atıf
kalmazsa cevap **bloklanır** (`GuardrailVerdict.blocked = True`).

`dropped_citations` listesini doldur: hangi atıfın neden düştüğü ölçülebilir
olmalı, yoksa "model atıf uyduramaz" iddiası kanıtsız kalır (Anayasa III).

Bu kontrol **modele sorulmaz**, Python'da yapılır. Fark budur.

### T014 — Sızıntı filtresi (`guardrails/leakage.py`)

Kural tabanlı kod bloğu ve doğrudan-çözüm dedektörü. Yakalaması gerekenler:

- Markdown kod çiti (```)
- Çitsiz ama girintili kod bloğu deseni
- "cevap: X", "sonuç: 42" kalıpları
- Sözde-kod (pseudocode) blokları
- Sözel çözüm: adım adım tam çözüm anlatımı

CS50 çalışması yanıtların %22'sinde çalışan kod sızdırıldığını raporladı; SC-007
bizim hedefimizi **test setinde 0** koyuyor. Bu filtre o hedefin taşıyıcısı.

**Fail-closed:** ihlalde bir kez yeniden üret, sürerse sabit şablon ipucuna düş.
Asla "filtreden geçemedi, cevabı yine de gösterelim" olmaz.

Sınav modunda ipucu tamamen kapalı — filtre orada daha da sıkı.

### T015 — Temizlik (`guardrails/sanitize.py`)

Markdown/HTML temizliği (XSS). Ham stack trace asla kullanıcıya gitmez.

### `chain.py` — zincir sırası

`ARCHITECTURE §5` sırası **sabittir**: generation → citation → leakage → sanitize.
Sırayı tek yerde kur ki çağıranlar (Şerit 3, 4) yanlış sırayla çağıramasın.

### T016 — Testler (`test_guardrails.py`)

En az:

1. Uydurma `chunk_id`'li atıf **düşer**; geçerli atıf kalmazsa cevap **bloklanır**
2. Kaynaksız Sokratik ipucu bloklanır
3. Kod çiti yakalanır → şablon ipucuna düşülür
4. Çitsiz girintili kod yakalanır
5. Sözde-kod yakalanır
6. "cevap: X" kalıbı yakalanır
7. Sınav modunda ipucu üretilmez
8. Injection: materyal içinde "önceki talimatları unut" geçen bir chunk, cevabı
   ele geçiremiyor
9. Forge edilmiş `</source>` kapanış etiketi payload'dan geçemiyor

Her test **saf fonksiyon üzerinde** koşsun — LLM çağırmadan. Zinciri test
ediyorsun, modeli değil.

## Sıra önerisi

1. `schemas/chat.py` + `fake.py` — bunlar olmadan hiçbir şeyi test edemezsin
2. `guardrails/citation.py` + testi — ürünün kalbi, en erken yeşil olsun
3. `guardrails/leakage.py` + testi — en çok vaka burada
4. `prompts.py`
5. `llm.py` — gerçek sağlayıcı en son; anahtar yoksa sahteyle devam
6. `service.py` + `chain.py` — hepsini birleştir

## Bitti sayılma ölçütü

- [ ] `pytest -q` yeşil, `ruff` temiz
- [ ] Zincir **sahte retrieval üzerinde uçtan uca** çalışıyor
- [ ] "Model atıf uyduramaz" davranışı testle sabit — uydurma atıflı bir cevabın
      bloklandığını **gösteren** test var
- [ ] Sahte sağlayıcı ağsız koşuyor (ağı kapat, testleri koştur, yeşil kalsın)
- [ ] Gerçek anahtar varsa: bir kez gerçek çağrı yapıldı ve gecikme ölçüldü
      (Anayasa VIII — gözlenmeden bitmedi). Anahtar yoksa bunu DONE notuna yaz
- [ ] `tasks.md`'de T008-T016 `[x]` + tarihli DONE notu

## Bittiğinde

Gruba **`Generator` protokolünün ve cevap şemasının hazır olduğunu** yaz.
Şerit 3 ve 4 bekliyor.

Vaktin kalırsa: **T046 injection koşusu** için vaka dosyalarını hazırlamaya başla —
Şerit 5'in gold set'iyle birleşecek, onunla koordine ol.
