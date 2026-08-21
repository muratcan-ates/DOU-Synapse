# Yerel Doğrulama: 010 API Observability

Bu dosya üretim sertifikası değildir. Gerçek sağlayıcı gerekmez; telemetri AI içeriği
taşımaz. Her koşu benzersiz test veritabanı kullanmalı ve bitince DB/süreç/cache
kalıntısı temizlenmelidir.

## Ön koşullar

- `API_OBSERVABILITY_ENABLED=true`
- `API_EVENT_RETENTION_DAYS=7`
- `API_DOCS_ENABLED=true`
- API bağlantısında `session_user=dou_api_runtime`
- en az 10 GiB boş disk; altında ağır browser/build paketi başlatma

## Kanıt sırası

1. Migration + RLS referans testi.
2. Recorder/admin endpoint targeted backend testleri.
3. RLS/validation mutation scripti.
4. OpenAPI security/error drift testi ve deterministic export.
5. Web unit + typecheck + production build.
6. Gerçek API ile Playwright: admin gate, workbench, filters/refresh, non-admin,
   375 px dark, keyboard, reduced-motion ve `/docs` Authorize.
7. Tam backend/web paketleri yalnız disk kapısı açıksa.
8. Dossier/evidence hashleri final candidate'tan sonra bağlanır; CI/staging/insan
   onayı gözlenmediyse açıkça pending kalır.

## Güvenli manuel kontrol

- Admin panelinde istek/route/status/gecikme dışında kişi veya içerik görünmemeli.
- Bir UUID'li course çağrısı sonrasında event route'u gerçek UUID değil
  `/courses/{course_id}/...` olmalı.
- Bilinmeyen yol `UNMATCHED` olmalı; ham yol saklanmamalı.
- Observer DB'si kapatıldığında aynı ürün endpoint'i aynı response'u vermeli; panel
  collector'ı degraded göstermeli.
- Kill switch kapandığında yeni event oluşmamalı; ürün endpointleri çalışmalı.
