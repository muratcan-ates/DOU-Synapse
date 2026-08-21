# Faithfulness etiketleme şablonu (T047)

**Durum (9 Ağustos 2026): süreç hazır, örneklem çekildi, ETİKETLEME KOŞULMADI.**

| Adım | Durum |
|---|---|
| Şablon ve kurallar | hazır (bu belge) |
| Örneklem çekme betiği | hazır — `pull_sample.py` |
| Örneklem çekildi | **evet** — `sample_2026-08-09.json`, n=25, tohum 20260809 |
| Örneklem geçerli mi | **HAYIR — sahte sağlayıcı** (aşağıya bakınız) |
| Etiketleme dosyaları | üretildi — `labels_etiketleyici_1.md`, `_2.md`, ikisi de **boş** |
| Uyum hesabı | **KOŞULMADI** |

## Neden bu örneklem rapora giremez

Örneklem gerçek API'den, gerçek guardrail zincirinden geçerek çekildi — ama sunucu
`LLM_FAKE_PROVIDER=true` ile koştu, çünkü **gerçek bir sağlayıcı anahtarı yok**
(`GROQ_API_KEY`, `GEMINI_API_KEY` ve `EVAL_LLM_API_KEY` boş).

Sahte sağlayıcı getirilen chunk'ları özetleyip döndürüyor. Böyle bir cevabı "kaynağa
sadık" diye etiketlemek **totolojidir**: cevap zaten kaynağın kendisi. 25 cevabın
25'i `answered` döndü ve her biri 3 atıf gösterdi; bu sayılar hattın çalıştığını
gösterir, cevap kalitesi hakkında hiçbir şey söylemez.

**Bu yüzden etiketleme yapılmadı.** Doldurulmuş bir tabloya bakan biri onu ölçüm
sanardı; boş bir tablo ne olduğunu doğru anlatıyor.

## İki etiketleyici sorunu — dürüst çözüm

Yöntem iki BAĞIMSIZ etiketleyici ister. Bu şeridi tek bir ajan koşturdu.
**"İki kişi etiketledi" YAZILMAYACAK.** Seçilen yol, şerit belgesindeki ikinci
seçenektir: **etiketleme dosyaları hazır bırakıldı**, iki ayrı dosya hâlinde, her
biri diğerine bakmamayı hatırlatan uyarıyla.

Dosyalar cevabın yanında **kaynak parçaların metnini** de taşıyor; etiketleyicinin
veritabanına ya da API'ye dönmesi gerekmiyor. "Kaynağı okumadan etiketleme" kuralı
ancak kaynak elinin altındaysa uygulanabilir.

---

## Neyi ölçüyoruz — ve neyi ölçmüyoruz

**Faithfulness:** cevaptaki iddiaların, gösterilen kaynak parçalar tarafından
gerçekten desteklenip desteklenmediği.

**Citation validator faithfulness'ı ÖLÇMEZ.** O, modelin retrieve edilmemiş bir
kaynağa atıf yapmasını engeller ve bu kontrol deterministiktir. Ama model, gerçekten
retrieve edilmiş bir chunk'a atıf verip o chunk'ın söylemediği bir şeyi de yazabilir.
İkisini raporda karıştırmak, jüri karşısında en kolay düşülen tuzaktır.

## Kurallar

1. **İki kişi BAĞIMSIZ etiketler.** Etiketleme bitene kadar birbirinizin kararını
   görmezsiniz: ayrı dosyalar, konuşmadan.
2. **Ham uyum oranı çözüm ÖNCESİ hâliyle raporlanır.** Anlaşmazlıklar sonradan
   tartışılıp karara bağlanır, ama uyum oranı tartışmadan önceki etiketlerden
   hesaplanır. Sonrasından hesaplanan uyum her zaman %100 çıkar ve hiçbir şey ölçmez.
3. **Ölçek üç değerlidir**, ara değer üretilmez:

| Etiket | Ne zaman |
|---|---|
| `destekleniyor` | Cevaptaki bütün iddialar gösterilen kaynaklarca destekleniyor |
| `kısmen` | En az bir iddia destekleniyor, en az biri kaynakta yok |
| `desteklenmiyor` | Ana iddia kaynakta yok ya da kaynakla çelişiyor |

4. **Kaynağı okumadan etiketleme.** Etiket, cevabın ikna ediciliğine değil kaynağın
   içeriğine bakılarak verilir.

## Örneklem nasıl seçilir

Holdout'un `direct` ve `multi_chunk` kategorilerinden **rastgele 20-30 cevap**.
Rastgelelik şart: "ilginç görünen" cevapları seçmek örneklemi bozar.

Seçim ve çekme artık tek betikte; elle yapılmaz:

```bash
cd apps/api
uv run python ../../evaluation/faithfulness/pull_sample.py \
    --corpus /tmp/corpus_e5.json --api-url http://127.0.0.1:8022 \
    --size 25 --llm-note "LLM_FAKE_PROVIDER=false; primary=groq/llama-3.3-70b-versatile"
```

`--dry-run` hangi soruların seçileceğini istek atmadan yazar.

Tohum sabit (`20260809`): örneklemin nasıl seçildiği yeniden üretilebilmeli, yoksa
"beğendiğiniz cevapları seçtiniz" itirazına verecek cevap kalmaz.

## Etiketleme tablosu

Her etiketleyici bu tabloyu **kendi kopyasında** doldurur:
`evaluation/faithfulness/labels_<isim>.md`

| Soru id | Cevap özeti (ilk cümle) | Gösterilen kaynaklar | Etiket | Not |
|---|---|---|---|---|
| H-0xx |  |  | `destekleniyor` / `kısmen` / `desteklenmiyor` |  |

## Uyum hesabı

Elle sayılmaz; tanımı testlerle sabitlenmiş fonksiyon kullanılır
(`metrics.label_agreement`, `apps/api/tests/test_eval_metrics.py`):

```bash
cd apps/api
uv run python -c "
import sys; sys.path.insert(0, '../../evaluation')
import metrics, json
first  = ['destekleniyor', 'kısmen', ...]   # 1. etiketleyici, soru sırasıyla
second = ['destekleniyor', 'destekleniyor', ...]  # 2. etiketleyici
print(json.dumps(metrics.label_agreement(first, second).as_dict(), ensure_ascii=False, indent=2))
"
```

- **Ham uyum oranı zorunludur.**
- **Cohen's kappa bonustur** ve tanımsız kalabilir: iki etiketleyici de her cevaba
  aynı etiketi verdiyse şans uyumu 1'e gider ve kappa hesaplanamaz. Böyle bir durumda
  fonksiyon `None` döndürür; ham uyum yine raporlanır — tanımsız bir kappa, ölçülmüş
  bir uyumu geçersiz kılmaz.

## Sonuç

| Alan | Değer |
|---|---|
| Örneklem büyüklüğü | 25 (çekildi, 9 Ağustos 2026) |
| Örneklem dosyası | `sample_2026-08-09.json` |
| Tohum | 20260809 |
| Sağlayıcı | **sahte** (`LLM_FAKE_PROVIDER=true`) — örneklem geçersiz |
| 1. etiketleyici | [ETİKETLENMEDİ] |
| 2. etiketleyici | [ETİKETLENMEDİ] |
| Etiketleme tarihi | [ETİKETLENMEDİ] |
| Ham uyum oranı | [ÖLÇÜLMEDİ] |
| Cohen's kappa | [ÖLÇÜLMEDİ] |
| `destekleniyor` / `kısmen` / `desteklenmiyor` dağılımı | [ÖLÇÜLMEDİ] |
| Çözülen anlaşmazlık sayısı | [ÖLÇÜLMEDİ] |

**İkinci etiketleyici:** R4 (Cevap kalitesi + guardrail) doğal eş. Takıma sorulacak.

## Neden koşulmadı — ve anahtar geldiğinde ne yapılacak

Sebep artık hattın eksikliği değil: uçtan uca hat çalışıyor, örneklem gerçek API'den
çekildi. Eksik olan tek şey **gerçek bir LLM sağlayıcı anahtarı.**

Anahtar geldiğinde üç adım:

```bash
# 1) API'yi GERÇEK sağlayıcıyla başlat (R2 portu 8022)
cd apps/api
DATABASE_URL=postgresql+psycopg://dou_app:dou_app_local@localhost/dou_synapse_eval \
EMBEDDING_PROVIDER=fastembed LLM_FAKE_PROVIDER=false GROQ_API_KEY=... \
uv run uvicorn app.main:app --port 8022

# 2) Örneklemi YENİDEN çek — aynı tohum, aynı sorular, gerçek cevaplar
uv run python ../../evaluation/faithfulness/pull_sample.py \
    --corpus /tmp/corpus_e5.json --api-url http://127.0.0.1:8022 --size 25 \
    --llm-note "LLM_FAKE_PROVIDER=false; primary=groq/llama-3.3-70b-versatile"

# 3) İki kişi bağımsız etiketler, sonra uyum hesaplanır
```

Tohum sabit olduğu için **aynı 25 soru** çekilir; sahte ve gerçek koşu soru soruya
karşılaştırılabilir. Eval için ayrı anahtar kullanılmalı (`EVAL_LLM_API_KEY`): demo
anahtarıyla eval koşmak demo günü kota bitmesi demektir.
