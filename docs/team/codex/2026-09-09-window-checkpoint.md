# DOU-Synapse — çalışma penceresi kapanış kaydı

9 Eylül 2026, 16:10 UTC denetimi. Planlanan çalışma penceresi 00:45 UTC / 03:45 İstanbul'da sona ermiştir. Daha sonra gelen otomatik devam bildirimi yeni bir geliştirme penceresi sayılmadı; otomasyon duraklatıldı. Görev kesintileri nedeniyle on saat kesintisiz yürütme iddiası yoktur.

## Kalıcı ve yeniden doğrulanan durum

- Son uygulama commit'i `d870c2615bc06007dced60b1e64397ed41ba96ef` (S10 / own036). Çalışma ağacı kapanış denetiminde temizdi. `deb83e1c0c4553e00072ea6797bd48b6ab53f330` tabanına karşı kesin commit yönetişim denetimi 9 Eylül'de yeniden **PASS** verdi.
- S10'un kaynak ve test arşivi [depoda korunuyor](../../../specs/018-codex-production-line/evidence/s10-local/README.md): 1688 API/38 alt vaka, 573 web, 134 ayrı izole kontrol, 56 gerçek HTTP isteği ve 71 tarayıcı akışı. Bunlar kendi kayıtlı kaynak sürümünün yerel sonuçlarıdır; kapanışta tam suite yeniden çalıştırılmadı.
- Sunucu kaynaklı destek kodu, günlüklerde kişisel veri azaltımı, test denetim kayıtlarının sahipliği ve süreç kapanışı; öğrenci/eğitmen/Bilgi İşlem kılavuzları bu kontrol noktasına dahildir.
- Son doğrulanmış uzak kabul `f79d8a2` idi. S9 `e19dc8c` / `deb83e1` ve onları içeren S10 gönderilmedi. Yeni bir uzak kabul, main birleşimi veya canlı dağıtım yapılmadı.

## S10 sonrası çalışmaların durumu

9 Eylül 16:10 UTC'de `/private/tmp/dou018-evidence`, test PostgreSQL dizini ve S11 aday dizinleri bulunamadı. Yokluğun nedeni bu denetimde belirlenmedi. S10 Git arşivi etkilenmedi. Görev kaydından kurtarılan kaynak ve konsol gözlemleri ayrı devam paketidir; özgün ham kanıtın mevcut olduğu veya final kabulün tamamlandığı şeklinde kullanılmaz.

| Dilim | Görev sırasında gözlenen sonuç | Kapanış kararı |
| --- | --- | --- |
| C1 yeni FTS sıralaması | Hashing Recall@5 78→77/105; E5 93→92/105. Kalite geriledi. | Aday reddedildi; ürün FTS koduna alınmadı. Özgün sonraki ham kayıtlar yeniden mevcutluk denetimi gerektirir. |
| C2 indeks belleği | Aynı 20.000 sentetik vektörle altı kurulum; üç düşük bellek kolunda taşma, yüksek bellekte daha kısa kurulum. Konsola yazdırılan nonzero/non-null Recall farkı filtresi boş; bu özet bütün vakaların ölçülmüş sıfır olduğunu kanıtlamaz. | Sonuç **INCONCLUSIVE**: yüksek kolda bellekte kalmayı gösteren bağımsız olumlu şahit yok. Yeni bellek zorunluluğu/göç eklenmedi. |
| S11 kalıcı silme kuyruğu | İlk adayda 24 gerçek PG vakası; gerçek işlem kimliği koruması kaldırılınca beklenen assertion hatası. Mevcut satırların korunması ve yinelenen anahtarda tüm göçün geri alınması için iki ayrı senaryo geçti. | Uygulamaya entegre edilmedi; R3 son kaynak kabulü, tam API ve gerçek CLI çalışması açık. |
| S11 yerel dosya silme | Storage karşılaştırmasında baseline beklenen assertion hatasını verdi, aday geçti; özgün dosya/hash kanıtları artık mevcut değil. Konsolda 44 izole test/22 alt vaka ve 17 ayrı CLI sözleşme testi başarı özeti var. | Bunlar aday ölçümleridir. Son biçimlenmiş kaynak Ruff denetiminden geçti; bu son sürümün tam API ve gerçek CLI kabulü yapılmadı. |

S11'in tehdidi koşulludur: yerel depoda önceden var olan/taşınmış sembolik bağlantı veya dizine işletim sistemi düzeyinde yazma yetkisi gerekir. Normal öğrenci yükleme API'sinin böyle bir bağlantı oluşturabildiği gösterilmedi. Yeni kuyruk da geçmiş yetimleri, belirsiz yükleme COMMIT'ini, fiziksel DB klonunu veya bütün yedeklerde hukuki imhayı otomatik çözmez.

Kurtarma tamamlandı: 12 özgün/ara sürüm kaynak dosyası kalıcı proje çıktı paketine kopyalandı; 11 dosya tarihsel SHA256 ile eşleşti. Timeout testinin tam metni kurtarıldı, bağımsız beklenen özeti bulunamadı. İki takip patch metni korundu; gerçek claim regresyon patch'i ve son biçimlenmiş v3 kaynakları eksik. Kaynaklar farklı aday aşamalarındandır ve tamamlanmış bir entegrasyon sürümü oluşturmaz. S10 için ayrıca 145 yapıt ve 435 kaynak bağının mevcut dosya özetleri eşleşti.

Kapanış belge denetimi 195 belgeyi taradı; 33 canlı iddia ölçümle eşleşti. İlk girişim UV önbelleğine yazma izni nedeniyle tamamlanamadı; görev için ayrı geçici önbellekle tekrar **PASS** verdi. API ve tarayıcı sayıları bu denetimde yalnız toplandı/listelendi; web testleri ve API tip denetimi çalıştı.

## Yeniden başlatıldığında sıra

1. Kurtarılan S11 kaynaklarını kalıcı bir çalışma dizininde, kayıtlı hash ve eksik dosya listesiyle uzlaştır. Eksik ham kanıtları yeni koşu olarak yeniden üret; eski sonucu yeni sonuç gibi yazma.
2. İncelenmiş kaynakları yeni ve kimliği bağımsız doğrulanmış sentetik DB/storage hedefine bağla. Rol haklarını değiştirmeden 23 göç, gerçek PG/XID/yarış, tam API ve gerçek yönetim CLI kabulünü tamamla. Eski test fixture'ının genel DROP/CREATE/ALTER ROLE yolunu otomatik çalıştırma.
3. S11'in tam kaynak kanıtı, gizlilik envanteri, kurumsal saklama sınırları ve ayrı yönetişim kaydını tamamladıktan sonra yerel commit oluştur. Önceki .ai kayıtlarını veya başarısız kanıtları değiştirme.
4. Sonraki parser incelemesindeki PPTX açılmış arşiv sınırı ve kod ayrıştırma regex süre maliyeti iddialarını küçük, süre/bellek sınırlandırılmış deneylerle doğrula. Statik şüpheyi düzeltilmiş güvenlik açığı sayma.
5. Gerçek Supabase oturumu/özel Storage, gerçek model ve bağımsız insan değerlendirmesi, barındırma/geri dönüş ve kurumsal KVKK/GDPR kararlarını ayrı kabul olarak sürdür.

## Yayın engeli

Otomatik onay incelemesi, S9 kodu ve sentetik kanıt arşivinin herkese açık GitHub deposuna gönderimini açık paylaşım onayı bulunmadığı gerekçesiyle reddetti. Önceki kullanıcı sorusu yanıtlanmadan bu commit'ler veya onları içeren yeni commit'ler gönderilmez; başka dal veya araçla aşılmaz. Ayrıntılı PR açıklamasının yayımlanması da ayrı beklemektedir. Teknik gizlilik iyileştirmeleri hukuki uygunluk sertifikası değildir.
