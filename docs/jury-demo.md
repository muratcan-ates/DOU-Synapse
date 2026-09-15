# Jüri demosu: kaynaklı öğrenme döngüsü

Yeni dosya: `docs/jury-demo.md`. Hazırlama ve dış kaynak kontrol tarihi: 13 Eylül 2026.
Bu belge bir prova planıdır; süreler hedef akıştır, ölçülmüş çalışma süresi değildir.
Canlı prova ve aşağıdaki kalite ölçümleri bu belge hazırlanırken **koşulmadı**.

> **15 Eylül notu:** Yukarıdaki cümle 13 Eylül'ün durumudur ve olduğu gibi bırakıldı.
> O tarihten sonra demo yığını çalıştırıldı ve ölçüldü; ne aşıldı ne hâlâ geçerli,
> belgenin sonundaki **"15 Eylül eki"** bölümünde tek tek yazılıdır. Sunum öncesi
> önce o bölümü okuyun.

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

## Yerel demo kurulumu (14 Eylül 2026)

Üç betik, sırayla; hepsi `scripts/demo/` altında ve yeniden koşulabilir:

1. `sh scripts/demo/setup_db.sh` — temiz `dou_demo` veritabanı, `scripts/migrate.sh` ile 24 göç, yerel roller, sentetik seed (Ayşe Hoca ve öğrenci).
2. `sh scripts/demo/run_api.sh` — API `127.0.0.1:8020`; dev-auth, gerçek E5 embedding, `QUESTION_AUTHORING_ENABLED` ve `STUDENT_ASSESSMENT_WORKSPACE_ENABLED` açık. `apps/api/.env` içinde `GROQ_API_KEY` doluysa gerçek model, boşsa sahte sağlayıcı ve bunu açıkça yazar.
3. `sh scripts/demo/run_web.sh` — üretim derlemesi, `127.0.0.1:3020`, `NEXT_PUBLIC_DEV_AUTH=true`.

Sahte sağlayıcıyla yapılan prova gerçek model kanıtı değildir; jüriye hangi sağlayıcıyla gösterildiği söylenir.

### 14 Eylül 2026 13:05 — yerel duman koşusu (sahte sağlayıcı, gerçek retrieval)

`scripts/demo/` betikleriyle, `GROQ_API_KEY` olmadan (`LLM_FAKE_PROVIDER=true`), API 8020 / web 3020. Ölçülenler:

- Eğitmen dev-auth girişi ve panel açıldı; `COME302 İşletim Sistemleri` dersi API'den açıldı, öğrenci üye yapıldı.
- `sample_data/isletim-sistemleri` içinden dört dosya (PDF ×2, Markdown, PPTX) yüklendi; dördü de gerçek E5 embedding ile `completed` (7+6+4+3 parça).
- Asistan sorusu "Bir sürecin durumları nelerdir…" için üç kaynak kartı geldi: `01-processes.pdf` sayfa 1 ve 3, `04-synchronization.md`. Cevap metni sahte sağlayıcının; kaynaklar gerçek retrieval'dan.
- Soru üretimi: konu `Süreçler ve CPU zamanlama`, 3 MCQ istendi, 3 döndü, 3 kabul, 0 ret; üçü onaylandı.
- Öğrenci konu filtreli alıştırma sınavını 3 soruyla başlattı; yanlış şıkla verilen cevap `is_correct=false`, `score=0`, "neden yanlış" kartı `02-cpu-scheduling.pdf` sayfa 1.
- Ölçülmeyen: gerçek model cevap kalitesi (anahtar yok), süreli sınav, yayımlanmış blueprint kataloğu, prova süresi, ekran görüntüleri. Bunlar 15 Eylül provasının işi.

## 15 Eylül eki — neyin aşıldığı, neyin hâlâ geçerli olduğu

Bu bölüm yukarıdaki tarihsel kayıtları **değiştirmez**; sonrasında ölçülenleri ekler.

### Aşıldı

| 13–14 Eylül kaydı | 15 Eylül durumu |
|---|---|
| `docker: command not found` → demo yığını ayağa kalkmadı | Yığın **docker'sız** koşuyor: yerel PostgreSQL + `sh scripts/demo/run_api.sh` (:8020) + `run_web.sh` (:3020). Belgenin §"Koşum" bölümü zaten bu komutları veriyor |
| Gerçek model koşusu yapılamadı | Gerçek **Groq** (`openai/gpt-oss-120b`) ile koşuldu; kapsam dışı ret, Sokratik merdiven ve atıflı cevap tek tek doğrulandı (kayıt: `docs/team/GECE-RAPORU-14-EYLUL.md`) |
| Ekran görüntüsü üretilemedi | 16 görüntü <!-- docs-check: tarihsel 16 · 2026-09-15 --> gerçek model ve güncel kampüs tasarımıyla çekildi (`docs/screenshots.md`) |
| Senaryo adımları ölçülmedi | Sahnede sorulacak sorular gerçek modelle ölçüldü ve sabitlendi; `answer_cache` dolduruldu. Liste ve **sorulmaması gerekenler** `docs/demo-script.md` |

### Hâlâ geçerli — sahnede iddia edilmeyecek

- **Sağlayıcı failover gösterilmez.** Yukarıdaki ENGEL maddesi duruyor ve sebebi
  artık ölçülü: `apps/api/app/modules/generation/service.py` rol farkındalıklı
  sohbet yolunda `provider_attempt_limit=1` kuruyor, yani ikinci sağlayıcı
  **bilinçli olarak denenmiyor** — jeton rezervasyonu atomik kalsın diye. Yani bu
  yalnız "doğrulanmadı" değil, tasarım gereği kapalı. `LLM_FALLBACK_MODEL` ayarlı
  olsa bile sohbet isteğinde devreye girmez.
- **Groq'ta anlık hata olursa kurtarıcı yedek yoktur.** Tek gerçek koruma
  `answer_cache`'tir: önbellekteki soru modele hiç gitmez. Bu yüzden canlı
  sahnelerde yalnız `docs/demo-script.md`'deki ölçülmüş liste sorulur.
- **`provider-fallback` uçtan uca testleri CI'da hâlâ koşmuyor** (simülasyon
  bayrağı koşucuya bağlanmadı; fazlı koşucu henüz birleşmedi).
- **`learning_events` eğitmen özeti** bu tabanda doğrulanmadı; yukarıdaki madde
  aynen geçerli.
