# Şerit raporları ve lider kararları — 9 Ağustos 2026

> Üç şerit (1 retrieval, 2 generation, 3 chat+Sokratik) işini bitirdi. Bu belge
> raporlarından çıkan **kararları** ve **diğer şeritleri bağlayan bulguları**
> topluyor. Handoff'ta olmayan her şey buraya yazıldı.

---

## 1. Kaynağında kapatılan iki tuzak

Üç şeridin **üçü de** aynı iki engele bağımsız olarak çarptı. İkisi de artık
kodda çözüldü; kimsenin bir şey ayarlaması gerekmiyor.

### Test veritabanı çakışması — çözüldü

`conftest.py` oturum başında test veritabanını DROP+CREATE ediyordu ve ad
sabitti. İki oturum aynı anda `pytest` koşunca birbirinin veritabanını siliyor,
hatalar **rastgele ve hiçbir değişiklikle ilişkisiz** görünüyordu. Üç şerit de
kendi `TEST_DB_NAME`'ini elle vererek kurtulmuştu.

Artık ad **çalışma ağacının klasör adından türetiliyor**: her worktree kendi
veritabanını alıyor, elle ayar gerekmiyor. `TEST_DB_NAME` verilirse o kazanır
(CI bunu kullanıyor).

```
~/code/dou-lead                 → dou_synapse_test_dou_lead
~/code/.dou-synapse-retrieval   → dou_synapse_test_dou_synapse_retrieval
```

### `parsers.py:63` mypy hatası — çözüldü

`enumerate(Document)` tip bilgisi taşımıyordu. İki hata `mypy app` koşumunu
**tamamen durduruyordu**, yani paketin tamamı için tip denetimi fiilen kapalıydı
ve kimse fark etmiyordu (CI'da `continue-on-error`).

Açık `page_count` döngüsüne çevrildi. **`mypy app` artık 41 dosyanın hepsinde
temiz.** Şeritler kendi modüllerini tip denetiminden geçirebilir.

## 2. Verilen sözleşme kararları

`app/contracts.py` güncellendi — üç şeridin beklediği kararlar:

**`Generator.generate`'e `student_attempt` eklendi.** Şerit 3 ipucunu öğrencinin
son denemesine göre şekillendiremiyordu; Şerit 2'nin gerçek servisinde bu kwarg
zaten vardı, yani sözleşme uygulamanın gerisindeydi. Gerekçe: öğrencinin neyi
yanlış anladığını görmeden verilen ipucu yönlendirme değil, tahmindir.

**Kanıt eşiğinin hangi skora uygulanacağı yazıldı.** Şerit 1 ve Şerit 3 aynı
tuzağa **ayrı ayrı** düştü: eşik `fused_score`'a uygulanırsa her soru reddedilir,
çünkü RRF skoru sıralamadan üretilir ve üst sınırı ~0.033'tür — alakadan bağımsız
olarak küçüktür. `ts_rank` de mutlak ölçekli değildir. Hattaki tek mutlak ölçekli
sayı `dense_score`'dur. Kural artık `RetrievedChunk`'ın üstünde yazılı ki üçüncü
kez düşülmesin.

**`Citation.claim` EKLENMEDİ** ve gerekçesi dosyaya yazıldı. `contracts.py`
guardrail zincirinin sözleşmesidir; `claim` sunum verisidir ve hiçbir guardrail
kararı ona bakmaz. Zarf katmanında (`schemas/chat.py`) taşınır. Eklenseydi,
hiçbir kontrolün okumadığı bir alanı üç modül birden doldurmak zorunda kalırdı.
**Tartışma yeniden açılmasın.**

## 3. Şerit 5'i doğrudan bağlayan iki ölçüm bulgusu

Bunlar T043 ve SC-005'i etkiliyor; Şerit 5 başlamadan okumalı.

### Kanıt kapısı bugün fiilen açık

Şerit 1'in ölçümü: `evidence_threshold=0.35` ile konu dışı **10 sorgunun 10'u da
geçiyor**. "Makarna nasıl pişirilir" sorusu 0.766 alıyor.

Sinyal sağlam, değer yanlış: en iyi kesim **0.7963**'te doğruluk **0.96**. Aday
"marj" sinyali daha kötü ayırdı (0.88). n=24 — yön göstergesi, kesin hüküm değil.

`config.py`'deki `evidence_threshold = 0.35` hâlâ "KALİBRE EDİLMEMİŞTİR" notuyla
duruyor. T043 bu sayıyı kalibre edip gerekçesini `evaluation/calibration.md`'ye
yazacak.

### SC-005 bu haliyle yanlış ölçer

Şerit 3'ün bulgusu: müfredat dışı sorular çoğunlukla **kanıt eşiğine takılıyor**,
yani `out_of_scope` değil `insufficient_context` etiketi alıyorlar. FR-011'in
sıralaması gereği bu davranış **doğru** — ama SC-005 yalnız `out_of_scope`'u
sayıyor, dolayısıyla metrik gerçekte iyi çalışan bir sistemde bile düşük çıkar.

İki seçenek, ikisi de meşru: (a) SC-005'i "doğru ret" olarak yeniden tanımla ve
iki durumu birden say, (b) kapsam sınıflandırmasını kanıt kapısından **önce**
koştur. Bu bir **ölçüm tasarımı kararı**; Şerit 5 verir ve gerekçesini yazar.

## 4. Şerit 3 ve 4 için: sahteleri bırakabilirsiniz

**`Retriever` gerçek uygulaması hazır** (`feat/retrieval`):
`retriever: Retriever = HybridRetriever(session)` mypy'dan geçiyor. `search()`
ham sonuç verir, `retrieve()` kanıt kapısını uygular ve eşik altında `chunks`'ı
boş döner.

**`Generator` ve cevap şeması hazır** (`feat/generation`): `AnswerPipeline.run()`
tek giriş noktası — guardrail sırasını kendiniz dizmeyin, zincir `chain.py`'de
sabit.

İkisi de henüz `main`'de değil; dallardan rebase alın.

## 5. Şerit 4 ve 5'in bilmesi gereken küçük kalemler

- **`answer_cache` sütunu `answer`**, `response` değil — T053 bu adı kullanmalı
- **`request_logs` yazma-yalnız**: SELECT politikası yok, `INSERT ... RETURNING`
  kullanılamaz. Şerit 5 satır bazlı okuma isterse `0005`'te politikayı açmalı
- **`evaluation/gold_set/injection_cases.json`** hazır (Şerit 2'nin bonusu):
  19 injection (yedi kalıp ailesi) + 12 sızıntı senaryosu, 3'ü yanlış pozitif
  kontrolü. Gold set Şerit 5'in dosyası, **birleştirme onda**. Dosyanın içinde
  rapor dili uyarısı var: hepsi geçse bile sonuç "bilinen temel kalıplara karşı
  smoke-test edildi"dir, "dayanıklı" denemez

## 6. Ertelenen teknik borç (bilinçli)

Şeritler kendi sınırları dışına taşmamak için geçici çözümle ilerledi. Bunlar
**bilinen** borçlar, unutulmuş değil:

| Kalem | Nerede | Kime ait |
|---|---|---|
| `ChatRequest`/`ChatResponse` `api/chat.py` içinde | T010'un dosyası `schemas/chat.py` olmalıydı | Şerit 2/3 uzlaşsın |
| Soru uzunluğu (2000) ve istek sınırı (20/dk) sabitleri | `api/chat.py`'de, `config.py`'ye taşınmalı | lider |
| `_pg_enum` üçüncü kez kopyalandı | `models/base.py`'ye taşınmalı | lider |
| ARCHITECTURE §5'teki `hints[]` dizisi konmadı | Bir Sokratik tur tam bir ipucu üretiyor; dizi `answer`'ı tekrarlardı | T010 karar versin |

## 7. Ölçülemeyen tek şey

**Gerçek LLM çağrısı yapılamadı** — ortamda API anahtarı yok. Şerit 2 bunu DONE
notuna yazdı. Anahtar geldiğinde tek gerçek çağrı + gecikme ölçümü gerekiyor;
SC-010 (p95 < 10 sn) o ölçüm olmadan raporlanamaz.

Sahte sağlayıcı bir stub değil: prompt'taki `<source>` etiketlerini geri
ayrıştırıp yalnızca gerçekten verilmiş chunk'lara atıf yapıyor. Bu yüzden
guardrail testleri kendi kurdukları sahneyi değil, üretim yolunu sınıyor.

## 8. Worktree adlandırması — belge gerçeğe uyduruldu

Handoff `~/code/dou-<serit>` diyordu; şeritler `~/code/.dou-synapse-<serit>`
kullandı (ilk iki şeridin kurduğu desen, sonrakiler ona uydu). **İkisi de
çalışır**; dal/worktree eşlemesi doğru olduğu sürece klasör adı önemsiz.
Taşımak venv'leri kırar, o yüzden kimse taşımasın.

Lider `~/code/dou-lead`'de.
