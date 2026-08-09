# Evidence eşiği kalibrasyonu (T043)

**Durum: KOŞULMADI.** Bu belge yöntemi ve kararları kayda geçiriyor; sayılar
kalibrasyon koşusu yapıldığında buraya yazılacak. Aşağıdaki hiçbir alanda tahmin
yoktur (Anayasa III).

**Son güncelleme:** 9 Ağustos 2026

---

## 1. Neyi ayarlıyoruz

`Settings.evidence_threshold` (`apps/api/app/core/config.py`). Retrieval'ın en iyi
sonucu bu eşiğin altında kalırsa sistem cevap üretmez, abstention döner (fail-closed,
Anayasa IV).

Şu anki değer **0.35** ve yanındaki yorum **"KALİBRE EDİLMEMİŞTİR — T043'e kadar bu
sayı hiçbir raporda kullanılamaz"** diyor. O not, kalibrasyon koşusu yapılıp seçilen
değer burada gerekçesiyle yazılana kadar **kalır**.

Değeri `config.py`'de güncelleyecek olan **Şerit 1'dir**, bu şerit değil: dosya onların
ve tek taraflı bir değişiklik ona karşı yazılmış modülleri kırar. Bu şeridin işi
sayıyı ölçmek ve gerekçesiyle bildirmektir.

## 2. Neden ayrı bir kalibrasyon seti (karar, 9 Ağustos)

**Karar: kalibrasyon seti holdout'tan KESİLMEZ, ayrıca yazılır.**

Gerekçe iki katlı:

1. 15 soru holdout'un içinden çıkarılsaydı holdout'un kategori dağılımı (20/10/10/10)
   bozulur ve raporlanan alt küme sayıları düşerdi. `multi_chunk` gibi zaten n≈10 olan
   kategorilerde bu, sayıyı anlamsızlaştırırdı.
2. Ayrı yazılan set, **"ayrı dosya, ayrı zaman, holdout'a hiç bakılmadı"** savunmasını
   somut kılar. Kesilmiş bir sette bu savunma anlatıya dayanır; ayrı dosyada dosya
   tarihlerine ve git geçmişine dayanır.

Kalibrasyon seti holdout'un kategori oranlarını **yansıtır** (6 direct, 3 multi_chunk,
3 technical_term, 3 out_of_scope) ama **aynı soruları içermez**.

## 3. Holdout'a bakılmadı beyanı

**9 Ağustos 2026 itibarıyla holdout seti üzerinde hiçbir ölçüm koşusu yapılmamıştır.**

Bu beyan boş bir söz değil, denetlenebilir:

- `evaluation/results/` klasöründe holdout koşusu yoktur (klasör boştur).
- `evaluate.py` her koşuda kalibrasyon-holdout ayrıklığını denetler ve kesişim
  bulursa koşuyu başlatmaz.
- Holdout koşusu `--threshold-calibrated` bayrağı olmadan koşulduğunda harness
  ekrana "holdout eşik ayarı için KOŞULMAZ" uyarısı basar.

Bu beyan, ilk holdout koşusundan sonra **tarihi ve koşu dosyasıyla** güncellenecektir.

## 4. Yöntem — kalibrasyon koşusu nasıl yapılacak

```bash
cd apps/api
EMBEDDING_PROVIDER=fastembed uv run python ../../evaluation/build_corpus.py \
    --database dou_synapse_eval --recreate --out /tmp/corpus.json

for threshold in 0.20 0.25 0.30 0.35 0.40 0.45 0.50; do
  EVIDENCE_THRESHOLD=$threshold uv run python ../../evaluation/evaluate.py \
      --set calibration --layer e2e --corpus /tmp/corpus.json
done
```

Her eşikte kalibrasyon setinde ölçülecek olan:

| Ölçü | Tanım |
|---|---|
| Doğru ret | `out_of_scope` sorusu reddedildi |
| Yanlış ret | `direct`/`multi_chunk`/`technical_term` sorusu reddedildi |
| Kaçan kapsam dışı | `out_of_scope` sorusu cevaplandı |

**Seçim ölçütü:** yanlış reddi (öğrencinin cevaplanabilir sorusunu geri çevirmek)
kabul edilebilir seviyede tutan en yüksek eşik. İki hata simetrik değildir: kapsam
dışı bir soruyu cevaplamak sistemin merkezi vaadini çiğner, cevaplanabilir bir soruyu
reddetmek ise kullanıcıyı rahatsız eder. Anayasa IV belirsizlikte kapanmayı söyler,
yani eşit maliyette daha yüksek eşik tercih edilir.

**Kapsam dışı ret oranı bu sette RAPORLANMAZ** — yalnız holdout'ta raporlanır.

## 5. Sonuçlar

| Eşik | Doğru ret | Yanlış ret | Kaçan kapsam dışı | Koşu dosyası |
|---|---|---|---|---|
| 0.20 | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | — |
| 0.25 | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | — |
| 0.30 | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | — |
| 0.35 | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | — |
| 0.40 | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | — |
| 0.45 | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | — |
| 0.50 | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | [ÖLÇÜLMEDİ] | — |

**Seçilen değer:** [ÖLÇÜLMEDİ]
**Gerekçe:** [ÖLÇÜLMEDİ]

### Neden koşulmadı

Kalibrasyon koşusu uçtan uca katmanı gerektirir; o da retrieval (Şerit 1) ve
generation + guardrail (Şerit 2) hattının `main`'e inmesini bekliyor. 9 Ağustos
itibarıyla `app/modules/retrieval/` ve `app/modules/generation/` bu branch'te boş.

Harness hazır ve arka uç indiği anda koşacak; şu an çağrıldığında sessizce boş sonuç
üretmiyor, nereye baktığını yazıp duruyor:

```
'hybrid' modu için retrieval fonksiyonu bulunamadı. Bakılan yerler:
  app.modules.retrieval.service:retrieve
  ...
```

## 6. Kalibrasyon sonrası yapılacaklar

1. Seçilen eşik ve gerekçesi bu belgeye yazılır, koşu dosyası adıyla.
2. Değer **Şerit 1'e bildirilir**; `config.py`'yi onlar günceller.
3. `config.py`'deki "KALİBRE EDİLMEMİŞTİR" notu ancak bu üç adım bittikten sonra
   kaldırılır.
4. Ondan sonra holdout koşusu yapılır (T044) ve `--threshold-calibrated` bayrağıyla
   koşulur, ki sonuç dosyası eşiğin kalibre olduğunu kayda geçirsin.
