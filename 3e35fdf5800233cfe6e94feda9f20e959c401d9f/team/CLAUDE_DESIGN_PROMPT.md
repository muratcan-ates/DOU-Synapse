# Claude Design — Sunum Üretim Promptu

> Bu dosyanın "PROMPT BAŞLIYOR / BİTTİ" arasını Claude Design'a (veya slayt üretecek
> herhangi bir Claude sohbetine) olduğu gibi yapıştır. Yanına Doğuş logosunu ekle
> (`~/Downloads/Dogus_universitesi_yeni_logo.png`). İçerik uydurmasına izin verme —
> promptta olmayan hiçbir sayı/özellik eklenmemeli.

---

## PROMPT BAŞLIYOR

Bir üniversite bitirme projesi ara sunumu hazırlıyorum. **9 slaytlık** bir sunum tasarla.
Aşağıda hem tasarım sistemi hem slayt slayt içerik var. İçeriğe sadık kal; **yeni özellik,
sayı veya iddia UYDURMA** — burada yazmayan şeyi ekleme.

### Bağlam

- Proje: **DOU-Synapse (CourseGPT)** — ders materyaliyle sınırlı, her cevabı sayfa
  kaynağıyla veren yapay zekâ ders asistanı
- Sunulacağı yer: Doğuş Üniversitesi, COME 491/492 bitirme projesi, danışman toplantısı
- Sunum dili: Türkçe · Süre: ~5 dakika · Ton: mühendislik olgunluğu, abartısız

### Tasarım sistemi (bağlayıcı)

- **Marka rengi:** `#C50C1F` (Doğuş kırmızısı) — YALNIZCA vurgu için: başlık altı ince
  çizgi, tek anahtar sözcük, slayt numarası. Zemin olarak asla kullanma
- **Zemin:** beyaz `#FFFFFF`; metin `#1C1917`; ikincil metin `#57534E`; ince ayraçlar `#E7E5E4`
- **Yazı:** Inter (yoksa temiz bir grotesk); başlıklar yarı kalın, gövde normal
- **YASAKLAR:** gradyan yok · gölge/3B efekt yok · stok görsel/illüstrasyon yok · emoji
  yok · TÜMÜ BÜYÜK HARF yok (Türkçe i/İ bozulur) · uzun tire (—) yerine orta nokta veya
  virgül kullan
- Düzen: bol beyaz alan, sola hizalı metin, slayt başına en fazla ~35 kelime; sayılar
  büyük punto, açıklamaları küçük
- Logo: her slaytın altbilgisinde küçük, tek renk; kapakta orta boy

### Slaytlar

**S1 — Kapak.** Büyük başlık "DOU-Synapse", alt başlık "Ders materyaliyle sınırlı,
kaynak gösteren yapay zekâ ders asistanı". Alta küçük: "COME 491/492 Ara Sunum ·
Muratcan Ateş · Eren · Metehan · Ağustos 2026". Doğuş logosu.

**S2 — Problem.** Başlık: "Öğrenciler yapay zekâya soruyor; üç şey ters gidiyor".
Üç kısa madde: (1) Müfredat dışına çıkıyor, sınavla ilgisiz cevap veriyor ·
(2) Kaynak göstermiyor, doğruluğu denetlenemiyor · (3) Ödevin cevabını doğrudan verip
öğrenmeyi zedeliyor. Altta tek satır kanıt: "Harvard CS50 asistanı değerlendirmesi:
yanıtların %22'sinde doğrudan kod sızıntısı (Liu vd., 2025)". %22 kırmızı ve büyük.

**S3 — Yaklaşımımız.** Ortada tek büyük cümle: "Kaynak yoksa cevap yok." Altında üç
küçük destek maddesi: Yalnız eğitmenin yüklediği materyalden · Her cevapta dosya adı +
sayfa numarası · Kanıt yetersizse cevap üretmek yerine açıkça söyler.

**S4 — Danışman gereksinimleri karşılandı.** İki sütunlu sade tablo, 6 satır:
Materyal yükleme (PDF/PPTX/kod) → Tamamlandı · Ders bazlı bilgi tabanı + izolasyon →
Tamamlandı, testli · Sokratik mod → Tasarlandı, motor 10 Ağu · Sınav provası + "neden
yanlış" → Tasarlandı, motor 10 Ağu · Soru üretimi + eğitmen onayı → Planlandı ·
Kaynak zorunluluğu + müfredat dışı ret → Çekirdek kural, tasarımda. Altta küçük not:
"Taslaktaki 12 maddenin 12'si, 35 numaralı gereksinime izlenebilir (spec.md)."

**S5 — Şu an çalışan sistem.** Başlık: "Bugün canlı gösterebiliyoruz". Dört madde:
Eğitmen ders açar, PDF/sunum/kod yükler · Sistem sayfa numarasını koruyarak işler
("3 sayfa · 12 parça") · Öğrenci yalnız kayıtlı olduğu dersi görür · 68 otomatik test,
her push'ta koşan CI. Sağda telefon/tarayıcı çerçevesinde tek ekran görüntüsü alanı bırak
(ben ekleyeceğim).

**S6 — Güvenlik: iddia değil kanıt.** Başlık: "İzolasyonu test ediyoruz; testin
yanabildiğini de test ediyoruz". İki kutu: Soldaki "Uygulama katmanı — ders kimliği
istemciden asla yetki sayılmaz"; sağdaki "Veritabanı katmanı — satır düzeyi güvenlik
(RLS)". Altta tek vurucu satır: "Güvenlik politikasını bilerek bozuyoruz; test kırmızıya
dönmezse sistem onu saymıyor demektir. Bu kontrol CI'da her push'ta otomatik."

**S7 — Nasıl ölçeceğiz.** Başlık: "Garanti demiyoruz; ölçüp raporlayacağız". Üç büyük
sayı kartı: "≥%90 · doğru sayfa atıfı" · "≥%90 · müfredat dışını doğru reddetme" ·
"0 · hedef: Sokratik modda kod sızıntısı (test setinde)". Altta küçük metodoloji satırı:
"50+ soruluk set; eşik ayarı ile ölçüm ayrı kümelerde; sonuçlar yön göstergesidir."

**S8 — Takvim ve ekip.** Yatay üç kilometre taşı: "10 Ağu · uçtan uca kaynaklı cevap
(kapı)" → "17 Ağu · özellik dondurma, test ve ölçüm" → "24 Ağu · teslim: canlı sistem +
başarı raporu + kılavuzlar". Altta ekip: "Eren — RAG hattı ve guardrail · Metehan —
sınav motoru ve ölçüm · Muratcan — arayüz ve koordinasyon · 60 görevlik izlenebilir plan".

**S9 — Danışmana sorular.** Başlık: "Görüşünüzü istediğimiz üç konu". (1) Örnek ders
paketi: telif açısından kendi ürettiğimiz materyalle ilerliyoruz; uygun mu? ·
(2) 50 soruluk değerlendirme setini 11-12 Ağustos'ta gözden geçirmenizi rica edebilir
miyiz? · (3) MVP kararları: derse katılım eğitmen davetiyle, sınav süresi sabit —
onaylıyor musunuz?

## PROMPT BİTTİ

---

## Kullanım notları (sana, prompta dahil değil)

1. S5'teki ekran görüntüsünü sunumdan önce çek: ders detay sayfası, "Hazır" rozetli
   belge + sekmeler görünsün (localhost:3000, açık tema, Ayşe girişi).
2. Claude Design farklı renk/efekt önerirse kabul etme; tasarım sistemi bölümü bağlayıcı.
3. Slayt sayısını artırmak isterse reddet — 5 dakikaya 9 slayt doğru yoğunluk.
4. Çıktıyı aldıktan sonra tek kontrol: %22, 68, 35/12, ≥%90, tarihler (10/17/24 Ağu)
   doğru aktarılmış mı? Bu sayılar dışında sayı görüyorsan uydurmuştur, sil.
