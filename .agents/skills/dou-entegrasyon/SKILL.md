---
name: dou-entegrasyon
description: "DOU-Synapse dallarını ve commitlerini karşılaştır, çakışmaları incele veya istenen yerel entegrasyonu yap. Tam base/aday kimliği, göç sırası, ortak sözleşmeler ve değişmez denetim kayıtlarını koru."
---

# DOU-Synapse entegrasyonu

Kullanıcı yalnız inceleme istediyse salt okunur çalış. Entegrasyon istediyse oturumda yetkilendirilmiş hedefi ve kapsamı kullan; hedef belirsizse tüm karşılaştırmayı hazırla, gerçek birleştirmeden önce yalnız eksik hedefi sor. Kaynak, hedef, tam HEAD/base SHA ve çalışma ağacı durumlarını kaydet. Sabit bir lider dizini veya geçmiş özellik dalını varsayma.

## İçeriği karşılaştır

- Her kaynağın hedefle merge-base'ini bul. Kaynağın kendi farkını ve hedefe girecek birleşik farkı ayrı incele; iki uç arasında düz fark, dalın yazdığı işle eşdeğer değildir.
- Aynı içeriğin daha önce alınıp alınmadığını patch eşdeğerliğiyle incele. Commit sayısı, içerik veya doğrulama kanıtı değildir.
- Ortak dosya sahipliği, API/istemci/SQL sözleşmeleri ve migration numaralarını bütün gelen şeritlerde karşılaştır. Çakışan veya daha önce uygulanmış migration'ı otomatik yeniden numaralandırma.
- Kullanılabilir Git sürümü destekliyorsa `git merge-tree --write-tree` ile önizleme yap. Çakışmalı çıkışı başarı gibi yorumlama.

## Yetkilendirilmiş yerel birleştirme

Mevcut temiz entegrasyon şeridi uygunsa onu kullan; aksi hâlde doğrulanmış hedeften ayrı çalışma ağacı hazırla. Başka sahibin kirli ağacında merge/cherry-pick yapma. Yalnız istenen commitleri al; kısmi aktarım gerekiyorsa dışlanan her dosyanın işlevsel gerekçesini kaydet. Dokümanları, testleri veya sözleşmeleri sırf başka araç yazdı diye topluca dışlama. `git add .`, tüm klasörü geri alma veya zorla push ile çakışmayı örtme.

Çakışmayı mevcut onaylı iş kurallarıyla çöz: hata zarfı, kaynak/kaynak sürümü, ders üyeliği, aktif sınav kilidi ve sunucuda puan hesaplama korunur. Çağrı yeri, şema, imza ve istemci birlikte tutarlı olmalı; aynı işi yapan yardımcıları gereksiz çoğaltma. Somut sözleşmenin kaynağını [API şemalarından](../../../apps/api/app/schemas), [hata üreticisinden](../../../apps/api/app/core/errors.py) ve seçilen feature belgelerinden oku.

[AI denetim kayıtları](../../../.ai/README.md) yalnız eklenir. Önceki dossier/raporları yeni adaya uyacak şekilde değiştirme. Eski SELF bağı yeni HEAD için kanıt değildir; tam incelenen base/aday aralığı için geçerli kayıt gerekir. Hatalı geçmiş adayın başarısız sonucunu koru; geçerli olmayan geçmişi sessizce yetkilendirici olarak sunma.

## Doğrulama ve teslim

Değişen kapsam için [dou-kanit](../dou-kanit/SKILL.md) akışını uygula. API değiştiyse uygulamadan OpenAPI üret; elle düzenleme. Belge kontrolü ölçüm yapamadıysa önce ortamı düzelt, sonuç sayısını düşürerek uyarlama. Migration denemelerini izole test hedefinde yap; entegrasyon, ortak veya canlı veritabanına göç yetkisi değildir.

Son rapor tam kaynak/hedef/aday kimliklerini, alınan ve dışlanan kapsamı, yeni koşulan ve devralınan testleri, çözülmemiş riskleri ayırır. Main birleşimi, dış push/PR, dal silme ve dağıtım yalnız mevcut açık yetki ve gereken inceleme kapılarıyla yapılır; beceri bunlar için otomatik yetki üretmez. Önceden verilmiş geçerli yetkiyi tekrar sorma. Yerel hazırlık tamamlanmadan onay isteme.
