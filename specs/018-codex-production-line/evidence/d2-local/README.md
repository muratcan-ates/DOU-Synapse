# D2 iş sahipliği ve kesinti kabulü

0026 kaynak hash'i3e15eaa33f8bc8fba2f7a6d6e84692d213cc696ccd8367fad73152e79f2b61d3.
Son çalışma kodu stage02'den birebir entegre edildi. Lease/token/revision denetimi,
DB dışında hazırlama, kısa kesinleştirme, üç deneme ve kontrollü iptal bırakması var.

İlk aday91 testi geçti. Bağımsız incelemede eski belge A silinince halef B'nin
lineage FK temizliğinin yanlış revision artışına yol açtığı bulundu. Gerçek API
upload/replacement/DELETE testinde2!=1 ile kırmızı oldu; yalnız ilişki alanı kaynak
revizyon karşılaştırmasından çıkarıldı. Gerçek kaynak/supersession koruması kaldı.
V2'de98 test geçti:10 iş sahipliği/yarış, lineage regresyonu,6 gerçek app/worker
yetki testi ve mevcut işleme uçları dahil. Kullanıcı processing claim oluşturamaz,
job güncelleyemez, yabancı/öğrenci/null kimlikle işi tekrar başlatamaz.

Göç çalışan veya mükerrer işleri bulunan iki yeni DB'de gerçekP0001 verdi; önceki
veri/şema/index/policy/retry tanımı hashleri değişmedi. Üçüncü DB'de geçerli eski
pending/failed/completed satırları korundu; yeni alanlar güvenli varsayılanlarla ve
doğrulanmış constraint/index ile eklendi. Üç geçici DB sonrasında kaldırıldı.

Sekiz gerçek süreç senaryosu: asyncio iptali, SIGTERM süresi içinde bitiş, süreyi
aşan işin bırakılması, SIGKILL sonrası DB saatine göre devralma, iki işleyicinin
tek işi alması, SIGSTOP/SIGCONT ile eski işleyicinin geç başarı/hata/heartbeat'inin
reddi, zincirli hassas hata canary'si ve worker başlangıcında expired quota silme.
Canlı quota penceresi değişmedi. V2 gerçek koşu19.919s ve sekiz senaryo başarılı.

İlk süreç koşusu sekiz davranışı geçmesine rağmen parent log denetiminden kaldı;
genel sonucu failed korunur. Ham parent log atıldığından tam eşleşme sonradan
kanıtlanamaz. V2 yalnız gerçek fixture uploadunun bilinen app.request rota UUID'sini
ayrı metadata olarak ölçtü; içerik/auth/bağlantı/parola yok, kimlik yalnız bu alanda.
Worker denetimleri aynıdır. Bu, uygulama stdout'unun anonim olduğu anlamına gelmez.
Sonraki rota minimizasyonu ayrı kaynak değişikliğidir ve bu eski ölçüme dahil değildir.

Bu kontrollü yerel süreç kabulüdür. asyncio.to_thread içindeki bloke parser/model
thread'ini iptal öldürmez; asyncio.run kapanışı bunu bekleyebilir. Kesin duvar saati
shutdown garantisi, harici I/O'da exactly-once,60 saniyelik periyodik TTL ölçümü,
scale-to-zero zamanlayıcı veya üretim kurtarma/saklama SLA'sı iddia edilmez.
