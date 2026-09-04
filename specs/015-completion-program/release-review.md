# 015 entegrasyon ve teslim incelemesi

## Yerel adayın kapsamı

015, yerel013 ve014 üzerine kurulur. Temel `4e948d5fc5ec42f447838cb1e95e22f5881cb0fa`; doğrulanmış uzak main `ba69ff9eec0a2867614dd145eb6e995f6c0af5ac`. Merge-base main ile aynıdır; 013/014 onun doğrudan ardıllarıdır. Bu rapor main'e birleşim veya canlı yayın kanıtı değildir. Kesin015 commit, bu raporu içeren commit olarak AI dossier SELF bağıyla kaydedilir.

## İnceleyiciye sunulacak değişiklik

Öğretmen onaylı soru yazımı ve öğrencinin kaynaklı sınav yolculuğu, yenilemede yanıt taslağı/alıştırma geri bildirimi kurtarma ile tamamlanır. Kaynağı değişen sorudan etkilenen sınav sürümüne gidilir. Model varsayılanları hizalanır; çevrimdışı erişim hazırlığı gerçek kalite kanıtından ayrılır. Değerlendirme araçları gerçek sunucu/çağrı kanıtı olmadan başarı etiketi üretmez ve yanlış veri tabanına yazmayı reddeder.

Bir main hedefli PR, yalnız015 farkını değil main→aday bütün013+014+015 farkını kapsamalıdır. Main ilerlerse yeni base/candidate doğrulaması gerekir; eski test veya dossier yeni birleşim kanıtı olarak kullanılmaz. Mevcut gelen0016 çakışması ve ayrılmış0017 bu dala ithal edilmez. Başka çalışma ağaçları silinmez veya yeniden numaralandırılmaz.

## Şema ve geri dönüş

Bu dalda0001–0015,0018 ve0019 vardır;015 yeni göç eklemez. Temiz015 test veri tabanında sıralı uygulama ve mevcut SQL/RLS testleri gerekir. Canlı uygulanmış göçlerle eşleşme staging erişiminde ayrıca doğrulanmalıdır.

Öğrenci çalışma alanını kapatmak için STUDENT_ASSESSMENT_WORKSPACE_ENABLED=false ve API yeniden başlatma kullanılır. Temel sınav bitirme, kaynak ve süre korumaları korunur. Değerlendirme yüzeyini kapatmak için EVAL_RUNTIME_ENABLED=false ve değerlendirme sırlarının kaldırılması gerekir. Veriler silinmez, cevaplar yeniden yazılmaz. Gerçek geri dönüş denemesi yapılmadan canlı rollback tamamlandı denmez.

## Yayın kapıları

| Kapı | Kanıt yeri / mevcut sınır |
|---|---|
| Kod, API, web, tarayıcı, sözleşme | verification.md içindeki yeni sonuçlar; kesin adayla bağlanacak |
| İnsan pedagojik kabul | evaluation/acceptance; bağımsız etiketler bekleniyor |
| Gerçek model erişimi/kalitesi | Ayrı anahtar ve sınırlı ön kontrol; gerçek koşu henüz yok |
| Container | Yerel Docker çalıştırıcısı bulunamadı; container build koşulmadı |
| PR CI | PR açılmadı, aday CI kanıtı yok |
| Gerçek kimlik/depolama/işçi | Staging erişimi ve üç rol gerçek akışı bekleniyor |
| Canlı yedek/PITR/geri yükleme | Staging/üretim üzerinde koşulmadı; yerel deneme bunun yerine geçmez |
| Canlı URL/öğretmen teslimi | Dağıtım ve öğretmen kabulü henüz yok |

## Hazır olan dış girdi paketi

Gerçek model anahtarı güvenli yerel ortam veya gizli değer kasasına konmalıdır, sohbet/rapora yazılmaz. Öğretmen örnek materyalin ders kapsamını ve beklenen kaynakları onaylar; iki bağımsız değerlendirici model cevaplarını mevcut etiket şemasıyla işaretler. Uygulama, test, kalibrasyon, main, staging ve teslim durumları docs/completion-program.md içinde ayrı tutulur.
