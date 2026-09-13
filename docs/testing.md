# Tarayıcı testleri ve kararsız test politikası

Yeni dosya: `docs/testing.md`. Düzenleme tarihi: 13 Eylül 2026.

## Projeler ve kimlikler

`chromium` genel portal/politika vakalarını, `llm` üretim/sohbet/değerlendirme
uçlarına dokunan dosyaları çalıştırır. Karma `flows.spec.ts` dosyasının tamamı
bilerek `llm` grubundadır. Proje adı gerçek LLM kanıtı değildir; sahipli yerel
çalıştırıcı `LLM_FAKE_PROVIDER=true` ve hashing embedding kullanır.

LLM dosyaları `worker-fixture.ts` üzerinden her Playwright çalışanına özgü
öğrenci/eğitmen profilleri alır. UUID ve koşu e-postası paylaşılmaz; üyelikler
ürün API'siyle kurulur, yönetici yetkisi verilmez. Oturum helper'ı yalnız sentetik
kurulum içindir; gerçek giriş/admin testleri seed kullanıcılarını korur.
Portalın profil PATCH vakası ortak Ayşe profilini değiştirmez.

Profil kurulumu, API/veritabanı kimlik sondasından sonra yazılan özel başarı
makbuzunu ister. Sahiplik manifesti INSERT'ten önce kaydedilir. Global teardown
önce mevcut koşu ders/audit temizliğini bitirir, sonra yalnız manifestteki tam
UUID/e-posta çiftini siler. Kalan FK, farklı e-posta veya audit kaydı varsa
silme işlemi durur; genel kullanıcı temizliği yapılmaz.

## Paralel kabul

Yapılandırmanın varsayılanı iki worker'dır. Varsayılan vaka bütçesi 90 saniye,
arayüz iddiası beklemesi 10 saniyedir; dosyaların açık vaka bütçeleri korunur.
Bunlar tamamlanma sınırlarıdır, performans SLO veya ölçülmüş yanıt süresi değildir. Hazırlanmış, hedefi doğrulanmış ayrı
E2E API/veritabanı ve audit kapsamı üzerinde aşağıdaki komut ayrı koşu kimlikleriyle
üç kez art arda başarılı olmalıdır:

```bash
cd apps/web
./node_modules/.bin/playwright test --workers=2
```

Her koşu için aday SHA, komut, çıkış kodu, sağlayıcı türü, sonuç özeti ve API
kapanışı sonrası audit muhasebesi saklanır. `--list`, typecheck veya tek başarılı
koşu bu kabulü kapatmaz. Yeniden denemede geçen vaka kararlı sayılmaz.

**ENGEL:** `scripts/run_owned_e2e.py` genel komutu hâlâ `--workers=1` ile çağırıyor.
Bu dosya L6 yüzeyi dışında; yapılandırmadaki iki worker değeri CLI zorlamasını
aşmaz. Çalıştırıcı sahibi bu zorlamayı kaldırmadan genel hattın paralel olduğu
iddia edilmez. Üç ardışık iki-worker kabulü **tamamlanmadı**; başarısız/kesilmiş koşular başarılı sayılmaz.

## Yerel doğrulama — 13 Eylül 2026

[Koşu kaydı](evidence/l6-h1-verification.json) başarılı dar vakaları, başarısız
adayları ve kesilen tam paketleri ayırır. Worker profil sondası yanlış kapsam,
manifest, e-posta ve kalan bağımlılık durumlarında silmeyi reddetti; bu sondanın
geçmesi tam tarayıcı kabulü değildir. Geçersiz e-posta alan adı düzeltildi;
profil ve sohbet silme dar koşusu başarılıdır. Gecikmiş sohbet yanıtı, kayıtlı
rubrik, değişen ipucu sınırı ve ikinci sekmenin başlangıcı için dört vaka iki
worker ile geçti; gerçek API kapanışı ve audit muhasebesi de başarılıydı.

Tam paketin son denemesinde web sunucusu 143 çıkış koduyla sonlandı ve ardından
bağlantı reddi alındı. Sinyalin kaynağı belirlenmedi. Bu **ENGEL** nedeniyle H1
kararlılık kabulü açık; ortak kapılar veya dar koşular bu eksik kabulü kapatmaz.
Başarısız koşuların audit kayıtlarında kayıp/değişmiş/beklenmeyen satır yoktu,
ama test başarısızlığı nedeniyle genel audit sonucu da başarılı sayılmadı.

Yerel tekrarlar API adresi gömülü aynı üretim derlemesini kullanır. Yerel
`repeat.config.ts`, depo projelerini/testlerini koruyup yalnız web başlatmayı
hazır derlemeye yönlendirir; kaynak ve derleme özetleri koşu öncesi/sonrası
karşılaştırılır. Yeni bir kaynak değişiminde üç ardışık kabul yeniden başlar.

## Kararsız test karantinası

- Yeniden deneme üst sınırı birdir; başarısızlığı saklamak için artırılmaz.
- Karantinaya girecek her vaka için açık issue, sorumlu kişi, tekrar adımları,
  son başarısız koşu bağlantısı ve takvim günü olarak son tarih zorunludur.
- Günlük ana hattan çıkarma, vakayı kalıcı `skip`/`fixme` ile susturmaz. Vaka ayrı
  karantina projesinde gerçekten çalışır; gecelik sonuç issue'ya bağlanır.
- Son tarihi geçen, sahibi bulunmayan veya gecelik sonucu olmayan kayıt açık
  engeldir. Karantinadan çıkış için aynı adayda iki-worker komutunun üç ardışık
  koşusu yeniden denemesiz geçmeli; issue'da kök neden ve düzeltme bulunmalıdır.
- Bu aday hiçbir testi karantinaya almıyor. Issue/sahip/son tarih uydurulmadı.

**ENGEL:** Gecelik karantina iş akışı bu adayda oluşturulmadı; workflow'lar L6
sahipliği dışındadır. Yalnız politika yazılması gecelik hat kanıtı değildir.

| Vaka | Issue | Sahip | Son tarih | Gecelik koşu | Durum |
|---|---|---|---|---|---|
| Henüz kayıt yok | yok | atanmadı | atanmadı | koşulmadı | karantina uygulanmadı |

## Sonuçların sınırı

Genel/admin portal vakaları ve politika geçmişi hâlâ sabit demo kimlikleri
kullanabilir; tüm paketin her hesabı benzersizdir iddiası yapılmaz. Erişilebilirlik,
gerçek sağlayıcı kalitesi, Linux görsel referansı ve canlı ortam kabulü ayrı
kanıt gerektirir. Her işin gerçek kapı sonuçları PR raporunda kaydedilir.
