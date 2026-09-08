# Sahipliği doğrulanan tarayıcı testi

Tarayıcı paketi gerçek API ve yeni web derlemesiyle çalışır. Uygulama verisi
ve denetim kayıtları için yalnız bu koşuya ayrılmış sentetik hedef kullanılır.
Mevcut geliştirme veya üretim veritabanında doğrudan temizlik komutu çalıştırmayın.

## Giriş noktası

`scripts/run_owned_e2e.py`, önceden bağımsız olarak oluşturulup kimliği
doğrulanmış hedef için çağrılır. Yerel operatör hedefin tek sahibi olduğunu,
aynı storage alanını veya API sürecini başka koşunun kullanmadığını doğrular.
Araç kendi API sürecini başlatır; açık web sunucusunu yeniden kullanmaz.

```text
python scripts/run_owned_e2e.py --repo <mutlak-depo-yolu> \
  --pins <özel-hedef-kaydı> --pins-sha256 <önceden-doğrulanan-sha256> \
  --passfile <özel-parola-dosyası> --output <yeni-mutlak-kanıt-dizini> \
  --run-id <benzersiz-koşu-kodu> --web-port <boş-yerel-port>
```

Python ortamında API bağımlılıkları, PATH üzerinde Bun ve PostgreSQL istemcisi,
kurulu Chromium gerekir. `--webpack` yerel derleyici seçeneğidir; varsayılan
CI derleyicisini değiştirmez. Hedef kaydı/üst dizini ve parola dosyası özel
izinli normal dosyalardır. Hedef kaydı cluster kimliği, DB adı/OID, açık sayısal
host/port, DBA rolü, API origin'i ve provisioning makbuzuna bağlanır.
Kendi bağlandığı DB'den hash üretmek, hedefe sahip olunduğunu tek başına kanıtlamaz.

Yerel provisioning ve rol yönetimi operatörün sorumluluğundadır. Bu araç mevcut
rol izinlerini değiştirmez, veritabanı yaratmaz/silmez. `bun run test:e2e`
tek başına üst sürecin sahiplik ve başlangıç kayıtlarını oluşturmaz; doğrudan
çağrı gerekli makbuz yoksa güvenli biçimde reddedilir.

## GitHub işi

E2E işi kendi PostgreSQL servis container kimliğini
`scripts/provision_ci_e2e.py` aracına verir. Araç pinli imajı, container/host
bağlantı eşliğini ve boş servis envanterini doğrular. Yalnız yeni oluşturduğu
hedefte göçleri, mevcut yerel demo rol kurulumunu ve sentetik seed'i uygular;
her SQL dosyasından önce hedef kimliğini tekrar kontrol eder. Mac veya ortak
PostgreSQL için bu CI provisioning yolu kullanılmaz.

## Sonucu okuma

Başarı için tarayıcı exit0, API'nin gözlenmiş normal kapanışı, değişmemiş kaynak
hash'leri ve başlangıç/son tam audit muhasebesi birlikte gerekir. Korunmuş
satırın kaybolması/değişmesi veya makbuzu yakalanmayan yeni satır başarısızlık
üretir. Araç bunu geniş DELETE ile gizlemez; hedef ve kanıt inceleme için kalır.

`result.json`, `quiescence.json`, `audit/final-accounting.json` ve gerçek test
loglarını birlikte okuyun. Kapanış hatasında yalnız exit0 yeterli değildir.
Hata sonrası tekrar için yeni koşu/hedef hazırlayın; eski makbuzları başarı
etiketiyle yeniden kullanmayın. Yalnız araç tarafından oluşturulmuş çocuk
süreçlerin kapanışına müdahale edilir.

CI artifact'ı JSON/log ve Playwright rapor/trace'lerini tutar; parola dosyası,
storage içeriği veya `.env` yüklemez. Sentetik fixture ve operasyonel metadata
yine erişim/saklama politikası gerektirir. Yerel başarı gerçek JWT, LLM,
private Storage, Docker hedefi veya hukuki uygunluk kabulü değildir.
