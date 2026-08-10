# API Sözleşmeleri — 001-course-assistant-mvp

Bu dizindeki `openapi.json`, FastAPI uygulamasından **export edilmiş** OpenAPI 3.1
şemasıdır (el yazımı değildir). Kaynak gerçeği kod tarafıdır:
`apps/api/app/api/*.py` + `apps/api/app/main.py`. Şema ile kod arasında fark
görülürse şema yeniden üretilir (aşağıdaki komut).

- API başlığı / sürümü: `DOU-Synapse API` / `0.1.0` (`apps/api/app/core/config.py`)
- Plan bağlamı: [PLAN.md](../../../PLAN.md) · Mimari: [ARCHITECTURE.md](../../../ARCHITECTURE.md)

---

## Mevcut sözleşme (43 yol, 58 işlem)

Yetki sütunu üç seviyedir:

- **yok** — kimlik doğrulama gerekmez
- **kimlik** — geçerli Bearer token yeter (`get_principal`)
- **üye** — dersin aktif üyesi olmak gerekir (`require_course_member`; üye olmayan
  kullanıcıya dersin varlığını sızdırmamak için **404** döner)
- **eğitmen** — dersin eğitmeni olmak gerekir (`require_course_instructor`; üyeyse ama
  eğitmen değilse **403**)

Tam ayrıntı `openapi.json` içindedir. Aşağıdaki tablo yüzeyleri özetler; endpoint
adlarını ikinci bir yerde 56 satırla kopyalamaz.

| Aile | Yetki | Sözleşme |
|---|---|---|
| `/health/*` | yok | Liveness, DB/pgvector ve embedding warmup readiness |
| `/courses`, `/members` | kimlik / eğitmen | Ders ve üyelik yönetimi; ders listesi cursor sayfalıdır |
| `/documents`, `/chunks`, `/retry` | üye / eğitmen | Yükleme, açık kaynak sürümü, işleme durumu, chunk önizleme ve başarısız işi yeniden kuyruğa alma |
| `/chat`, `/chat/availability`, `/chat/sessions` | üye | Kaynaklı QA/Sokratik akış, sınav kilidi, cursor sayfalı oturum+mesaj geçmişi |
| `/chat/messages/*/feedback`, `/chat/quality` | üye / eğitmen | Gerekçeli öğrenci puanı, toplu kalite ölçümü ve yalnız açık izinli inceleme kayıtları |
| `/questions`, `/questions/generate` | üye / eğitmen | Dört soru tipi, taslak→onay kapısı, üretim kotası ve cursor sayfalama |
| `/blueprints`, `/learning-outcomes`, `/exam-versions` | üye / eğitmen | Blueprint hücreleri, öğrenme çıktıları, kaynak sürümü, yayın ve değişmez sınav sürümü |
| `/exams`, `/answers` | üye | Practice/exam oturumu, süre, puan, rubrik kırılımı ve neden-yanlış |
| `/policy` | eğitmen | Ders bazlı mod, kaynak, kanıt eşiği, ipucu ve token bütçesi |
| `/analytics` | öğrenci / eğitmen | Kişisel mastery ve anonimleştirilmiş sınıf özeti |
| `/me/export`, `/me/chat-history`, `/me/anonymize` | kimlik | KVKK dışa aktarma, silme ve güvenli anonimleştirme |
| `/internal/drain` | paylaşılan sır | Ayrı worker kuyruğu; sır yoksa/yansa 404 fail-closed |

**İzolasyon kuralı (tüm `{course_id}` yolları):** yol parametresindeki `course_id` bir
yetki belgesi değildir; her istekte sunucu tarafında üyelik tablosundan doğrulanır
(`apps/api/app/api/deps.py`). İkinci katman olarak aynı oturumda Postgres RLS devrededir.

---

## Hata zarfı sözleşmesi

Uygulama hataları tek biçimde döner (`apps/api/app/core/errors.py`,
`app_error_handler`):

```json
{ "error": { "code": "...", "message": "Anlaşılır Türkçe mesaj.", "request_id": "..." } }
```

`message` her zaman kullanıcıya gösterilebilir Türkçedir; frontend kendi hata metnini
uydurmaz (Anayasa İlke V). Ham stack trace veya sağlayıcı hatası asla sızmaz.

| HTTP | `code` | Ne zaman |
|---|---|---|
| 400 | `app_error` | Genel uygulama hatası (taban sınıf varsayılanı) |
| 401 | `unauthenticated` | Token yok / geçersiz / süresi dolmuş |
| 403 | `permission_denied` | Üye ama yetki yetersiz (ör. öğrenci eğitmen ucunu çağırdı) |
| 404 | `not_found` | Kayıt yok **veya** kullanıcı o derse üye değil (varlık sızdırılmaz) |
| 409 | `conflict` | Mükerrer ders kodu, mükerrer üyelik, aynı dosyanın tekrar yüklenmesi |
| 413 | `payload_too_large` | Yükleme boyut sınırı aşıldı (varsayılan 20 MB) |
| 429 | `rate_limited` | Sohbet veya soru üretimi kotası aşıldı |
| 422 | `validation_error` | Uygulama seviyesi doğrulama (ör. "kendi eğitmen üyeliğinizi kaldıramazsınız") |
| 503 | `storage_unavailable` | Kalıcı belge deposuna geçici olarak erişilemiyor |
| 500 | `internal_error` | Beklenmeyen hata; ayrıntı loga, kullanıcıya genel mesaj |

FastAPI/Pydantic doğrulama hataları da aynı zarfı ve Türkçe mesajı kullanır.
`request_id` destek ekranında kopyalanabilir; sağlayıcı hata metni veya stack trace
zarfın içine girmez.

---

## Kimlik doğrulama şeması

Tüm korumalı uçlar `Authorization: Bearer <token>` bekler
(`apps/api/app/core/security.py`):

1. **Üretim / normal yol:** Supabase Auth'un verdiği JWT. Backend, `SUPABASE_JWT_SECRET`
   ile HS256 doğrular (`aud=authenticated`, `exp` ve `sub` zorunlu); `sub` → `user_id`.
2. **Geliştirme yolu:** `Bearer dev:<uuid>` biçiminde imzasız kimlik. **Yalnızca**
   `DEV_AUTH_ENABLED=true` iken kabul edilir; `ENVIRONMENT=production` ile birlikte
   açılmaya çalışılırsa config doğrulayıcısı ayarların yüklenmesini reddeder — yani bu
   yol canlıda hiç var olamaz (fail-closed, `config.py::_check_auth_configuration`).

Yetkilendirme (kim hangi derse erişir) token katmanında değil, ders bağımlılıklarında
(`deps.py`) ve RLS'te yapılır. API veritabanına tablo sahibi olmayan, BYPASSRLS
taşımayan `dou_app` rolüyle bağlanır.

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
- CI aynı export'u yeniden üretip diff alır; kodla sözleşme ayrışırsa yapı düşer.
