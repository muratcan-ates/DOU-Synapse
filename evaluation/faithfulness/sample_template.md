# Faithfulness etiketleme şablonu (T047)

**Durum: örneklem çekilmedi.** Şablon hazır; doldurma, uçtan uca koşu yapıldıktan
sonra (gerçek cevaplar üretildiğinde) yapılacak.

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

```bash
cd apps/api
uv run python -c "
import json, random, sys
sys.path.insert(0, '../../evaluation')
import goldset
gold = goldset.load('../../evaluation/gold_set/holdout.json')
pool = [i.id for i in gold.items if i.category in ('direct', 'multi_chunk')]
random.Random(20260809).shuffle(pool)
print(pool[:25])
"
```

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
| Örneklem büyüklüğü | [ÖLÇÜLMEDİ] |
| 1. etiketleyici | [ÖLÇÜLMEDİ] |
| 2. etiketleyici | [ÖLÇÜLMEDİ] |
| Etiketleme tarihi | [ÖLÇÜLMEDİ] |
| Ham uyum oranı | [ÖLÇÜLMEDİ] |
| Cohen's kappa | [ÖLÇÜLMEDİ] |
| `destekleniyor` / `kısmen` / `desteklenmiyor` dağılımı | [ÖLÇÜLMEDİ] |
| Çözülen anlaşmazlık sayısı | [ÖLÇÜLMEDİ] |

**İkinci etiketleyici:** R2 (Guardrail & QA) doğal eş. Takıma sorulacak, kim müsaitse.

## Neden koşulmadı

Uçtan uca koşu için sohbet ucu (Şerit 3) ve generation + guardrail hattı (Şerit 2)
`main`'e inmedi. Gerçek cevap üretilmeden etiketlenecek bir şey yok.
