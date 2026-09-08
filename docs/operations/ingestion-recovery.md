# Belge işleyicisinin kesinti ve sürüm geçişi

8 Eylül2026 yerel018 kodu:0026 göçü, sonlu iş sahipliği ve kaynak revizyonu.
[Gerçek PostgreSQL ve süreç kanıtları](../../specs/018-codex-production-line/evidence/d2-local/README.md)
ayrı saklanır; yeni hosted ve canlı barındırma kabulü tamamlanmış sayılmaz.

## İşleme ve yetki

İşleyici kısa işlemde document→job sırasıyla kilit alır; UUID sahiplik anahtarı,
kaynak revizyonu, deneme sayısı ve DB saatine bağlı son zamanı kesinleştirir.
Dosya okuma, ayrıştırma ve embedding sırasında DB işlemi/kilidi tutulmaz. Okunan
baytların boyutu ve SHA256 değeri kabul edilmiş kaynakla eşleşmelidir.

Heartbeat yalnız süresi dolmamış mevcut anahtarı yeniler. Son yazım belgeyi ve işi
yeniden kilitler; anahtar/revizyon/süre geçerliyse chunk, belge durumu ve iş sonucu
tek işlemde kesinleşir. Yeni işleyici işi aldıktan sonra eski süreç geri gelse de
başarı, hata veya heartbeat yazamaz. Belge silme ve gerçek supersession aynı
yetki kilit sırasıyla korunur. Önceki sürüme ilişkin FK'nin temizlenmesi halefin
kendi kaynağını değiştirmez; gerçek kaynak A→B→A değişiminde revizyon yine artar.

Uygulama yalnız aktif eğitmenin yeni pending/attempt0 işini ekler; processing
anahtarı oluşturamaz ve job tablosunu güncelleyemez. Eğitmenin retry yeteneği,
kendi dersindeki başarısız ve superseded olmayan belge için tek başarısız işi
sıfırlar. Başka ders, öğrenci ve kimliksiz çağrı başarılı olmaz. Worker rolünün
mevcut BYPASSRLS yetkisi API rolüne aktarılmaz; bu değişiklik yeni rol yaratmaz.

## Deneme ve kapatma

Otomatik deneme sayısı en çok3; ilk iki hata sonrası yeniden uygunluk DB saatine
göre1 ve3 saniyedir. İptal/kesinti önceki denemeyi tüketmiş sayılır. Son başarısız
iş sabit neden koduyla failed olarak kalır; ayrı bir ölü-mektup tablosu yoktur.
Eğitmen açık retry yapabilir. Bu sürümde jitter eklenmedi; eşzamanlı toplu dış
hatalarda yük dağıtımı/kapasite kabulü ayrı değerlendirilmelidir.

Varsayılan lease60s, heartbeat10s, kontrol işlemi sınırı5s, kapanış grace5s'dir.
Yapılandırma sonlu değerler ve heartbeat+kontrol<lease ilişkisini doğrular.
SIGTERM yalnız bağımsız worker.main tarafından ele alınır: yeni iş alımı durur,
mevcut işe süre verilir; süre aşılırsa sınırlı iptal/bırakma yapılır. API içindeki
drain Uvicorn'un signal handler'ını değiştirmez. SIGKILL'de bırakma çalışmaz;
lease süresi ve geri çekilme geçtikten sonraki işleyici uyanışı devralmayı sağlar.

`asyncio.to_thread` içindeki ayrıştırıcı/model kodunu görev iptali öldürmez;
Python executor kapanışı bloke thread'i bekleyebilir. Gerçek deneyler kontrollü
async dosya bariyerindedir. Kesin duvar saati kapanma garantisi veya dış I/O'da
exactly-once iddia edilmez. CPU/bellek izolasyonu ve barındırma sonlandırma politikası
ayrı işletim işidir. Yeni süreç yoksa lease'in bitmesi kendi başına iş başlatmaz.

Bağımsız worker kotanın süresi dolmuş satırlarını ayrı görevde başlangıçta ve
60 saniyelik beklemelerle batch500 temizler. Başlangıçta gerçek expired/live
ayrımı doğrulandı; tekrar planlama kontrollü birim testidir. Scale-to-zero dış
uyanış/takvim ve saklama SLA'sı canlı kurulumla belirlenmelidir.

## İlk geçiş ve geri dönüş

1. Bütün eski bağımsız işleyicileri, API içi BackgroundTasks ve HTTP drain
   tetikleyicilerini durdurun; yeni belge alımını durdurup devam eden işleri boşaltın.
2. processing iş veya aynı belge için mükerrer aktif iş varsa göç reddedilir.
   Eski süreçlerin durduğunu doğrulamadan bunları körlemesine pending yapmayın.
   Belge/chunk/depo durumu ve devam eden işlemler için tek tek uzlaştırma yapın.
3.0026'yı uygulayın ve bütün tüketicileri yeni kaynakla başlatın. Eski kodun
   anahtarsız son yazımı ile yeni lease sahipliği birlikte güvenli kabul edilmez.
4. İşlerin ilerlediğini, failed nedenlerini ve bakımın çalıştığını ölçün; yalnız
   kodun çalışması ya da süre sütununun varlığı kurtarma/saklama SLA'sı değildir.

Göçün dolu ama geçerli pending/failed/completed satırlarını koruduğu, processing
ve mükerrer kuyrukları veri/şema değiştirmeden reddettiği gerçek DB'de doğrulandı.
Geri dönüşte eski yazıcıları yeniden etkinleştirmek anahtar korumasını kaldırır.
Trafiği durdurarak yeni sahiplik kontrolünü koruyan ileri düzeltme tercih edilir;
göçü veya aktif iş alanlarını kör DROP/UPDATE ile geri almaya çalışmayın.

İş ve claim kimliklerini, dosya yolunu, parser/model hatasını veya kaynak içeriğini
günlüğe yazmayın. İşleyici sabit neden/aşama ve sayaç kullanır. Claim anahtarı API
yanıtına çıkmaz. Genel stdout/proxy günlükleri ve yedek kopyaları ayrıca envantere
tabidir; işin failed olması ilgili kişisel verilerin silinmesi anlamına gelmez.
