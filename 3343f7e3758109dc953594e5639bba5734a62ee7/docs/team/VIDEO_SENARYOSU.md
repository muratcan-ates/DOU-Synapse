# Danışman videosu — çekim senaryosu

> Hocanın isteği (6 Ağustos toplantısı): *"10-15 dakikalık, adım adım gösteren bir video
> çekin. Şu ana kadar ne yaptığınızı. Şu an telefondan bağlandım, görmekte zorlanıyorum.
> Videoyu OneDrive'a yükleyip linkini paylaşın."*
>
> Hedef süre: **13-15 dakika.** Aşağıdaki bölüm süreleri toplamı 14 dakika.

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
> **İkincisi API:** Python ve FastAPI ile yazılmış backend, 8000 portunda. Ders yönetimi,
> materyal yükleme, yetkilendirme ve izolasyon burada.
>
> **Üçüncüsü worker:** ayrı bir süreç olarak koşan işleyici. Yüklenen dosyayı parçalara
> ayırıp vektörlerini hesaplayan iş burada dönüyor. Web isteğinin içinde yapmıyoruz;
> büyük bir PDF yüklendiğinde arayüz kilitlenmesin diye ayırdık.
>
> **Dördüncüsü arayüz:** Next.js ile yazılmış web uygulaması, 3000 portunda.
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

> Şu an 92 otomatik test geçti. Bunların içinde en önemsediğimiz grup izolasyon testleri.
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

    uv run uvicorn app.main:app --port 8000
    uv run python -m app.worker
    cd ../web && bun install && bun run dev

> Arayüz 3000 portunda açılıyor.

---

## 7:30-12:00 — Çalışan özelliklerin turu

Tarayıcıda `localhost:3000`. Yavaş gez, her ekranda bir-iki cümle söyle.

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

## 12:00-13:30 — Henüz tasarım olanlar ve sıradaki iş

**Bu bölümü atlama.** Hoca mühendis; çalışmayan bir şeyi çalışıyor gibi göstermek
güvenilirliğini zedeler, dürüstçe söylemek tersine güçlendirir.

Sohbet ve sınav ekranlarını aç. Ekrandaki **"tasarım önizlemesi"** etiketini göster.

**Söyle:**

> Bu iki ekran şu an **tasarım önizlemesi** — ekranda da böyle etiketli. Buradaki konuşma
> örnek veri; arkasındaki cevap üretme hattı henüz bağlı değil. Size çalışıyormuş gibi
> göstermek istemem.
>
> Şu an bitmiş olan kısım altyapı: izolasyon, materyal işleme hattı, parçalama, vektör
> indeksleme ve arayüz. Sıradaki iş cevap üretme hattı: arama, dil modeli bağlantısı ve
> guardrail zinciri. Bunun için kendimize 10 Ağustos'ta bir kapı koyduk — uçtan uca,
> gerçek materyalle kaynaklı cevap. Geçemezsek plana göre kapsamı daraltıyoruz.

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

> Özetle: altyapı çalışıyor ve testlerle doğrulanmış durumda, cevap üretme hattı sıradaki
> iş, teslim 24 Ağustos.
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

- Testlerin sayısını yuvarlama ya da abartma — 92 ise 92 de.
- "Şu da çalışıyor" deme, göstermediğin hiçbir şeyi çalışıyor sayma.
- Sohbet ekranındaki örnek konuşmayı gerçek cevapmış gibi okuma.
- Takım arkadaşlarının yapmadığı bir işi yapılmış gösterme; hoca ilerleyen toplantıda
  sorar.
