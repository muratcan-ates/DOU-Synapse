---
name: dou-kanit
description: "DOU-Synapse değişiklikleri için riske uygun doğrulamayı seç, test ve tarayıcı sonuçlarını doğru adayla bağla ve kanıtlı teslim hazırla. Kurulum veya ürün özelliği tasarlama amacıyla kullanılmaz."
---

# DOU-Synapse doğrulama ve kanıt

Başlangıçta depo, dal, tam base/HEAD, çalışma ağacı değişiklikleri ve feature kabul ölçütlerini doğrula. Hangi dosyaların bu işe ait olduğunu ayır. [Anayasa](../../../.specify/memory/constitution.md), seçilen feature görevleri ve gerçek kod davranışı ölçütleri belirler; eski runbook sayıları yeni sonuç değildir.

## Kapsama uygun kapılar

En küçük anlamlı kontrolle başla; yalnız kalan risk veya gereken teslim kapısı için genişlet.

- Beceri/doküman değişikliği: beceri yapısı, gerçek dosya başvuruları, gerçekçi kullanım denemesi ve ilgili belge kontrolü. Uygulama değişmediyse bütün API/tarayıcı paketini sırf sayı üretmek için tekrarlama.
- API/iş kuralı: hedefli olumlu ve olumsuz testler, ilgili SQL/RLS testleri, lint/biçim/tip kontrolü. Yetki veya süre kilidi için koruma kaldırılırsa kırmızı olacak mutasyon ya da gerçek HTTP karşı testi kullan.
- Arayüz: kütüphane testleri, tip kontrolü, üretim derlemesi ve değişen öğrenci/eğitmen yolculuğunu gerçek tarayıcıda gözleme. Geliştirme sunucusu davranışı değiştiyse onu da dene.
- Sürüm/entegrasyon: tam API/web/tarayıcı kapıları, sözleşme, migration sırası, gerçek sağlayıcı/ortam kanıtları ve gerekli bağımsız inceleme. Yerel sahte test, gerçek öğrenme kalitesini veya üretimi doğrulamaz.

Komutların mevcut karşılıklarını [API yapılandırmasından](../../../apps/api/pyproject.toml), [web komutlarından](../../../apps/web/package.json), [CI'dan](../../../.github/workflows/ci.yml) ve [belge ölçümünden](../../../scripts/docs_check.mjs) oku. Her çalışmanın hedefini [dou-kurulum](../dou-kurulum/SKILL.md) uyarınca izole et. Aynı test veritabanını eşzamanlı koşulara verme; E2E'nin oluşturacağı/sileceği kayıtları önceden belirle.

## Kanıtın gerçekten ölçüldüğünü göster

Mutasyon gerekiyorsa önce değişikliğin uygulandığını ve yanlış sebep yerine beklenen korumanın testi düşürdüğünü doğrula. Kendi mutasyonunu geri alıp yeşili tekrar gör. Kullanıcının değişikliklerini topluca geri alma; ayrı kopya veya açık sahiplik kullan. Test asılı kalıyorsa bunu negatif test başarısı sayma.

Her kayıtta komut, aday kimliği, ortam/DB izolasyonu, tarih, gerçek çıkış kodu ve sonuç bulunsun. Kabuk zincirinin son komutu önceki hatayı maskelemesin. Koleksiyon/listeme test çalıştırma değildir. Eksik bağımlılık yüzünden kısmi test çalıştıysa düşük sayıyı yeni doğru sayı olarak yazma.

Önceki adayın sonuçları kullanılacaksa kaynak SHA/log özetini ve dosya eşitliği veya kapsam farkını açıkça kaydet; yeni adayda yeniden koşulduğunu iddia etme. AI dossier/raporlarını [eklemeli denetim kuralına](../../../.ai/README.md) göre tut. Sahte, çevrimdışı, gerçek sağlayıcı, staging ve canlı kanıt etiketlerini karıştırma; insan onayı veya etiket uydurma.

## Teslim

İstenen işi, geçen kontrolleri, koşulmayan gerekli kontrollerin somut nedenini ve kalan riski anlat. Kabul ölçütü sağlandıktan sonra görev sahibinin dosyasını güncelle; eski bir entegratör dosyasına otomatik yazma. Bu işe ait test izlerini koru. Tarayıcı çıktısı oluştu diye tüm `docs/images`, `.next` veya `test-results` klasörlerini otomatik silme.

Commit biçimini güncel kullanıcı/depo talimatlarından al; eski bir lider tercihini kalıcı kural sayma. Yalnız gözden geçirilmiş görev yollarını stage et. Anahtarlar, kimliği belirli öğrenci verisi ve başka görevlerin değişiklikleri commit'e girmez. Yerel tamamlanma, main birleşimi ve canlı kabul durumlarını ayrı belirt.
