# Danışman videosu — çekim senaryosu

> Hocanın isteği (6 Ağustos toplantısı): *"10-15 dakikalık, adım adım gösteren bir video
> çekin. Şu ana kadar ne yaptığınızı. Şu an telefondan bağlandım, görmekte zorlanıyorum.
> Videoyu OneDrive'a yükleyip linkini paylaşın."*
>
> Hedef süre: **13-15 dakika.** Aşağıdaki bölüm süreleri toplamı 14 dakika.

> **15 Eylül güncellemesi.** Bu senaryo 8 Ağustos'ta yazıldı ve o günün durumunu
> anlatıyordu. Aradan geçen beş haftada cevap üretme hattı bağlandı, gerçek modelle
> koşuldu ve demo yığını değişti. Güncellenen yerler: portlar ve komutlar, test sayısı,
> "tasarım önizlemesi" bölümü (artık **yanlış** — hat çalışıyor), kapanış tarihleri ve
> çekim öncesi kontrol listesi. Bu metinle çekim yapmadan önce "Çekimden önce"
> bölümündeki jeton kotası maddesini mutlaka koştur.

---

## Çekimden önce

**Ekran ve okunabilirlik.** Hoca videoyu telefondan da izleyebilir. Terminal yazı boyutunu
en az 16pt yap, tarayıcı zoom'unu %125'e al. Ekranı 1920x1080'de kaydet.

**Masaüstünü temizle.** Alakasız sekmeleri, bildirimleri ve WhatsApp'ı kapat. Rahatsız
Etme modunu aç.

**Repo public olmalı.** Videoda hocanın kendi bilgisayarına klonlayabileceğini
göstereceksin. Depoyu private yaparsan bu adım hoca için çalışmaz — private yapacaksan
önce hocayı collaborator olarak ekle, videoda da bunu söyle.

**Prova et.** Kurulum bölümünü bir kez baştan sona koştur. Aşağıdaki komutlar bu makinede
doğrulandı ama senin terminalinde `PATH` farklı olabilir.

**Jeton kotasını kontrol et — kaydı ortasında kesebilecek tek sessiz risk bu.** Öğrenci
başına günlük tavan 50.000 jeton ve istek başına ~4.500 gidiyor; aşılırsa ekranda
"Günlük kişisel AI kullanım kotan doldu" yazar. Çekimden hemen önce koştur:

    psql -d dou_demo -Atc "select coalesce(sum(coalesce(charged_tokens,reserved_tokens)),0) \
      from ai_token_reservations where user_id='22222222-2222-2222-2222-222222222222' \
      and created_at >= date_trunc('day', now() at time zone 'Europe/Istanbul') at time zone 'Europe/Istanbul'"

Sonuç **35.000'in altında olmalı**. Üstündeyse ya gece yarısını bekle ya ikinci sentetik
öğrenciyle çek.

**Önbellek dolu olsun.** Önbellekten dönen cevaplar jeton harcamaz ve internet kesilse
bile gelir. Sorulacak soruların sabit listesi `docs/demo-script.md` içinde; **sahnede
sorulmaması gerekenler** de orada yazılı (materyalde karşılığı olmayan sorular).

**Tek çekimde, düzeltmeden.** Hoca "otur 15 dakika bir şeyler anlat kalk, hiç düşünmene
gerek yok" dedi. Cilalı olmasına gerek yok; anlaşılır olması yeterli.

---

## 0:00-1:00 — Ne yaptığımız, tek cümlede

**Göster:** Sadece kendini ya da proje README'sini.

**Söyle:**

> Hocam merhaba. CourseGPT'nin şu ana kadarki halini adım adım göstereceğim.
>
> Projeyi tek cümleyle şöyle tarif ediyoruz: sizin yüklediğiniz ders materyaliyle
> **sınırlı** çalışan, her cevabında hangi dosyanın kaçıncı sayfasına dayandığını
> gösteren, ve öğrenciye cevabı doğrudan vermek yerine Sokratik yöntemle kendi cevabını
> buldurmayı esas alan bir ders asistanı.
>
> Ana ilkemiz şu: **kaynak yoksa cevap yoktur.** Materyalde karşılığı olmayan bir soruya
> sistem cevap uydurmuyor, bulamadığını söylüyor. Bunu bir hata değil, tasarlanmış bir
> davranış olarak kuruyoruz.

---

## 1:00-3:30 — Ne nerede çalışıyor

**Göster:** Bir çizim ya da sadece dört terminal penceresi. Karmaşık diyagram gerekmez.

**Söyle:**

> Sistem dört ayrı parçadan oluşuyor, hepsi şu an kendi bilgisayarımda çalışıyor.
>
> **Birincisi veritabanı:** PostgreSQL 16. İçinde pgvector eklentisi var, yani materyalin
> anlamsal aramaya uygun vektör temsillerini ayrı bir vektör veritabanı kurmadan aynı
> veritabanında tutuyoruz. Bunu bilinçli seçtik; ikinci bir depo, senkronizasyon derdi ve
> dersler arası veri sızma riski demekti.
>
> **İkincisi API:** Python ve FastAPI ile yazılmış backend, 8020 portunda. Ders yönetimi,
> materyal yükleme, yetkilendirme ve izolasyon burada.
>
> **Üçüncüsü worker:** ayrı bir süreç olarak koşan işleyici. Yüklenen dosyayı parçalara
> ayırıp vektörlerini hesaplayan iş burada dönüyor. Web isteğinin içinde yapmıyoruz;
> büyük bir PDF yüklendiğinde arayüz kilitlenmesin diye ayırdık.
>
> **Dördüncüsü arayüz:** Next.js ile yazılmış web uygulaması, 3020 portunda.
>
> Bir de bunların üstünde sürekli entegrasyon var: her `main`'e gönderimde GitHub'da
> testler, kod denetimi ve izolasyon kanıtı otomatik koşuyor.

---

## 3:30-7:30 — GitHub'dan indirip çalıştırma

Bu bölüm hocanın özellikle istediği kısım: kendi bilgisayarında nasıl çalıştıracağı.
Komutları **canlı yaz ve çalıştır**, hazır ekran görüntüsü gösterme.

**Söyle:**

> Şimdi projeyi sıfırdan, GitHub'dan indirip nasıl çalıştırdığımızı göstereyim. Siz de
> aynı adımlarla kendi bilgisayarınızda çalıştırabilirsiniz.

**Adım 1 — Depoyu klonla.** Terminalde yaz:

    git clone https://github.com/muratcan-ates/DOU-Synapse.git
    cd DOU-Synapse

> Depo herkese açık, yani hesap gerekmeden indirilebiliyor.

**Adım 2 — Veritabanını kur.**

    export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
    createdb dou_synapse
    for f in supabase/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -d dou_synapse -f "$f"; done
    psql -d dou_synapse -f supabase/local_dev_setup.sql
    psql -d dou_synapse -f supabase/seed_demo.sql

> Şema, satır düzeyi güvenlik politikaları ve iki demo kullanıcısı bir arada geliyor.
> Tam kurulum yönergesi depoda `specs/001-course-assistant-mvp/quickstart.md` dosyasında;
> PostgreSQL ve pgvector kurulumunu da adım adım anlatıyor.

**Adım 3 — Backend'i kur ve testleri koştur.** Bu videonun en önemli anı — burada
acele etme.

    cd apps/api
    uv venv --python 3.12
    uv pip install -e ".[dev]"
    uv run pytest -q

**Testler yeşil yandığında ekranı bir saniye tut ve söyle:**

> Şu an **ekranda yazan** sayıda otomatik test geçti (bu satırı çekim anında ekrandan
> oku, ezberden söyleme; bu yazının yazıldığı gün 2142'ydi). Bunların içinde en
> önemsediğimiz grup izolasyon testleri.
>
> Şunu göstermek istiyorum: sistemde bir dersin verisi başka bir derse **iki ayrı katmanda**
> kapalı. Birincisi uygulama katmanı: istemciden gelen ders kimliğini asla yetki belgesi
> saymıyoruz, üyeliği her istekte sunucuda doğruluyoruz. İkincisi veritabanı katmanı:
> PostgreSQL'in satır düzeyi güvenlik politikaları.
>
> Ve şuna dikkatinizi çekmek isterim: testin bir şey kanıtladığını da kanıtlıyoruz.
> Sürekli entegrasyonda politikayı **bilerek bozup** testin kırmızı yandığını
> doğruluyoruz. Yanmazsa yapı başarısız sayılıyor. Çünkü hiçbir şeyi kontrol etmeyen bir
> test de yeşil yanar.

**Adım 4 — Servisleri başlat.** Üç terminal:

    uv run uvicorn app.main:app --port 8020
    uv run python -m app.worker
    cd ../web && bun install && bun run dev

> Arayüz 3020 portunda açılıyor.

**Not (sen okumuyorsun, çekim notu):** Yukarıdaki yol "sıfırdan klonla ve çalıştır"
yoludur; hocanın istediği kısım budur ve boş bir veritabanıyla açılır. **Özellik turunu
bu yığında çekme** — materyal, soru havuzu ve önbellek orada yok. Tur için demo yığınını
kullan:

    sh scripts/demo/setup_db.sh     # dou_demo: materyaller, sorular, sentetik kullanıcılar
    sh scripts/demo/run_api.sh      # 127.0.0.1:8020 — logda "sağlayıcı: Groq" yazmalı
    sh scripts/demo/run_web.sh      # 127.0.0.1:3020

İki yığın da aynı portları kullanır; ikisini aynı anda açma.

---

## 7:30-12:00 — Çalışan özelliklerin turu

Tarayıcıda `127.0.0.1:3020` (demo yığını). Yavaş gez, her ekranda bir-iki cümle söyle.

**Giriş.** Ayşe Hoca ve Burak Yılmaz demo kartları.

> Şu an gerçek kimlik doğrulama yerine geliştirme kimlikleri kullanıyoruz; Supabase Auth
> entegrasyonu planda var ama henüz bağlanmadı. Ayşe Hoca eğitmen, Burak öğrenci.

**Ders listesi ve yeni ders.** Ayşe ile gir, ders aç.

**Materyal yükleme.** Bir PDF yükle ve durumu canlı göster.

> Dosya önce doğrulamadan geçiyor: uzantı, boyut sınırı ve **dosya imzası**. Yani uzantısı
> `.pdf` yapılmış bir çalıştırılabilir dosya reddediliyor; içeriğin gerçekten iddia edilen
> tür olduğunu kontrol ediyoruz.
>
> Kabul edilen dosya kuyruğa giriyor, worker onu alıyor. Durum rozetleri iki saniyede bir
> yenileniyor: yüklendi, işleniyor, tamamlandı.

**Parça önizleme.** En kritik gösterim — burada dur.

> Bu, materyalin işlendikten sonraki hali. Her parçanın **hangi sayfadan geldiği** yanında
> duruyor. Bu sayfa numarası tesadüfi değil: cevabın altında göstereceğimiz kaynak
> referansı buradan üretilecek, modelin kendi metninden değil. Model bir sayfa numarası
> uydursa bile o referans doğrulamadan geçemez.
>
> Ayrıca parçalama sayfa sınırını hiç birleştirmiyor, çünkü birleştirirsek hangi sayfaya
> atıf vereceğimizi bilemeyiz.

**Sekmeler ve üye yönetimi.** Katılımcılar sekmesinde Burak'ı derse ekle.

> Öğrenci derse kendi kendine kayıt olamıyor, yalnız eğitmen davetiyle katılıyor.

**İzolasyonun canlı kanıtı.** Bu, videonun en güçlü anı olabilir.

> Şunu göstermek istiyorum: üye olmadığınız bir dersin adresini doğrudan yazarsanız sistem
> "yetkiniz yok" bile demiyor, **404, yani böyle bir ders yok** diyor. Çünkü "yetkiniz
> yok" demek dersin var olduğunu sızdırmak olurdu.

Burak'la gir, üye olmadığı bir dersin adresini elle yaz, 404'ü göster.

**Konu tanımlama.** Materyaller sekmesinde konu ekle.

> Konular soru üretiminin ve ilerleme takibinin dayanağı; eğitmen tanımlıyor.

---

## 12:00-13:30 — Cevap hattı: çalışan kısım ve hâlâ eksik olan

**Bu bölümü atlama.** Hoca mühendis; abartmak da eksiltmek de güveni zedeler. Burada
çalışanı **canlı göster**, çalışmayanı **adıyla söyle**.

> **8 Ağustos'tan kalan uyarı artık geçersiz.** O tarihte bu iki ekran "tasarım
> önizlemesi" etiketliydi ve senaryo sana "cevap hattı bağlı değil" dedirtiyordu. Hat
> bağlandı; o etiket koddan kaldırıldı. Eski metni okursan projeyi olduğundan zayıf
> göstermiş olursun.

Sohbet ekranını aç ve **önbellekteki listeden** bir soru sor (liste
`docs/demo-script.md`; dışına çıkma, sebebi aşağıda).

**Söyle:**

> Şimdi asistanın kendisini göstereyim. Bu cevap gerçek bir dil modelinden geliyor —
> Groq üzerinden çalışan açık ağırlıklı bir model — ama modelin bildiklerinden değil,
> **yalnız bu derse yüklenmiş materyalden** üretiliyor.
>
> Dikkatinizi şuraya çekmek isterim: cevabın altındaki kaynak kartı. Hangi dosyanın
> kaçıncı sayfası olduğunu yazıyor. Bu kart modelin yazdığı metinden çıkarılmıyor —
> modelden gelen metne güvenmiyoruz — parçanın kendi meta verisinden üretiliyor ve
> gerçekten getirilen kümeye karşı makine tarafından doğrulanıyor. Model olmayan bir
> kaynağı uydurursa cevap yayımlanmıyor.

**Kapsam dışı soruyu sor** (listedeki ret sorularından biri, ör. "İtalya'nın başkenti
neresidir?").

> Ve işte ana ilkemiz burada görünüyor: bu soruyu model gayet iyi biliyor, ama cevap
> vermiyor. Çünkü bu dersin materyalinde karşılığı yok. Bu bir eksiklik değil,
> tasarlanmış davranış: **kaynak yoksa cevap yok.**

**Sokratik moda geç ve üst üste iki soru sor**, sonra "cevabı direkt söyle" de.

> Sokratik modda cevabı vermiyor, ipucu veriyor. Israr edince de merdiven ilerlemiyor —
> bu kararı sunucu tutuyor, tarayıcıdan değiştirilemiyor.

**Sonra dürüstçe eksikleri say:**

> Neyin henüz olmadığını da söyleyeyim.
>
> Birincisi: sistem şu an **benim bilgisayarımda** çalışıyor, buluta kurulmadı. Canlı bir
> adres veremiyorum; bu yüzden bu videoyu çekiyorum.
>
> İkincisi: kimlik doğrulama hâlâ geliştirme kimlikleriyle; gerçek e-posta/şifre
> entegrasyonu bağlanmadı.
>
> Üçüncüsü, ve bunu özellikle söylemek istiyorum: **kalite ölçümümüz eksik.** Arama
> katmanını 161 soruluk bir kümeyle ölçtük ve sayıları raporda var. Ama gerçek modelle
> uçtan uca, geniş bir soru kümesinde kalite ölçümünü henüz tamamlamadık. Tek tek
> örneklerin çalıştığını gösterebiliyorum; "şu oranda doğru" diyecek sayıyı henüz
> üretmedim, üretmeden de söylemek istemiyorum.

**Toplantıdaki bir noktayı düzelt.** Bunu mutlaka söyle:

> Bir de toplantıda soru üretimi konusunda kendimi yanlış ifade ettim, onu düzelteyim.
> "Yapay zeka soruları kendisi hazırlamayacak" demiştim; aslında tasarımımız tam da sizin
> tarif ettiğiniz gibi:
>
> **Çerçeveyi siz kuruyorsunuz, yapay zeka dolduruyor.** Siz konuyu ve biçimi
> seçiyorsunuz — test, klasik ya da kısa cevap — isterseniz bir-iki örnek soru
> veriyorsunuz. Sistem materyalden o biçimde ve o üslupta taslak sorular üretiyor. Ama
> üretilen hiçbir soru **siz onaylamadan** öğrenciye görünmüyor; taslak havuzda bekliyor.
> Onaylama ve reddetme sizde.
>
> Yani hem soruyu yapay zeka üretiyor hem denetim sizde kalıyor.

---

## 13:30-14:00 — Kapanış

**Söyle:**

> Özetle: altyapı da cevap üretme hattı da çalışıyor ve testlerle doğrulanmış durumda.
> Kalan işler bulut kurulumu, gerçek kimlik doğrulama ve uçtan uca kalite ölçümü.
>
> Gereksinim analizi belgesini de ayrıca gönderiyorum. Depo herkese açık, isterseniz
> kendiniz de indirip çalıştırabilirsiniz; kurulum yönergesi `quickstart.md` dosyasında.
>
> Geri bildirimlerinizi bekliyorum hocam, teşekkür ederim.

---

## Çekim sonrası

1. Videoyu OneDrive'a yükle.
2. Paylaşım linkini al ve **linkin başkasında açıldığını doğrula** (izin ayarı sık sık
   "yalnız ben" kalıyor).
3. Hocaya gönder: video linki + gereksinim analizi belgesi + kaynak listesi.
4. Grupta Eren ve Metehan'a da at, aynı anlatıyı kullansınlar.

## Video sırasında SÖYLEME

- Testlerin sayısını yuvarlama ya da abartma — ekranda kaç yazıyorsa onu söyle.
- "Şu da çalışıyor" deme, göstermediğin hiçbir şeyi çalışıyor sayma.
- **Kalite oranı söyleme.** "Şu kadar doğru cevaplıyor" diyebileceğin ölçüm henüz yok.
- **Yedek sağlayıcı iddia etme.** Sohbet yolunda ikinci sağlayıcı bilinçli olarak
  devrede değil; Groq'ta hata olursa kurtaran şey önbellektir, failover değil.
- Önbellek listesinin dışında soru sorma; materyalde karşılığı olmayan sorular doğru
  davranışla reddedilir ama kayıtta arıza gibi görünür.
- Takım arkadaşlarının yapmadığı bir işi yapılmış gösterme; hoca ilerleyen toplantıda
  sorar.
