# CSP gözlem başlığı

Yeni dosya: `docs/content-security-policy.md`. Kaynak inceleme tarihi: 13 Eylül 2026.

`next.config.ts`, mevcut uygulanan `Content-Security-Policy` başlığına ek olarak
`Content-Security-Policy-Report-Only` gönderir. Gözlem kopyası yalnız `script-src`
üzerindeki `unsafe-inline` ve geliştirmedeki `unsafe-eval` izinlerini çıkarır.
Diğer yönergeler mevcut `webSecurityHeaders()` çıktısından alınır. Böylece API
ve kimlik sağlayıcısı adresleri iki ayrı sabit listede ayrışmaz.

Bu başlık ek koruma uygulanmış olduğu anlamına gelmez. Next'in inline hydration
betikleri için ihlal bildirimi beklenebilir; gözlem politikası bunları engellemez.
`report-to` / `report-uri` veya rapor toplayıcısı bu adayda kurulmadı. Tarayıcı
konsolunda gözlem yapılabilir; merkezi rapor teslimi ve sayısı ölçülmüş değildir.
İhlal içerikleri kullanıcı verisi taşıyabileceğinden toplayıcı ayrı veri kararıdır.

## Nonce ve rota etkisi

Bu değişiklik nonce, Proxy, `next/headers` üzerinden dinamik istek başlığı
okuması veya `connection()` eklemez. Mevcut `next.config.ts` içindeki
`async headers()` yapılandırması yalnız yanıt başlığı üretir. Bu yüzden tek başına sayfaları dinamik
sunucu render'ına geçirmez. Kurulu Next paketinin CSP rehberi, istek başına nonce
kullanımının dinamik render gerektirdiğini açıklar. İleride nonce'a geçiş;
statik üretim, önbellek ve PPR üzerinde ayrı tasarım ve ölçüm gerektirir.

Kaynak: kurulu `apps/web/node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md`
(`Without Nonces`, `Static vs Dynamic Rendering with CSP`) ve depo
[`security-headers.ts`](../apps/web/lib/security-headers.ts).

## Doğrulama

Kaynak incelemesi canlı başlık/ihlal ölçümü değildir. H6 kabul kaydında üretim
derlemesiyle gerçek yanıtın iki CSP başlığı, mevcut başlığın korunması ve
etkileşimli sayfanın açılması ayrı belirtilir. İhlal sayısı ölçülmeden yazılmaz.

## Gerçek yerel kabul — 13 Eylül 2026

`h6-production-csp-03` yeni üretim derlemesi ve yerel Chrome ile geçti.
Gerçek `/` ve `/dashboard` HTTP yanıtlarında mevcut CSP ve diğer güvenlik
başlıkları değişmeden kaldı; gözlem başlığı yalnız betik yönergesini daralttı.
Gerçek demo girişi, sunucudan sahipli kullanıcı eşleşmesi, tam sayfa yenileme
ve çıkış doğrulandı. Yakalanmamış tarayıcı hatası kaydedilmedi; dashboard
PNG'si ayrıca açılıp incelendi. Bu gözlem bütün sayfalarda hata yok iddiası değildir.

Tarayıcı bu koşuda **5** gerçek `report / script-src-elem / inline` olayı
teslim etti. Kontrollü inline tanı betiği de çalıştırıldı; sayı yalnız Next
hydration betiklerine veya bütün ihlallere ait değildir. Merkezi rapor
iletimi ölçülmedi. Her iki sayfanın yanıtında prerender başlığı görüldü;
nonce/dinamik istek okuması eklenmedi.

Ürün kaynağı ile ayrı runtime girdilerinin koşu öncesi/sonrası özetleri
aynı kaldı. İlk iki hazırlık denemesindeki modül yükleme ve yedek dosya
keşif hataları korunur; başarılı koşu sayılmaz.
[Ölçüm kaydı](evidence/l6-h6-csp.json), gerçek başlıkları, olayları,
derleme kimliğini, kaynak özetlerini ve yerel kapsamı taşır.
Gerçek Supabase/LLM, Linux Chromium ve üretim dağıtımı kabulü koşulmadı.
