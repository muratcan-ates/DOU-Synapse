# C1 gerçek E5 çapraz tanı — dar kapsam kararı

8 Eylül 2026. Bu ek rapor önceki hashing, E5 ve C1 raporlarının yerine geçmez. Kaynak, altın set, eşik, veritabanı veya model bu analiz sırasında değiştirilmedi. Analiz saklanan JSON ve yerel kaynaklar üzerinde yapıldı; DB sorgusu ve model çalıştırması yapılmadı.

**Yeni dense + eski FTS, eski dense + eski FTS ile aynı sonucu verdi.** Aynı 127 sorgunun 105 puanlanan örneğinde Recall@5, Recall@8, MRR, bütün ilk isabet sıraları ve bütün kaynak sırası listeleri eşit. Bu bulgu, ANN/GUC/dense düzeltmesini koruyup FTS içerik-hash sıralaması değişikliğini bu teslim adayından geri çekmeyi destekliyor. Çapraz birleştirme tanısı tek başına son üretim kaynağının kabul testi değildir; daraltılmış gerçek kaynak tekrar çalıştırılmalıdır.

| Dense | FTS | Recall@5 | Recall@8 | MRR |
|---|---|---:|---:|---:|
| Eski | Eski | 93/105 = 0.885714 | 98/105 = 0.933333 | 0.7377210884 |
| Yeni | Eski | 93/105 = 0.885714 | 98/105 = 0.933333 | 0.7377210884 |
| Eski | Yeni | 92/105 = 0.876190 | 97/105 = 0.923810 | 0.7395351474 |
| Yeni | Yeni | 92/105 = 0.876190 | 97/105 = 0.923810 | 0.7395351474 |

Dar tanı kolu için Recall@5 ≥ 0.80, baseline Recall@5 azalmama ve baseline MRR azalmama koşulları sağlanıyor. İlk birleşik adayın E5 ve hashing gerilemeleri geçerli olumsuz kanıt olarak korunuyor. FTS geri çekmesi bu başarısız kayıtları geriye dönük başarılıya çevirmeyecek.

## Doğrulanan koşullar

- Ölçüm `measured_diagnostic / complete`; özgün iki kolun 127 sorguluk üst-8 sonuçları ve kaynak sıraları tekrarında sapma yok (`original_replay_drift=[]`).
- Bütün 508 çapraz RRF sonucu gerçek dönen dense/FTS aday kimliklerinden mevcut saf RRF fonksiyonu ile yeniden hesaplandı. Bu dört kolun tüm kaynak isabet sıraları altın setteki dosya/sayfa/slayt/bölüm koşullarından bağımsız yeniden hesaplandı; seçilen 127 soruda metin çapası nedeniyle bu kontrolün atlandığı örnek yok.
- Eski üç retrieval dosyasının saklanan byte'ları `git show 71d5ff640f0d48a08f3967b000485a15035f10c7` ile eşit. Adayın çalışma ağacı kaynak hashleri, ortak bağımlılık/harness hashleri, önceki E5 karşılaştırma manifesti ve geçici çalıştırıcı hashleri aynı. Kirli aday yalnız checkout commit SHA'sıyla tanımlanmıyor.
- 161 altın sorudan değişmeden seçilen 127 soru; 105 puanlanan, 22 kapsam dışı. Soru sırası/metni hash'i `3901c94a6f7e6cdbf2089d9aa5e4ab102fbcb8576ad08c400dfcdae99f6a8a3a`. Aynı top-8, dense24, FTS24, çarpan8, RRF60, mevcut 0.81 eşik ayarı korunuyor. Ham retrieval eşik uygulayan guardrail akışı değildir.
- Gerçek sağlayıcı `FastEmbedProvider`, model `intfloat/multilingual-e5-large`, namespace `fastembed/intfloat/multilingual-e5-large@0.8.0`. Aynı altı yerel model dosyasının tam içerik hashleri ölçüm öncesi/sonrası ve ilk E5 ölçümü arasında eşit. Tam ağırlık hashlerini root'un çalıştırdığı wrapper okudu; bu bağımsız analiz hash kayıtlarını ve kaynak bağını denetledi, modeli yeniden yüklemedi.
- Aynı `dou018_eval_c1e501` korpusu: 167 chunk/embedding. Kayıtlı içerik/vektör/metadata hash'i önce/sonra ve özgün ölçümle eşit: `1fbff9e89fe71c86f343608c52cea1243cc3dcdeabf7770d94f25082298120c9`.
- Gerçek `dou_app`, `rolsuper=false`, `rolbypassrls=false`; kaynakta zorunlu öğrenci RLS bağlamı ve salt okunur işlemler. Ölçüm tek fiziksel bağlantıda PID16030 ile ilerledi. Bütün 254 kol işlemi plan modunu `auto` olarak geri aldı. Çalıştırıcının 11.634 kaynak metadata kontrolü geçti; analizde çapraz sonuçlar içindeki aynı chunk'ın metadata hashleri de tutarlı.

## Eşit skor ayrımı

E5 dense sonuçları 127/127 sorguda dönen bütün 24 adayın kimliği, sırası, skoru ve metadata'sıyla **tamamen aynı**. Bu, bu küçük korpustaki gerçek E5 koşusunun bulgusudur; büyük HNSW korpusları için genel exact-recall garantisi değildir.

FTS sonuçları yalnız 2/127 sorguda tamamen aynı. 51/127 sorguda aday kimlik kümesi aynı; diğer 76 sorguda değişen kimliklerin hepsi iki kolun da son aday sınırındaki tam eşit FTS skorunu taşıyor. Ortak kimliklerin skorları ve her sıradaki skor dizisi bütün 127 sorguda aynı. Dolayısıyla gözlenen fark skor hesaplama değişiminden gelmiyor; eşit skorlu adayların sırası ve LIMIT24 içinde temsil edilen adaylar değişiyor. RRF, sıra numarasını kullandığı için aynı skorlu FTS adaylarını farklı sıralamak birleşik sonucu değiştirebiliyor.

Somut örnekler:

- **H-154 (LRU kod incelemesi):** `page_replacement.py` chunk0 dense1 ve chunk2 dense2 iki kolda aynı. Eski FTS bunları sırasıyla13/14'te, aynı `0.007599089` skoru ile içeriyor; yeni FTS'nin ilk24'ünde ikisi de yok. Belgeden chunk5 iki kolda da FTS9. İlk doğru birleşik kaynak eski FTS ile2, yeni FTS ile8 oluyor; tek Recall@5 kaybı bu soru.
- **H-112:** Beklenen I/O sayfa4 dense5 olarak iki kolda aynı ve iki FTS aday listesinde de yok; başka adayların FTS temsil/sıra farkı doğru kaynağı birleşik8'den ilk8 dışına itiyor.
- **H-120:** Beklenen güvenlik sayfa1 dense2 olarak iki kolda aynı ve iki FTS listesinde de yok; birleşik7'den ilk8 dışına çıkıyor.
- **H-119:** Beklenen güvenlik sayfa1 dense1 olarak iki kolda aynı ve iki FTS listesinde de yok; diğer adayların değişimi doğru kaynağı ilk8 dışından6'ya taşıyor. Bu kazanım, diğer Recall@8 kayıplarından yalnız birini dengeliyor.

Yalnız dönen 24 aday izleniyor. Tüm uygun kayıtların LIMIT dışındaki eşitlik kümesi bu tanı tarafından sayılmadı; eşitlik grupları için evrensel bir temsil iddiası kurulamaz. İçerik hash sırası tekrar üretilebilirliği iyileştirmeyi amaçlasa da alaka sırası değildir.

## Uygulama ve kabul sınırı

Öneri, yalnız yeni FTS hash-tie değişikliğinin geri çekilmesi; dense MATERIALIZED, sınırlı fazla aday seçimi ve dense çağrısına özel custom-plan korumasının tutulmasıdır. Eski FTS'nin yeniden yüklemede UUID'ye bağlı eşitlik davranışı açık iş kalır. Bu ayrı kusur kabul metninden silinmemeli ve dense iyileştirmesi onun çözümü gibi sunulmamalıdır. C2 bellek/indeks göçü için nedensel ölçüm hâlâ yoktur.

Geri çekmeden sonra gerçek son kaynaklarla tam API, prepared-plan/runtime probe ve hashing + gerçek E5 iki kol holdout yeniden çalıştırılmalı; yeni kaynak hashleri ayrı manifestlerde bağlanmalıdır. Eski RLS, metadata ve erişim negatifleri korunmalıdır. Test amacı, altın set veya eşikler değiştirilmeden ölçülmüş zararlı bir bileşenin ayrılmasıdır. Bu deneyde LLM çağrısı, yanıt/citation faithfulness, pedagojik değerlendirme, insan kabulü veya performans kabulü yoktur.

Kanıtlar: `c1-e5-trace-measured-01/manifest.json` SHA256 `e4a6b7ede5e971e0b5b5af9f3f550b8a1802610175c3cc0f08d9163402962b0c`; `trace.jsonl` SHA256 `f5830f3edead58b66ba5a2127dbd90e8558a6c6a16a973ad025e5b90b2847d76`. Sayısal bağımsız çıktı `c1-e5-trace-analysis.json`; analiz kaynağı `analyze_c1_e5_trace.py`. İlk E5 başarısızlığı için ayrı `c1-e5-analysis.md/json` korunur.
