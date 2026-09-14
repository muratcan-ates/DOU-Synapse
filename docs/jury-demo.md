# Jüri demosu: kaynaklı öğrenme döngüsü

Yeni dosya: `docs/jury-demo.md`. Hazırlama ve dış kaynak kontrol tarihi: 13 Eylül 2026.
Bu belge bir prova planıdır; süreler hedef akıştır, ölçülmüş çalışma süresi değildir.
Canlı prova ve aşağıdaki kalite ölçümleri bu belge hazırlanırken **koşulmadı**.

## Gösterim öncesi kontrol

- Yalnız sentetik demo kullanıcıları ve izinli ders materyali kullanılır. Öğrenci ile eğitmen ayrı tarayıcı oturumlarında açılır.
- Ders, konu, yayımlanmış blueprint ve ona uygun soru havuzu önceden doğrulanır. Gerçek sağlayıcı ve sahte sağlayıcı koşuları birbirinden ayrılır.
- Yanlış cevabın kaynak kartı açılır; dosya adı, sayfa ve alıntı gerçek materyalle karşılaştırılır. Kaynak yoksa açıklama gösterilmez.
- Aktif sınav bitirilmeden asistan gösterimine geçilmez. Sınav kilidi etrafından dolaşılmaz.
- **ENGEL:** Bu tabanda sağlayıcı 429 simülasyonu → “Önceden kaydedilmiş demo yanıtı” etiketli ürün akışı doğrulanmış değildir. Bu adım ilgili ürün işi ve gerçek sunucu E2E kanıtı gelene kadar canlı başarı olarak sunulmaz. Arayüzde sahte yanıt enjekte etmek sağlayıcı failover kanıtı değildir.
- Yeni `learning_events` mini eğitmen özeti bu tabanda doğrulanmadı. Mevcut analitik görünümü ile planlanan olay özeti ayrı anlatılır.

## 10 dakikalık senaryo

| Hedef zaman | Eylem | Söylenecek / kontrol edilecek |
|---|---|---|
| 00:00–00:45 | Öğrenciyle ders ve konu seç | “Bu oturum yalnız seçili dersin erişilebilir kaynaklarıyla çalışır.” Kaynak ve konu seçimi görünür. |
| 00:45–02:00 | Blueprint seç, sınav provasını başlat | Yayımlanmış planın kapsamını göster. Provanın nota veya geçme/kalmaya girmediği kullanım varsayımını açıkla. |
| 02:00–03:00 | Bilerek yanlış cevap ver, gerekli teslim adımını tamamla | Aktif sınavda cevap/çözüm sızdırmadan gerçek sonuç ekranına ilerle. Puan varsa yalnız sunucunun bu denemede ürettiği puanı göster. |
| 03:00–04:30 | “Neden yanlış?” ve kaynak kartını aç | Yanlışlık açıklamasını kaynak alıntısı/sayfayla karşılaştır; kod sorusunda varsa “Eksik ölçütün dayanağı” ve sonraki ipucunu göster. Alan yoksa uydurulmuş açıklama okumak yerine bu sınırı söyle. |
| 04:30–05:45 | **Bilinçli başarısızlık 1:** seçili materyalde olmayan soru sor | Ret/abstention görünmeli. “Kanıt bulamadığında cevap üretmemesi beklenen davranış.” LLM'e sıfır çağrı iddiası yalnız ayrı ölçüm varsa söylenir. |
| 05:45–07:00 | **Bilinçli başarısızlık 2:** onaylı yerel sağlayıcı 429 simülasyonu | Retry/fallback kanıtı varsa “Önceden kaydedilmiş demo yanıtı” etiketi ve kaynaklarını göster. Bu adayda adım engelli: beklenen davranışı plan olarak anlat, gerçekleşmiş gibi oynatma. |
| 07:00–08:30 | Eğitmen oturumunda mevcut ders analitiğini aç | Gerçek denemeden oluşan özeti kontrol et. Ham sohbeti gösterme; planlanan konu bazlı yanlış/ipucu/ret olay özetini mevcut özellik diye sunma. |
| 08:30–10:00 | Ölçüm kartı ve yol haritası | Kaynaklı açıklama → ret → görünür sağlayıcı hatası zincirinin sınırlarını anlat. Açık işler: 429 etiketli akış, olay özeti, gerçek model/insan kabulü, hedef ortam, erişilebilirlik ve LTI keşfi. |

## Ölçüm kartı

Ekranda yalnız aynı aday, veri kümesi ve koşu kaydına bağlı ölçümler bulunur.
Boş alanlar yüzdeye veya sıfıra çevrilmez; henüz ölçülmediyse “koşulmadı” gösterilir.

```text
citation coverage __/__
abstention __/__
scope-leak __/__
fallback __/__
aday SHA: __
koşu tarihi / sağlayıcı türü / kanıt yolu: __
```

- `citation coverage`: kaynakla doğrulanan akademik cevap / akademik cevap gerektiren değerlendirilebilir vaka. Retler cevap gibi paya eklenmez.
- `abstention`: doğru biçimde reddedilen kaynak dışı vaka / önceden belirlenmiş kaynak dışı vaka.
- `scope-leak`: seçili kapsam dışından içerik sızdıran vaka / kapsam sınırını sınayan vaka. Düşük olması istenir; atıf varlığı tek başına kapsam kanıtı değildir.
- `fallback`: doğru etiket ve kaynakla sonuçlanan simüle sağlayıcı hata vakası / simüle sağlayıcı hata vakası.

Her vaka için girdi, beklenen kontrol koşulu, gözlenen sonuç ve kanıt bağlantısı tutulur.
Sahte sağlayıcı sayıları gerçek model kalitesi olarak etiketlenmez.

## Jüri sorularına yaklaşık 15 saniyelik cevap taslakları

| Soru | Cevap |
|---|---|
| ChatGPT'den farkı? | “Buradaki hedef genel sohbet değil: ders üyeliği, seçili kaynak, doğrulanabilir alıntı ve sınav kilidiyle sınırlandırılmış prova. Farkı ürün adlarıyla değil bu kontrollerin gözlenen davranışıyla gösteriyoruz.” |
| Khanmigo varken neden? | “Benzer öğrenme desteği fikrini kendi ders materyalimiz ve Türkçe değerlendirme akışımız üzerinde sınayıyoruz. Khanmigo'ya üstünlük ölçmedik; bizim kabulümüz kaynak ve rol sınırlarının doğrulanması.” |
| Canvas/Moodle yerine mi? | “Ders yönetim sisteminin yerini alma hedefimiz yok. Prova ve kaynaklı açıklama üzerinde çalışıyoruz. Kurumun dış araç yetkileri ve entegrasyon sözleşmesi doğrulanmadan hazır bağlantı vaat etmiyoruz.” |
| LLM yanlışsa? | “Kaynak üyeliği ve kanıt kapısı yanlışlığı azaltmayı hedefler; modelin anlamsal doğruluğunu garanti etmez. Kaynak yoksa cevap yok, kuşkulu değerlendirme için insan incelemesi ve ölçülmüş hata kaydı gerekir.” |
| KVKK? | “Teknik erişim ve veri sınırlarını test ediyoruz. Hukuki uygunluk sertifikası vermiyoruz; saklama, veri işleyenler, yurt dışı aktarım ve kurum kararları ayrıca değerlendirilir.” |
| LTI neden yok? | “Önce kurumun LTI dış araç desteği, kayıt yetkilisi ve test ortamı doğrulanmalı. Protokolü ve güvenlik sözleşmesini sınamadan LTI hazır demiyoruz.” |
| Ölçek? | “Bu aday için ölçmediğimiz eşzamanlı kullanıcı veya gecikme rakamını söylemiyoruz. Hedef ortamda yük, kaynak tüketimi ve sağlayıcı kotası birlikte ölçülmeden kapasite taahhüdü vermiyoruz.” |
| Kopyayı önlüyor mu? | “Prova notlandırma kararı için kullanılmıyor. Aktif sınav sırasında yardım erişimi sunucuda kilitlenir; bunu tüm dış araçları veya kopyayı engelleme garantisi olarak sunmuyoruz.” |

“KVKK uyumlu”, “production-ready”, “LTI hazır” ifadeleri kullanılmaz.

## Dış gerçekler ve kullanım sınırı

- YÖK rehberinin duyurusu **7 Mayıs 2024** tarihlidir; kapsamı bilimsel araştırma ve yayın faaliyetlerinde üretken yapay zekâ kullanımıdır. Eğitim ürünümüz için uygunluk belgesi değildir. [YÖK duyurusu](https://www.yok.gov.tr/Sayfalar/Haberler/2024/yuksekogretim-kurumlari-bilimsel-arastirma-ve-yayin-faaliyetlerinde-uretken-yapay-zeka-kullanimina-dair-etik-rehber.aspx).
- TÜBİTAK **2209-A en fazla 12.000 TL**, **2209-B en fazla 16.000 TL** destek gösterir. 13 Eylül 2026 kontrolünde resmî program sayfalarında 2026 çağrısı yayımlanmış görünmüyor; 2026 tarihli sonuç işlemleri yeni çağrı değildir. Başvuru öncesi tekrar kontrol edilir. [2209-A](https://tubitak.gov.tr/tr/burslar/lisans-onlisans/destek-programlari/2209-universite-ogrencileri-arastirma-projeleri-destekleme-programi), [2209-B](https://tubitak.gov.tr/tr/burslar/lisans-onlisans/destek-programlari/2209-b-universite-ogrencileri-sanayiye-yonelik-arastirma-projeleri-destegi-programi).
- **BiGG 1812-2026-1**, §5.5/2: **%3 şirket payı karşılığında 1.350.000 TL yatırım**; hibe diye sunulmaz. [Resmî çağrı, sayfa 7](https://tubitak.gov.tr/sites/default/files/2026-03/1812-2026-1_Cagri_Duyurusu_260225.pdf).
- **AI Act kullanım varsayımı:** sınav provası sonuçları nota/geçme-kalmaya girmez. Bu tek başına muafiyet değildir: öğrenme sonuçlarını değerlendirme ve öğrenmeyi yönlendirme Ek III 3(b) kapsamında olabilir. **Madde 6(3)** koşulları ve varsa profil çıkarma ayrıca değerlendirilir; muafiyet gerekçesi belgelenmeden düşük risk iddiası yapılmaz. [Ek III](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3), [Madde 6](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6).
- Komisyonun güncel takviminde eğitim dahil Ek III yüksek risk yükümlülükleri **2 Aralık 2027** uygulanır. Madde 6 sayfası Omnibus değişikliklerinin henüz işlenmediğini belirttiğinden takvim için güncel Komisyon açıklaması esas alınır; bu belge hukuki sınıflandırma sonucu değildir. [Komisyon takvimi](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai), [güncel sorular ve yanıtlar](https://digital-strategy.ec.europa.eu/en/faqs/navigating-ai-act).

## Kodla karşılaştırma

Öğrenci/blueprint akışı: `apps/web/app/courses/[courseId]/exam/` ve
`apps/web/app/courses/[courseId]/blueprints/`; geri bildirim:
`apps/web/components/exam/feedback-panel.tsx`; kaynaklı puanlama:
`apps/api/app/modules/assessment/grading.py`. Bunların okunması canlı prova
veya gerçek model başarısı olarak kaydedilmez.

## 14 Eylül 2026 prova girişimi (P5 paketi) — koşulmadı

Bu bölüm P5 GPT sohbetinin kaydıdır; yukarıdaki plan L6'nındır ve değişmedi. Sohbetin ortamında PostgreSQL, API ve Docker yoktu; hiçbir adım ölçülmedi.

### Çalıştırma durumu
- 14.09.2026: demo stack açma/koşturma ve bütün adımlar **KOŞULMADI**.
- Son girişimde teknik engel: bu ortamda `docker` bulunmadı, bu yüzden demo yığını (`docker compose ...`) ayağa kaldırılamadı.

### Denenen ölçümler
1. `pg_isready -h /tmp -p 5432 -U postgres` → **KOŞULMADI** (`/tmp` soketi için yanıt yok).
2. `psql` ile `SELECT 1` denemesi → **KOŞULMADI** (`Operation not permitted`).
3. `curl http://localhost:8030/health/ready` → **KOŞULMADI** (yanıt yok).
4. `docker compose up -d db api api-fallback` → **KOŞULMADI** (`docker: command not found`).

### Planlanan adımlar
- Eğitmen yükleme
- Soru üretme/onaylama/yayımlama
- Öğrenci konu seçimi
- Süreli çözüm
- Yanlış cevapta kaynak kartı
- İlerleme ekranı
- Prova süresi ölçümü

Hepsinin ölçümleri yukarıdaki teknik engel nedeniyle **koşulmadı**.

### ENGEL
- Ortam başlangıç engeli: demo için gerekli servisleri çalıştıracak `docker` binary'si bu oturumda yüklü değil; API/PostgreSQL ayakta olmayınca ekran görüntüsü üretimi ve senaryo koşumu yapılamadı.
