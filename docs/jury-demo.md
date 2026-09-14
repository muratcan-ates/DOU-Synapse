# Jüri demosu — 10 dakika

Bu belge bitirme jürisinde canlı gösterilecek akışı sabitler. Amacı etkileyici
görünmek değil, **iddiaların kanıtla eşleştiğini** göstermektir. Bir sayı burada
yazılıysa ölçülmüştür; ölçülmemişse "ölçülmedi" yazar.

> **Kullanılmayan sözcükler.** "Production-ready", "KVKK uyumlu", "LTI hazır",
> "garantili" ve "%99 doğru" ifadeleri bu demoda **kullanılmaz**. Hiçbiri
> ölçülmedi; ölçülmemiş bir uyum iddiası jüri karşısında savunulamaz.

---

## 0. Kurulum (demo öncesi, sahnede değil)

```bash
docker compose up -d db
./scripts/migrate.sh
psql -d dou_synapse -f supabase/seed_demo.sql
cd apps/api && .venv/bin/uvicorn app.main:app --port 8000
cd apps/web && bun run dev
```

Demo verisi `sample_data/` altındaki ders materyalidir. Gerçek öğrenci verisi
kullanılmaz ve ekranda gerçek bir öğrenci adı görünmez.

**Yedek plan (C planı):** ağ veya sağlayıcı düşerse
`docker compose --profile fallback up`. Bu profil dış ağa çıkmaz; cevaplar
önceden doldurulmuş `answer_cache`'ten gelir ve zarfında `cached: true` taşır.
Sahte sağlayıcıyla uydurma metin **gösterilmez** — önbellekten gelen cevap
gerçek hattan bir kez geçmiş cevaptır. Ayrıntı: [dağıtım §7](deployment.md).

---

## 1. Dakika 0–2 — Problem ve tek cümlelik iddia

> "Öğrenci ders materyaline soru soruyor. Sistemin iddiası şu: **kaynağı
> olmayan hiçbir cevabı vermiyorum.** Bunu bir slogan olarak değil, bir
> mekanizma olarak göstereceğim."

Ekranda: ders listesi → bir ders → materyaller. Yüklenmiş PDF'ler ve parça
sayısı görünür. Buradaki sayı ekrandan okunur, ezberden söylenmez.

---

## 2. Dakika 2–4 — Kanıtlı cevap

Soru: **materyalde gerçekten geçen** bir kavram sorulur.

Gösterilecek üç şey:

1. Cevap gelir ve altında **kaynak kartları** vardır.
2. Bir kaynak kartına tıklanır → **o parçanın kendisi** açılır: dosya adı ve
   sayfa numarası görünür.
3. Vurgulanacak nokta: *dosya adı ve sayfa numarası modelin yazdığı metinden
   değil, parçanın veritabanındaki metadata'sından gelir.* Model bir kaynak
   uydursa bile atıf `chunk_id` küme-üyelik kontrolünden geçemez ve gösterilmez.

Jüri sorabilir: "Model kaynağı uydurursa ne olur?" Cevap: atıf, o soru için
gerçekten getirilen parçaların kimlik kümesinde yoksa **elenir**; elenen atıf
ekrana çıkmaz. Bunun regresyon testi `apps/api/tests/test_guardrails.py`
içindedir.

---

## 3. Dakika 4–6 — Kaynak yoksa **susma**

Soru: dersin **kapsamı dışında** bir şey sorulur (ör. başka bir dersin konusu).

Gösterilecek: sistem cevap üretmez, **neden veremediğini** söyler.

Vurgulanacak iki nokta:

1. Bu bir "bilmiyorum" şablonu değil, bir **eşik kararı**dır: kanıt eşiği
   aşılamadığında istek **LLM'e hiç gitmez**. Bu, testte sağlayıcı çağrı
   sayacının sıfır olmasıyla kanıtlanır.
2. Fail-closed ilkesi: belirsizlikte açmak değil kapatmak. Yanlış cevap,
   cevapsızlıktan daha pahalıdır — özellikle sınav provasında.

---

## 4. Dakika 6–8 — Sağlayıcı düştüğünde: **etiketli** yedek

Sağlayıcı 429 (kota) döndürülür (demo bayrağıyla).

Gösterilecek:

1. Sistem `Retry-After` süresine saygı duyup **bir kez** tekrar dener.
2. Tekrar da düşerse ekranda **"Önceden kaydedilmiş demo yanıtı"** etiketiyle
   bir cevap görünür.
3. Vurgulanacak nokta: **sessiz model değişimi yoktur.** Kullanıcıya gösterilen
   cevabın canlı üretilmediği ekranda yazar. Yedek cevapta da kaynak kartları
   aynı küme-üyelik kontrolünden geçer.

Jüri sorabilir: "Neden sessizce başka modele geçmiyorsunuz?" Cevap: geçmek
teknik olarak kolay, ama o zaman ekrandaki cevabın hangi modelden geldiği
kullanıcı için görünmez olur ve bir eğitim ortamında bu bir güven sorunudur.

---

## 5. Dakika 8–10 — Eğitmen özeti

Eğitmen görünümü: konu bazında **yanlış / ipucu istenen / cevaplanamayan**
sayıları.

Gösterilecek ve **açıkça söylenecek**:

1. Özet yalnızca sayı gösterir. **Ham sohbet içeriği eğitmene açılmaz.**
2. Olay kayıtlarında öğrenci kimliği doğrudan tutulmaz; takma bir kimlik
   kullanılır.
3. Bu özet "hangi öğrenci kötü" tablosu değil, "hangi konu zayıf" tablosudur.
   Tasarım kararı budur ve isteyerek alınmıştır.

---

## 6. Jürinin sorması muhtemel sorular

**"Bu sistem öğrenciyi notlandırıyor mu?"**
Hayır. Sınav provasının sonuçları nota ya da geçme-kalmaya **girmez**. Bu, AB
Yapay Zekâ Yasası'nın yüksek riskli sistem tanımıyla ilgili bilinçli bir sınır:
Ek III'te eğitim alanı listelenir, ancak Madde 6(3) kararın sonucunu maddi
olarak etkilemeyen sistemleri bu sınıfın dışında tutar. Sistemi o sınırın
içinde tutmak için provanın nota etkisi **mimari olarak** yoktur.
Ek III yükümlülüklerinin uygulanma tarihi Digital Omnibus düzenlemesiyle
**2 Aralık 2027**'ye taşınmıştır.

**"Yapay zekânın ödevde kullanımı konusunda mevzuat ne diyor?"**
YÖK'ün üretken yapay zekâ kullanımına ilişkin etik rehberi **7 Mayıs 2024**
tarihlidir; ders bazında kullanım politikası yetkisi eğitmendedir. Sistemde
ders başına yapay zekâ politikası ayarı ve politika geçmişi bu yüzden vardır
(`docs/security.md`, ders ayarları ekranı).

**"Öğrenci verisi nerede duruyor, kim görüyor?"**
İki katman: sunucu üyelik kontrolü **ve** aynı işlemde PostgreSQL satır düzeyi
güvenliği. İstemciden gelen ders kimliği tek başına hiçbir zaman yetki değildir.
Bunun kanıtı `supabase/tests/rls_*.sql` mutasyon betikleridir: politika
kaldırıldığında bu testler **kırmızı yanabilmelidir**; yanamıyorsa test hiçbir
şey kanıtlamıyor demektir. KVKK **uyumluluk iddiası yapılmaz**; yapılan şey,
veri erişiminin teknik olarak sınırlandırılmasıdır.

**"Ne kadarı çalışıyor, ne kadarı plan?"**
[Test raporu](test-report.md) ölçülen ile ölçülmeyeni ayırır.
[Dağıtım belgesi §11.6](deployment.md) koşulmamış adımları madde madde listeler.
Bulut dağıtımı **koşulmadı**; demo yerel ortamdadır.

**"Ticarileşme / destek başvurusu var mı?"**
TÜBİTAK 2209 programının 2026 çağrısı bu belgenin yazıldığı tarihte **ilan
edilmemişti**; doğrulanması gerekir. BiGG (1812) desteği için kayıtlı tutar
1,35 milyon TL ve geri ödemesiz oran %3 olarak not edilmiştir — bu iki sayı
başvuru öncesi güncel çağrı metninden **yeniden doğrulanmalıdır**.

---

## 7. Demo sırasında yapılmayacaklar

- Ölçülmemiş bir sayı söylemek ("%95 doğru", "2 saniyede cevaplıyor").
- Bulut dağıtımını çalışıyormuş gibi anlatmak.
- Sahte sağlayıcı çıktısını gerçek cevap gibi göstermek.
- Gerçek bir öğrencinin adını veya sohbetini ekrana getirmek.
- "Uyumlu" sözcüğünü herhangi bir mevzuat adının yanında kullanmak.

## 8. Bu belgenin sınırı

Buradaki akış **yerel ortamda** provası yapılmak üzere yazıldı. Bu belgenin
kendisi bir kabul kaydı değildir: her demo öncesi akış baştan sona bir kez
koşulmalı ve kırılan adım burada güncellenmelidir.
