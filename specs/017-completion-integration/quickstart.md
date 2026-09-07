# 017 yerel ve teslim kabulü

Bu aday main ba69ff9 üzerine013–016 ile PR23/25'i bütünleştirir. Tamamlanmış source-of-truth ve test sonuçları verification.md'de; eski015 sonuçları yeni ölçüm diye kullanılmaz.

## Ortam

Mevcut kilitli kurulum yönergelerini kullanın. Yeni bir yerel test PostgreSQL kümesi/veritabanı seçin; fixtures o test veritabanını sıfırlar. 017 kanıt ortamı127.0.0.1:55447, ayrı dou017_* ve dou_synapse_e2e_dou017 adlarını kullanır; canlı/veri içeren veritabanı kullanılmaz.

Migration'lar dosya adı sırasıyla uygulanır. PR23'ün0016_api_contract_admin_access dosyası dahil; eski009/010 dalındaki farklı0016_assessment_integrity bu adayda değildir.0020_policy_audit_cascade ders silme sırasında yetim audit yazımını önler; normal politika değişikliği denetimi korunur. Staging'deki uygulanmış migration kimlikleri ayrıca karşılaştırılmalıdır.

Yerel sentetik tarayıcı kabulünde QUESTION_AUTHORING_ENABLED=true ve STUDENT_ASSESSMENT_WORKSPACE_ENABLED=true, DEV_AUTH_ENABLED=true, LLM_FAKE_PROVIDER=true, EMBEDDING_PROVIDER=hashing kullanılır. EVAL_RUNTIME_ENABLED=false kalır. Bu ayarlar production yapılandırması değildir. Gerçek kalite için evaluation/acceptance/README.md izlenir; anahtarlar rapora veya sohbete yazılmaz.

## Öğretmen → öğrenci kontrolü

1. Eğitmen ders açar, öğrenci ekler ve örnek kaynak yükler. Belge işlenip sayfa/slayt bağlamı görünür.
2. Öğrenme çıktısı ve zorlukla soru üretir; taslağı düzenleyip onaylar ve sınav yayımlar.
3. Öğrenci konu veya yayımlanmış sınavı seçer. Yenileme sonrasında oturum/yanıt taslağı bulunur.
4. Alıştırmada ipucu sınırı0 iken ipucu verilmez;1 iken yeni basamak sunulmaz. Ekran açıkken sınır düşürülmesi aynı ipucunu çoğaltmaz.
5. Soru sonradan görünmez olduğunda boşalan oturum yine bitirilebilir.
6. Tamamlanmış sonuç başka sekmede sınav başlayınca odağa dönüşte gizlenir. Asistanın tek başına kapatılması sonuç erişimini engellemez; sonuç izni sunucudan yeniden okunur.
7. Kaynak dayanağı doğrulanamayan AI değerlendirmesinde puan/yorum gösterilmez. Kod/hata bulma cevaplarını gerçek öğretmen rubriğiyle ayrıca inceleyin.
8. Eğitmen kaynağı değiştirir; etkilenen soru ve sınav sürümüne ulaşır.

## Operasyon ve belgeler

/docs yerel CSS/JS kullanır; /openapi.json platform yöneticisi yetkisi ister. Container testi tüm belge varlıklarının imaj içinde olduğunu ağsız doğrular. Hazırlık yoklaması /health/ready'dir.

Kabul paketi, dışa yazdığı assessment_cases.json dosyasının hash'ini manifestte taşır. Gerçek sample yalnız aynı temiz adaya bağlı kanıtla kabul edilir. Skorlayıcı mevcut insan sonuçlarını ezmez; kısmi çıktı varsa koruyup yolunu bildirir. Yeni bir boş hedef dizini kullanın.

## Güvenli durdurma ve kalan girdiler

Yeni arayüzleri kapatmak için authoring/workspace bayraklarını false yapıp API'yi yeniden başlatın; süre/kaynak/sınav yardım korumalarını kaldırmayın. Değerlendirme runtime'ını ve sırlarını kapalı tutun.0020 veri silmez; geri dönüş için eski bozuk audit trigger'ını yeniden etkinleştirmek gerekmez. Gerçek geri dönüş kanıtı staging'de ayrı üretilir.

Teslim: onaylı ders paketi, gerçek model/insan başarı raporu, öğrenci/eğitmen kılavuzları ve aynı sürümün çalışan URL'si. Yerel testler gerçek model veya canlı kabul anlamına gelmez.
