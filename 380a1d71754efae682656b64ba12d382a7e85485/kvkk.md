# KVKK Aydınlatma Metni

**DOU-Synapse — Ders ve Sınav Asistanı**
Son güncelleme: 9 Ağustos 2026

> **Bu metin, sistemin kodunda gerçekten var olan veri akışını anlatır.** Her iddianın
> karşılığı depoda bir dosya ve satırdır; kaynaklar parantez içinde verilmiştir. Henüz
> uygulanmamış olan konular §8'de **açıkça "uygulanmadı"** olarak listelenmiştir —
> uygulanmamış bir korumayı uygulanmış gibi yazmak, aydınlatma metninin amacını
> ortadan kaldırır.
>
> Bu bir bitirme projesidir. Metin, 6698 sayılı Kişisel Verilerin Korunması Kanunu'nun
> aydınlatma yükümlülüğünü karşılamak üzere **teknik gerçeği** anlatır; kurumsal
> yürürlüğe girmeden önce üniversitenin hukuk birimince gözden geçirilmelidir.

---

## 1. Veri sorumlusu

Doğuş Üniversitesi Bilgisayar Mühendisliği Bölümü bünyesinde yürütülen COME 491/492
bitirme projesi kapsamında geliştirilen DOU-Synapse uygulaması.

Başvuru: bu metnin §7'sindeki yol.

---

## 2. İşlenen kişisel veriler

Sistemin veritabanında tutulan **her** kişisel veri aşağıdadır. Liste
`supabase/migrations/` altındaki şemadan çıkarılmıştır.

| Veri | Nerede tutulur | Nasıl toplanır |
|---|---|---|
| Ad soyad | `profiles.full_name` | Girişte kimlik sağlayıcıdan |
| E-posta adresi | `profiles.email` | Girişte kimlik sağlayıcıdan |
| Kullanıcı kimliği (UUID) | `profiles.id` | Sistem üretir |
| Ders üyeliği ve rolü | `course_memberships` | Eğitmen ekler |
| **Sohbet mesajlarınız** (sorularınız ve size verilen cevaplar) | `chat_messages.content` | Siz yazarsınız |
| Sohbet oturumu ve Sokratik kademe durumu | `chat_sessions` | Sistem üretir |
| **Sınav cevaplarınız** | `answers.given` | Siz yazarsınız |
| Değerlendirme geri bildirimi (puan, eksik noktalar) | `answers.feedback` | Sistem üretir |
| Konu bazlı çalışma puanı | `mastery.score`, `mastery.answer_count` | Sistem hesaplar |
| Yüklediğiniz materyaller ve içerikleri (eğitmen) | `documents`, `chunks` | Eğitmen yükler |
| İstek ölçüm kaydı | `request_logs` | Sistem üretir — **§3'e bakın** |

**Özel nitelikli kişisel veri işlenmez.** Sistem T.C. kimlik numarası, sağlık, biyometrik
ya da benzeri veri toplamaz ve bunlar için bir alan da yoktur.

---

## 3. Soru metinleriniz ölçüm kayıtlarına YAZILMAZ

Bu, sistemin en somut gizlilik güvencesidir ve bir filtreye değil **şemanın kendisine**
dayanır.

Sistem her istek için bir ölçüm kaydı tutar (`request_logs`). Bu tablonun **serbest metin
alanı yoktur** — soru metnini yazacak bir sütun bulunmadığı için yazılması mümkün değildir.
Tablonun tam sütun listesi:

```
id · course_id · user_id · route · mode · status · http_status
latency_ms · token_count · cache_hit · created_at
```

`route` alanı bir yol şablonudur (`POST /courses/{course_id}/chat`), sorunun kendisi değil.

Kaynak: `supabase/migrations/0003_chat.sql`, `apps/api/app/models/chat.py` (`RequestLog`).
Kodda kaydı yazan çağrının yanında şu not durur:
*"Soru metni hiçbir log satırına yazılmaz (FR-035 redaksiyonu)"*
(`apps/api/app/api/chat.py`).

Uygulama günlükleri (JSON log) de soru metni içermez; ders, oturum ve kademe kimlikleri
gibi tanımlayıcılar yazılır.

---

## 4. Sohbetlerinizi eğitmeniniz okuyamaz

Sohbet mesajlarınıza erişim veritabanı düzeyinde kısıtlıdır: `chat_messages` üzerindeki
okuma politikası yalnız **oturumun sahibine** açıktır. Eğitmene okuma yetkisi
**bilinçli olarak verilmemiştir.** Migration'da gerekçesi şöyle yazılıdır:

> "Öğrencinin hocasına sorma çekindiği soruyu sisteme sorabilmesi ürünün gerekçelerinden
> biri, eğitmenin bunu satır satır okuyabilmesi bunu bozar." (`0003_chat.sql`)

Eğitmenin gördüğü analitik ekranı bu tablodan değil, serbest metin taşımayan
`request_logs` tablosundan okur (`0005_analytics.sql`). Yani eğitmen *"kaç soru
reddedildi"* sorusunun cevabını alır, *"kim ne sordu"* sorusunun cevabını alamaz.

**İzolasyon iki katmanlıdır:** uygulama sunucusunda her istekte ders üyeliği doğrulanır ve
PostgreSQL satır düzeyi güvenliği (RLS) aynı oturumda ikinci katman olarak çalışır.
Uygulama, tabloların sahibi olmayan ve güvenliği atlama yetkisi bulunmayan ayrı bir
veritabanı rolüyle bağlanır; testler de aynı rolle koşar ve bu izolasyon her sürekli
entegrasyon koşusunda ayrıca kanıtlanır (`supabase/tests/rls_isolation.sql`).

---

## 5. Üçüncü taraflara aktarım

### Dil modeli sağlayıcısı (Groq / Google Gemini)

Bir soru sorduğunuzda dil modeli sağlayıcısına **yalnız şunlar** gider:

- Sistem talimatı (sabit metin, kişisel veri içermez)
- Ders materyalinden getirilen parçalar — dosya adı, sayfa/slayt bilgisi ve metin
- **Sorunuzun metni**
- Sokratik modda **kendi deneme yazınız**

**Gitmeyenler:**

- Adınız, e-posta adresiniz, kullanıcı kimliğiniz
- Ders kimliği, oturum kimliği
- Sınav geçmişiniz, puanlarınız, mastery kaydınız
- Diğer sohbetleriniz

Sağlayıcıya giden istek tek bir yerde kurulur ve gövdesi yalnız yukarıdaki alanlardan
oluşur: `apps/api/app/modules/generation/prompts.py` → `build_request()`. Kişisel verinin
istek gövdesine girebileceği başka bir yol yoktur.

Sağlayıcının veriyi kendi tarafında ne kadar sakladığı **o sağlayıcının politikasına
tabidir** ve bizim denetimimiz dışındadır. Bu yüzden asistana kişisel bilgi yazmayın:
soruların ders içeriğiyle sınırlı kalması hem ürünün amacı hem gizliliğinizin lehinedir.

**Anahtar tanımlı olmadığında hiçbir yere veri gitmez.** Sistem o durumda deterministik
yerel bir sağlayıcıya düşer ve dış ağa çıkmaz (çevrimdışı demo bu şekilde çalışır).

### Diğer

Sistem reklam, analitik izleyici ya da üçüncü taraf çerezi kullanmaz. Veriler yurt
dışında barındırılan altyapıda tutuluyorsa (Supabase/bulut sağlayıcı) bu, hizmetin
sağlanması amacıyladır.

---

## 6. Saklama süresi

| Veri | Süre |
|---|---|
| Profil, ders üyeliği | Hesap silinene ya da üyelik sonlandırılana kadar |
| Sohbet mesajları, sınav cevapları, mastery | **Ders silinene kadar** |
| Materyaller ve parçaları | Eğitmen silene ya da ders silinene kadar |
| İstek ölçüm kayıtları | Ders silinene kadar |

Bir ders silindiğinde o derse bağlı sohbetler, mesajlar, sınav oturumları, cevaplar,
mastery kayıtları, materyaller ve ölçüm kayıtları **veritabanı düzeyinde birlikte
silinir** (şemadaki `ON DELETE CASCADE` bağları). Bir kullanıcı silindiğinde ona ait
sohbet ve üyelik kayıtları da aynı şekilde silinir.

**Dürüst sınır:** bugün **zamana bağlı otomatik bir silme mekanizması YOKTUR.** "90 gün
sonra silinir" gibi bir kural kodda tanımlı değildir; silme, dersin veya hesabın
silinmesine bağlıdır. Kurumsal yürürlükte bir saklama süresi belirlenirse bunun ayrıca
uygulanması gerekir (§8).

---

## 7. Haklarınız ve başvuru

KVKK m.11 uyarınca; kişisel verilerinizin işlenip işlenmediğini öğrenme, işlenmişse buna
ilişkin bilgi talep etme, işlenme amacını ve amaca uygun kullanılıp kullanılmadığını
öğrenme, yurt içinde/yurt dışında aktarıldığı üçüncü kişileri bilme, eksik veya yanlış
işlenmişse düzeltilmesini isteme, silinmesini veya yok edilmesini isteme, bu işlemlerin
aktarıldığı üçüncü kişilere bildirilmesini isteme, münhasıran otomatik sistemlerle
analiz edilmesi suretiyle aleyhinize bir sonuç ortaya çıkmasına itiraz etme ve zarara
uğramanız hâlinde giderilmesini talep etme haklarına sahipsiniz.

**Otomatik karar hakkında:** sistemin ürettiği konu bazlı puan **resmî bir değerlendirme
değildir.** Notunuzu etkilemez; yalnızca hangi konuya çalışmanız gerektiğine dair bir
göstergedir. Değerlendirme kararı her zaman eğitmeninize aittir (insan denetimi).

**Başvuru:** derse kayıtlı olduğunuz eğitmene ya da bölüm sekreterliğine yazılı olarak
başvurabilirsiniz. Başvurunuz en geç 30 gün içinde sonuçlandırılır.

---

## 8. Henüz uygulanmayanlar

Bu bölüm bilinçlidir. Aşağıdakiler tasarlanmış ama **bugün kodda yoktur**; kurumsal
kullanım öncesinde tamamlanmalıdır.

| # | Konu | Durum |
|---|---|---|
| 1 | **Kullanıcının kendi verisini indirmesi/sildirmesi** için arayüz | Uygulanmadı. Silme bugün ancak ders/hesap silinerek gerçekleşir |
| 2 | **Zamana bağlı otomatik saklama süresi** (örn. dönem sonunda sohbetlerin silinmesi) | Uygulanmadı (§6) |
| 3 | **Aydınlatma metninin uygulama içinde bir sayfa olarak gösterilmesi** ve girişte onay alınması | Uygulanmadı — metin hazır, sayfa yapılacak |
| 4 | **Gerçek kimlik doğrulama.** Bugün geliştirme kimliği (`DEV_AUTH`) kullanılıyor; imzasız kimlik kabul ediliyor | Uygulanmadı. **Bu haliyle gerçek öğrenci verisiyle çalıştırılmamalıdır** |
| 5 | Denetim izi (kim hangi kişisel veriye ne zaman erişti) | Uygulanmadı |
| 6 | Veri işleyen sıfatıyla dil modeli sağlayıcılarıyla sözleşmesel çerçeve | Kurumsal konu, proje kapsamı dışında |

**4. madde bu metnin en önemli uyarısıdır:** sistem bugün gerçek kimlik doğrulaması
olmadan koşmaktadır ve **gerçek öğrenci kişisel verisiyle üretimde kullanılmaya hazır
değildir.** Demo ve değerlendirme, sabit demo hesaplarıyla yapılır.

---

## İlgili belgeler

- [Öğrenci Kılavuzu](student-guide.md) · [Eğitmen Kılavuzu](instructor-guide.md)
- [Mimari — Güvenlik](../ARCHITECTURE.md#6-güvenlik)
