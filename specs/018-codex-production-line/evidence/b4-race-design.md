# B4: silme ile devam eden sohbet yarışı

## Ölçülmüş sonuç

Yalnız gerçek HTTP/SQL transaction/RLS yolu kullanıldı; model beklemesi asyncio.Event ile taklit edildi. Ders/tüm geçmiş DELETE yanıtı model serbest bırakılmadan önce 200 döndü. Önceden başlayan yeni POST sonrasında 200 dönerek bir oturum ve iki mesaj bıraktı. Profil DELETE/me de 200 başarı sonrasında aynı veriyi bıraktı. Önceden commit edilmiş tekli sohbetin silinmesinde yeniden oluşturma görülmedi. Regresyon sonucu mevcut kodda beklenen 3 failed / 1 passed, 2.00 saniye. Geçici dou018_delete_race DB fixture teardown tamamlandı.

Kanıt: b4-delete-race-baseline.log. Test, S kapanış koleksiyonuna girmemesi için b4-test_chat_deletion_race.py olarak bu klasörde tutuluyor; üretim dosyaları değişmedi. Hash'ler b4-race-evidence-hashes.json içinde.

## Neden

- api/chat_history.py:36–50 yeni ChatSession satırını modelden önce INSERT/flush eder. core/db.py:117–127 ve api/deps.py:66–84 aynı transaction'ı endpoint bitene kadar açık tutar; commit yanıt öncesidir.
- api/chat.py:451–490 provider I/O yapar; :519–559 state/cache/messages/request-log yazar. Provider sonrası mevcut kontrol yalnız öğrenci sınav kilididir (:493–509).
- api/privacy.py:45–58 DELETE yalnız o SQL statement'ına görünür ChatSession satırlarını kapsar. Diğer transaction'da henüz commit edilmemiş yeni oturum görünmez; rowcount=0 başarılı bir silmedir.
- Tekli mevcut oturum yüklemesi api/chat_history.py:55 plain SELECT'tir; silindikten sonra yeniden INSERT yapılmaz. Mesaj FK'sı 0003_chat.sql:68 ve INSERT RLS'si :200–208 oturumu olmayan mesajı engeller. Mevcut kod bu son-yazım durumunu kontrollü alan hatasına çevirmiyor.
- Profil yolu api/privacy.py:292 önce geçmişi tarar, :293–309 sonra üyelikleri iptal edip profil e-postasını değiştirir. Yeni chat INSERT'in profiles FK kilidiyle bu güncellemenin etkileşimi son yazımın önce commit olmasına izin verir; ölçümde DELETE başarıyla bittiğinde sohbet kalmıştır. Boş DELETE taramasını üyelik iptali tek başına geri alamaz.

## Çözüm karşılaştırması

1. Modelden önce kullanıcı bazlı transaction advisory lock almak ve DELETE'i aynı lock'a bağlamak küçük bir patch'tir, fakat tüm model/retrieval I/O boyunca silmeyi bekletir; DELETE istemci timeout'una, aynı kişinin başka dersteki işlemlerinin gereksiz beklemesine ve kötü gizlilik UX'ine yol açar. Finalde yalnız lock/SELECT eklemek görünmez yeni oturum sorununu çözmez.
2. Öneri: kapsamlı kalıcı silme nesli + yalnız final/delete kritik bölümünde kısa DB lock. Model I/O sırasında lifecycle lock tutulmaz. Yeni oturum da final karara kadar INSERT edilmez; aksi halde profil FK kilidi ile final lifecycle lock arasında döngüsel bekleme yaratılabilir.

## Dar tasarım

- Yeni küçük tablo: sahip user_id, opsiyonel course_id, monoton revision; kullanıcı-geneli ve kullanıcı+ders satırları birbirinden ayrı. User/course FK cascade, own-user RLS, yalnız API'nin gerekli SELECT/INSERT/UPDATE yetkileri. Sabit scope benzersizliği (ör. UNIQUE NULLS NOT DISTINCT); payload, başlık, model çıktısı tutulmaz. Yeni migration numarasını root tahsis eder; 0021/22/23 rezerve.
- POST modelden önce o kullanıcının global ve ilgili ders revision çiftini okur (satır yoksa 0). Yeni sohbet UUID'li transient ORM nesnesi olarak hazırlanır; session.add/flush final kontrole ertelenir. Model/retrieval I/O yeni chat FK kilidi tutmaz.
- Final: kısa kullanıcı advisory lock al, global+ders revision çiftini taze SQL ile karşılaştır. Değiştiyse kontrollü 409 chat_history_changed; cache/mesaj/oturum yazma, cevap metnini gönderme. Lock transaction commit/rollback'e kadar kalır.
- Aynı final bölümde aktif üyelik/audience taze sorgulanır. session_id gönderilmişse oturum varlığı aynı sahip+ders filtresiyle yeniden okunur; eski SQLAlchemy identity-map nesnesine güvenilmez. Silinmişse kontrollü 409; oturum yeniden yaratılmaz.
- Ders geçmişi DELETE yalnız o dersin revision'ını artırır; tüm geçmiş/profil DELETE global revision'ı artırır. Silinen satır 0 olsa da revision artışı şarttır. Artış ve DELETE/profil revokasyonu aynı transaction ve kısa kullanıcı lock içinde gerçekleşir.
- Tekli DELETE aynı kısa lock altında hedef satırı siler; global/course revision artırmaz. Böylece aynı kişinin farklı oturumu veya başka derste başlayan yeni sohbeti iptal edilmez. Devam eden hedef session_id final varlık kontrolünde durur.
- Profil handler'ında lock profil durumu kontrolünden önce alınır; revision artışı, sohbet silme, üyelik iptali ve profil maskeleme aynı kritik bölümde kalır.

## Kabul matrisi

- Yeni POST beklerken ders DELETE tamamlanır: hedef ders yazılmaz; başka dersin bekleyen POST'u tamamlanabilir.
- Tüm geçmiş DELETE: kullanıcının tüm derslerinde önceden başlamış POST'lar 409; başka kullanıcının POST'u etkilenmez.
- Tekli DELETE: hedef session_id devamı 409; aynı dersteki başka oturum/yeni sohbet ve başka ders etkilenmez.
- Profil DELETE: 200 sonrası bekleyen chat verisi yok; üyelikler revoked, profil maskeli; yeni POST üyelik kapısında reddedilir. Önceden var olan akademik kayıtlar korunur.
- Ters sıra: POST final kritik bölümünü önce tamamladıysa DELETE onun yazdıklarını da kaldırır. Yeni, silmeden sonra kabul edilmiş POST normal çalışabilir.
- Öğrenci ve eğitmen, ilk ve devam turu; ilk açılış, cache/refusal ortak final yolu; DELETE hata/rollback revision'ı kalıcılaştırmaz; epoch ve kontrol bypass negatif mutasyonu kırmızıya düşer.

En dar ürün sahipliği: yeni migration + dar lifecycle helper; api/chat.py, api/chat_history.py, api/privacy.py ve yeni yarış testi. Eski S üretim dosyaları şu anda değişmedi. Frontend tekli/ders silme UI'sı sunucudaki bu sınırdan sonra bağlanmalı.
