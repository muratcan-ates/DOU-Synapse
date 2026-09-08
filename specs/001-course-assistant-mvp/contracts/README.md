# API sözleşmesi

`openapi.json`, FastAPI uygulamasından üretilir; elle yazılmış şema değildir. Kaynak gerçeği `apps/api/app/api/` ve `apps/api/app/schemas/` altındaki koddur. Bu dizinin numarası ilk ürün diliminden gelir; şema güncel uygulamayı izler.

8 Eylül 2026, 018 adayından alınan yerel export: **57 yol, 73 HTTP işlemi**, OpenAPI 3.1, uygulama sürümü 0.1.0. Export veritabanına veya gerçek model sağlayıcısına bağlanmaz; bir çalışma zamanı ya da canlı ortam testi değildir.

## Aileler

Etiket sayıları otomatik şemadan ölçülmüştür. Bir işlem birden fazla etiket taşıyabildiğinden bu sütun toplamı benzersiz işlem sayısını vermez.

| Etiket | İşlem etiketi sayısı |
|---|---:|
| health | 2 |
| profile | 2 |
| dashboard | 1 |
| admin | 5 |
| courses | 6 |
| documents | 6 |
| sources | 2 |
| privacy | 5 |
| chat | 4 |
| policy | 3 |
| assessment | 10 |
| chat-quality | 2 |
| exams | 10 |
| blueprints | 13 |
| analytics | 2 |

## Yetki ve yanıt sınırları

Korumalı uçlar `Authorization: Bearer <token>` bekler. Normal yol HS256 Supabase JWT doğrulamasıdır; üretimde issuer açıkça tanımlanır. İmzasız `dev:<uuid>` yalnız geliştirme ayarıyla kullanılabilir; üretim ayarları bunu reddeder. Ders kimliği yetki belgesi değildir: üyelik kontrolü ve aynı oturumda PostgreSQL RLS birlikte çalışır. Üye olmayana ders varlığını açıklamayan 404, üye olup ilgili işlem yetkisi olmayana 403 döner.

Sayfalama tek tip değildir. Kaynak ve soru listelerinde imleç, yönetim uçlarında offset/total, politika geçmişinde limit/offset kullanan düz dizi gibi ayrı mevcut sözleşmeler vardır. Tüketici ilgili uç şemasını esas almalıdır.

Sınav cevap anahtarı ve ölçüt geri bildirimi açıklanma kuralına bağlıdır. Çalışma cevabı kendi okuma ucundan, tamamlanmış sınav ise sonuç ucundan açılır; tamamlanmış sınavın tek-cevap ucunu çağırmak da izin vermez. 018 ekleri [değişiklik sözleşmesinde](../../018-codex-production-line/contracts/api.md) açıklanır.

## Bilinen OpenAPI eksikleri

Çalışma zamanı hata zarfı şöyledir:

```json
{"error":{"code":"permission_denied","message":"Kullanıcıya gösterilebilir açıklama","request_id":"destek-kimliği"}}
```

Bu export hata zarfının bütün yanıt kodlarını henüz şemalamaz; FastAPI'nin `HTTPValidationError` şeması görünür. Ayrıca bearer yetkisinin `securitySchemes` bildirimi eksiktir. Bunlar dokümantasyon/istemci üretim boşluklarıdır; API'nin çalışma zamanı kimlik kontrolünü kaldırmaz. Şemadan otomatik istemci üreten tüketiciler hata ve auth sözleşmelerini yalnız bu exporttan tam olarak çıkaramaz. Eksikler kapatılmadan şemanın eksiksiz olduğu iddia edilmez.

## Yeniden üretme

`apps/api` içinden, yalnız yerel export ayarlarıyla:

```bash
ENVIRONMENT=local DEV_AUTH_ENABLED=true EMBEDDING_PROVIDER=hashing GROQ_API_KEY= GEMINI_API_KEY= OPENAI_API_KEY= uv run python -c '
import json
from app.main import create_app
print(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2))
' > ../../specs/001-course-assistant-mvp/contracts/openapi.json
```

İstemci tipleri hâlâ elle tutulur; yeni alanların web tipleri, gerçek API geri okuma testleri ve ilgili tarayıcı senaryolarıyla birlikte doğrulanması gerekir.
