# Yerel belge bağlantılarını denetleme

`scripts/check_links.mjs`, depodaki Markdown bağlantılarını ağ isteği yapmadan okur. Yeni paket gerektirmez; Node'un yerleşik modüllerini kullanır. Belgeleri, hedef dosyaları veya Git durumunu değiştirmez.

## Kullanım

Depo kökünde çalıştırın:

```sh
node scripts/check_links.mjs
node scripts/check_links.mjs --json
node scripts/check_links.mjs --json README.md docs/security.md
node scripts/check_links.mjs --help
```

Dosya belirtilmezse Git'in izlediği `.md` ve `.markdown` dosyaları taranır. Henüz Git'e eklenmemiş bir belge için dosya yolunu açıkça verin. Açık dosya argümanları komutun çalıştırıldığı dizine göredir; `--` seçeneklerin sonunu belirtir.

Bağlantı hedefi kaynak belgenin dizinine göre çözülür. `/` ile başlayan hedef depo köküne göredir; bir geliştiricinin bilgisayarındaki mutlak dosya yolu değildir. Depo dışına çıkan yollar ve depo dışını gösteren sembolik bağlantılar reddedilir. Eski makine yollarını kalıcı bağlantı saymayın: örneğin `/private/tmp/...` ve `/Users/...` taşınabilir kaynak değildir. Bir tarihsel kanıtın hedefini değiştirmeden önce arşivdeki baytları ve kaynak kaydını doğrulayın.

## Sonucu yorumlama

Çıkış kodu `0`, denetleyicinin kapsamındaki yerel bağlantılarda hata bulunmadığını belirtir. `1`, kırık hedef, başlık, referans veya satır bağlantısı bulunduğunu; `2`, geçersiz komut girdisi, okunamayan kaynak belge veya erişilemeyen Git deposunu belirtir. JSON çıktısında `errors`, atlanan dış şema sayaçları ve `fragmentsSkipped` ayrı alanlardır.

Denetleyici dosya ve dizin varlığını; Markdown ATX/setext başlıklarını, yinelenen başlıkları ve açık HTML `id`/`name` hedeflerini; URL kodlamasını; referans ve resim bağlantılarını; `#L1` ve `#L1-L2` satır hedeflerini kontrol eder. Başlık kimliklerinde Unicode küçük harf dönüşümü kullanılır. Türkçe büyük `İ` dönüşümünde oluşan birleşen nokta da kimliğin parçasıdır.

HTTP(S) adreslerinin erişimi, yönlendirmesi veya içeriği kontrol edilmez. Markdown dışındaki genel fragmentler denetlenmez ve `fragmentsSkipped` içinde bildirilir. Yerel çıkış `0`, dış bağlantıların çalıştığı veya bütün belge biçimlerinin doğrulandığı anlamına gelmez.

## Ayrıştırma sınırları

Bu araç tam CommonMark/MDX ayrıştırıcısı değildir. Fenced code, inline code ve HTML yorumlarındaki bağlantılar taranmaz. İç içe liste veya alıntıdaki kod blokları, girintili kod, ham HTML bağlantıları ve çıplak URL otomatik bağlama kapsam dışıdır. Referans tanımları tek satır olmalıdır; bütün HTML entity kataloğu desteklenmez.

Tanımsız kısa `[etiket]` normal metinden ayırt edilemediği için bağlantı sayılmaz. Tanımı olmayan, boşluk veya satır geçişiyle ayrılmış `[P] [US1]` ve `- [x] [NEEDS CLARIFICATION]` görev etiketleri de metin kalır. Tanımlı boşluklu referanslar denetlenir. Bitişik `[metin][etiket]` ve boş `[]` kullanan collapsed referanslarda eksik tanım hata olmaya devam eder.

## 13 Eylül 2026 ön taraması ve açık engel

I1 değişiklikleri uygulanmadan önce ana yürütücünün yaptığı salt okunur tam taramanın kayıtlı sonucu **30 hata, çıkış kodu 1** oldu. Kanıt, yerel çalışma arşivindeki `evidence/link-baseline-before-i1.json` dosyasıdır; SHA256: `58c103cc6096571def4c9f3eac21973b9f5536558cc91ce397a36b80a30e2863`. Bu sayı yeni bir ürün testi, dış URL ölçümü veya bu belgenin son uygulanmış haliyle alınmış sonuç değildir.

Hataların tamamı `specs/018-codex-production-line/evidence/` altındaki şu tarihsel kanıt belgelerindeki eski makine yollarıdır:

- `c1-final-acceptance.md`
- `d1-http-local/independent-audit.md`
- `d2-local/d2-independent-migration-review.md`
- `d2-local/d2-process-v1-independent-review.md`
- `d2-local/d2-v2-authority-acceptance-addendum.md`
- `d2-local/d2-v2-legacy-positive-addendum.md`

**ENGEL:** Bu kanıt belgeleri I6'nın belge, README ve görev listesi düzeltme sahipliği dışındadır. Tarihsel ölçüm satırları, özgün yazar içeriği ve arşiv manifestleri değiştirilmedi. Eski kaynak baytları kanıtlanamayan bağlantılar güncel ürün dosyasına yönlendirilmedi. I1/I2/I3/I4 adayları da bu hata kaynaklarını değiştirmiyor; uygulamaları bu ön taramadaki hataları kendiliğinden gidermeyecek.

I6 kabulünde son değişiklikler uygulandıktan sonra tarama yeniden yapılmalı; kaynak sürümü, kullanılan script özeti, gerçek sonuç ve kalan engeller kaydedilmelidir. Bu ön kayıt, bütün depo bağlantı kapısının geçtiği iddiası değildir.

## Uygulanan kaynakla son tarama — 13 Eylül 2026

I1, I3, H2, H3 protokolü ve I4 teslimlerinden sonra, uygulanan `scripts/check_links.mjs` ile izlenen bütün Markdown dosyaları yeniden tarandı. Gerçek sonuç yine **30 hata, çıkış kodu 1**; hataların tamamı yukarıdaki tarihsel kanıt dosyalarında. Yeni ve düzeltilmiş izinli belgelerde ek kırık hedef bulunmadı. Tam kaynak dosyası özetleri, komut ve ham çıktı yerel `runtime/evidence/i6-final-scan/repository-scan.json` kaydında korunur. Bu tarama dış HTTP(S) adreslerini sınamadı.

Aynı API kaynaklarından daha önce alınmış OpenAPI dışa aktarımı kayıtlı sözleşmeyle anlamsal olarak aynıydı; kaynak özetleri tekrar eşleştirildi. Uç değişikliği bulunmadığından sözleşme yeniden yazılmadı. Tam depo bağlantı kabulü, kapsam dışındaki eski yollar giderilene kadar açık kalır.
