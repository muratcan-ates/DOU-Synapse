# API Sözleşmeleri — 001-course-assistant-mvp

Bu dizindeki `openapi.json`, FastAPI uygulamasından **export edilmiş** OpenAPI 3.1
şemasıdır (el yazımı değildir). Kaynak gerçeği kod tarafıdır:
`apps/api/app/api/*.py` + `apps/api/app/main.py`. Şema ile kod arasında fark
görülürse şema yeniden üretilir (aşağıdaki komut).

- API başlığı / sürümü: `DOU-Synapse API` / `0.1.0` (`apps/api/app/core/config.py`)
- Plan bağlamı: [PLAN.md](../../../PLAN.md) · Mimari: [ARCHITECTURE.md](../../../ARCHITECTURE.md)

> Bu dosyanın önceki sürümü iki teslim geride kalmıştı ("9 yol / 13 işlem" diyor,
> bugün canlı olan uçları "henüz yok" sayıyordu). 16 Ağustos'ta canlı spec'ten
> ölçülerek yeniden yazıldı; uç listesi elle değil aşağıdaki export komutunun
> çıktısından türetilir.

---

## Mevcut uçlar (53 yol, 69 işlem — canlı spec'ten ölçüldü)

Tek tek uçların şeması, parametreleri ve yanıt tipleri `openapi.json`'dadır; burada
yalnız aile haritası tutulur (etiketler spec'teki `tags` alanından):

| Aile | İşlem | Kapsam |
|---|---|---|
| health | 2 | `live` (bağımlılıksız) + `ready` (DB/pgvector; ısınma durumunu da taşır) |
| courses | 4+ | ders CRUD'u, üyelik ekleme/iptal (soft revoke) |
| documents | 5 | yükleme (202 + durum izleme), listeleme, silme, chunk önizleme, ingestion retry |
| sources | 2 | kaynak bağlamı: chunk görüntüleme + inspect |
| chat | 2 | soru sorma (`mode: qa \| socratic`) + kullanılabilirlik |
| chat/privacy | 4 | oturum listeleme/silme, mesaj geçmişi (keyset sayfalama) |
| chat-quality | 2 | mesaj geri bildirimi + eğitmen kalite panosu |
| exams | 6 | oturum başlat/cevapla/bitir/ipucu; blueprint'e bağlı sınav dahil |
| assessment | 6 | soru üretimi + eğitmen onay akışı + konu yönetimi |
| blueprints | 7 | sınav planı ailesi: sürümleme, madde, yayınlama, hazırlık kontrolü |
| policy | 2 | ders AI politikası (GET/PUT) + politika geçmişi |
| analytics | 2 | sınıf ve kişisel analitik |
| privacy | 3 | KVKK: veri dışa aktarımı, sohbet geçmişi silme, hesap silme |
| profile / dashboard / admin | 8 | profil, kullanıcı panosu, Bilgi İşlem salt-okunur admin (5 uç, `total/offset` sayfalama istisnası — bilinçli ve belgeli sınır) |

**İzolasyon kuralı (tüm `{course_id}` yolları):** yol parametresindeki `course_id` bir
yetki belgesi değildir; her istekte sunucu tarafında üyelik tablosundan doğrulanır
(`apps/api/app/api/deps.py`). Üye olmayana ders varlığı sızdırılmaz (**404**), üye ama
yetkisiz olana **403** döner. İkinci katman olarak aynı oturumda Postgres RLS devrededir.

**Sayfalama:** liste uçları `{items, next_cursor}` zarfı ve opak keyset imleci kullanır
(`apps/api/app/core/pagination.py` — `paginate` / `paginate_keyset` tek uygulama).
Tek istisna, ayrı tüketicisi olan `/admin` uçlarının `total/offset` biçimidir.

---

## Hata zarfı sözleşmesi

Uygulama hataları tek biçimde döner (`apps/api/app/core/errors.py`; dört handler —
`AppError`, router `HTTPException`, `RequestValidationError` ve beklenmeyen istisna —
`main.py`'de kayıtlıdır):

```json
{ "error": { "code": "...", "message": "Anlaşılır Türkçe mesaj.", "request_id": "..." } }
```

- `message` her zaman kullanıcıya gösterilebilir Türkçedir; frontend kendi hata metnini
  uydurmaz (Anayasa İlke V). Ham stack trace veya sağlayıcı hatası asla sızmaz.
- `request_id` zorunludur ve destek kodu olarak kullanıcıya gösterilir; middleware
  atlansa bile handler üretir (`X-Request-ID` başlığıyla aynı değer).

| HTTP | `code` | Ne zaman |
|---|---|---|
| 400 | `app_error` | Genel uygulama hatası (taban sınıf varsayılanı) |
| 401 | `unauthenticated` | Token yok / geçersiz / süresi dolmuş |
| 403 | `permission_denied` | Üye ama yetki yetersiz (ör. öğrenci eğitmen ucunu çağırdı) |
| 404 | `not_found` | Kayıt yok **veya** kullanıcı o derse üye değil (varlık sızdırılmaz) |
| 409 | `conflict` | Mükerrer ders kodu, mükerrer üyelik, aynı dosyanın tekrar yüklenmesi |
| 413 | `payload_too_large` | Yükleme boyut sınırı aşıldı (varsayılan 20 MB) |
| 422 | `validation_error` | Doğrulama — uygulama seviyesi VE FastAPI/Pydantic istek doğrulaması. Eski "detail biçimi zarfın dışında" istisnası kapandı: `RequestValidationError` handler'ı da zarfı üretir (`tests/test_error_envelope.py` kanıtı) |
| 429 | `rate_limited` / `agent_*` | İstek sıklığı veya AI kota sınırları (`retry_after` taşır) |
| 503 | `pipeline_unavailable` / `course_agent_disabled` | Cevap hattı takılı değil ya da asistan kapalı (fail-closed) |
| 500 | `internal_error` | Beklenmeyen hata; ayrıntı loga, kullanıcıya genel mesaj |

`010-api-observability` adayı bu runtime/spec boşluğunu kapatır: mevcut 422 yanıtları
`ErrorEnvelope` referansına çevrilir, korumalı işlemler `BearerAuth`, bütün işlemler
500 zarfını taşır ve `HTTPValidationError` artık export edilen sözleşmede kalmaz.
Bilinmeyen yol ile yanlış metot da runtime'da aynı Türkçe zarfı döndürür. Bu iddia
generated JSON ve `tests/test_openapi_contract.py` ile birlikte doğrulanır.

---

## Kimlik doğrulama şeması

Tüm korumalı uçlar `Authorization: Bearer <token>` bekler
(`apps/api/app/api/deps.py`, `apps/api/app/core/security.py`). Yerel/demo Swagger
`Authorize` düğmesi aynı HTTP Bearer şemasını kullanır. `/health/live` ve
`/health/ready` public kalır; production'da docs/OpenAPI yüzeyi fail-closed kapalıdır:

1. **Üretim / normal yol:** Supabase Auth'un verdiği JWT. Backend, `SUPABASE_JWT_SECRET`
   ile HS256 doğrular (`aud=authenticated`, `exp` ve `sub` zorunlu); `sub` → `user_id`.
2. **Geliştirme yolu:** `Bearer dev:<uuid>` biçiminde imzasız kimlik. **Yalnızca**
   `DEV_AUTH_ENABLED=true` iken kabul edilir; `ENVIRONMENT=production` ile birlikte
   açılmaya çalışılırsa config doğrulayıcısı ayarların yüklenmesini reddeder — yani bu
   yol canlıda hiç var olamaz (fail-closed, `config.py::_check_auth_configuration`).

Yetkilendirme (kim hangi derse erişir) token katmanında değil, ders bağımlılıklarında
(`deps.py`) ve RLS'te yapılır. API veritabanına tablo sahibi olmayan, BYPASSRLS
taşımayan gerçek LOGIN `dou_api_runtime` rolüyle bağlanır; `dou_app` NOLOGIN izin
taşıyıcısıdır.

---

## openapi.json nasıl yeniden üretilir

Şema elle düzenlenmez; API kodu değiştikçe `apps/api` içinden yeniden export edilir.
`create_app()` ayarları yüklerken kimlik konfigürasyonu ister; export için
`DEV_AUTH_ENABLED=true` yeterlidir (veritabanına bağlanılmaz):

```bash
cd apps/api
DEV_AUTH_ENABLED=true uv run python -c "
import json
from app.main import create_app
print(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2))
" > ../../specs/001-course-assistant-mvp/contracts/openapi.json
```

Notlar:

- `ensure_ascii=False` zorunludur: docstring'lerdeki Türkçe metin (ör. "Ders kimliği")
  escape edilmeden kalmalı.
- `apps/api/tests/test_openapi_contract.py` tracked JSON'u gerçek
  `create_app().openapi()` çıktısıyla birebir karşılaştırır; CI backend paketi bu
  drift kapısını çalıştırır. Şema değişince export ve kod aynı adayda güncellenmelidir.
- Frontend tipleri (`apps/web/lib/types.ts` + `lib/*.ts`) spec'in elle yazılmış
  aynasıdır; codegen yoktur. Ölçülmüş drift listesi ve kapatma planı için
  [docs/team/modularization-v2-audit.md](../../../docs/team/modularization-v2-audit.md) §5-7.
