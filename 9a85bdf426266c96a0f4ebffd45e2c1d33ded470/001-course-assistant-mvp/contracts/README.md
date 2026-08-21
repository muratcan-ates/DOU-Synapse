# API Sözleşmeleri — 001-course-assistant-mvp

Bu dizindeki `openapi.json`, FastAPI uygulamasından **export edilmiş** OpenAPI 3.1
şemasıdır (el yazımı değildir). Kaynak gerçeği kod tarafıdır:
`apps/api/app/api/*.py` + `apps/api/app/main.py`. Şema ile kod arasında fark
görülürse şema yeniden üretilir (aşağıdaki komut).

- API başlığı / sürümü: `DOU-Synapse API` / `0.1.0` (`apps/api/app/core/config.py`)
- Plan bağlamı: [PLAN.md](../../../PLAN.md) · Mimari: [ARCHITECTURE.md](../../../ARCHITECTURE.md)

---

## Mevcut uçlar (9 yol, 13 işlem)

Yetki sütunu üç seviyedir:

- **yok** — kimlik doğrulama gerekmez
- **kimlik** — geçerli Bearer token yeter (`get_principal`)
- **üye** — dersin aktif üyesi olmak gerekir (`require_course_member`; üye olmayan
  kullanıcıya dersin varlığını sızdırmamak için **404** döner)
- **eğitmen** — dersin eğitmeni olmak gerekir (`require_course_instructor`; üyeyse ama
  eğitmen değilse **403**)

| Metot | Yol | Yetki | Amaç |
|---|---|---|---|
| GET | `/health/live` | yok | Süreç ayakta mı (bağımlılıksız); `{status, environment, version}` |
| GET | `/health/ready` | yok | DB + pgvector erişimi; sorun varsa 503 `degraded`. Deploy duman testi ve demo günü ısıtma isteği bu ucu kullanır |
| GET | `/courses` | kimlik | Kullanıcının aktif üyeliği olan dersler (dersteki rolüyle birlikte) |
| POST | `/courses` | kimlik | Ders oluşturur; oluşturana aynı işlemde eğitmen üyeliği verir (`app.create_course`). 201; kod çakışmasında 409 |
| GET | `/courses/{course_id}` | üye | Tek ders + kullanıcının rolü |
| GET | `/courses/{course_id}/members` | eğitmen | Ders üye listesi (e-posta, ad, rol, durum) |
| POST | `/courses/{course_id}/members` | eğitmen | E-postayla üye ekler (`app.add_course_member`). Kullanıcı kayıtlı değilse 404, zaten üyeyse 409 |
| DELETE | `/courses/{course_id}/members/{user_id}` | eğitmen | Üyeliği iptal eder (soft: `status=revoked`, kayıt silinmez). Eğitmen kendini çıkaramaz (422). 204 |
| POST | `/courses/{course_id}/documents` | eğitmen | Materyal yükler (multipart `file`): uzantı + boyut + magic byte doğrulaması, `file_hash` ile mükerrer engeli (409), ingestion job + worker tetiği. **202** döner; istemci `status` alanını izler |
| GET | `/courses/{course_id}/documents` | üye | Dersin belgeleri (durum: `uploaded / processing / completed / failed`) |
| GET | `/courses/{course_id}/documents/{document_id}` | üye | Tek belge durumu (ilerleme takibi için poll edilir) |
| DELETE | `/courses/{course_id}/documents/{document_id}` | eğitmen | Belgeyi ve FK cascade ile tüm chunk'larını siler. 204 |
| GET | `/courses/{course_id}/documents/{document_id}/chunks` | eğitmen | İlk chunk'ların önizlemesi (`limit`, varsayılan 20, tavan 100) — eğitmen sistemin belgeden ne çıkardığını görür |

**İzolasyon kuralı (tüm `{course_id}` yolları):** yol parametresindeki `course_id` bir
yetki belgesi değildir; her istekte sunucu tarafında üyelik tablosundan doğrulanır
(`apps/api/app/api/deps.py`). İkinci katman olarak aynı oturumda Postgres RLS devrededir.

---

## Hata zarfı sözleşmesi

Uygulama hataları tek biçimde döner (`apps/api/app/core/errors.py`,
`app_error_handler`):

```json
{ "error": { "code": "...", "message": "Anlaşılır Türkçe mesaj." } }
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
| 422 | `validation_error` | Uygulama seviyesi doğrulama (ör. "kendi eğitmen üyeliğinizi kaldıramazsınız") |
| 500 | `internal_error` | Beklenmeyen hata; ayrıntı loga, kullanıcıya genel mesaj |

**Bilinen istisna:** FastAPI/Pydantic'in kendi istek doğrulama hatası (bozuk UUID, eksik
gövde alanı vb.) hâlâ FastAPI'nin standart `{"detail": [...]}` biçiminde döner —
`openapi.json`'daki `HTTPValidationError` şeması budur ve zarfın dışındadır.
[NEEDS CLARIFICATION: RequestValidationError handler'ı da zarfa çekilecek mi, yoksa
frontend iki biçimi de mi tanıyacak?]

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

## Planlanan uçlar — HENÜZ YOK

Aşağıdakiler ARCHITECTURE.md §5 (sorgu pipeline'ı + cevap şeması) ve PLAN.md
takviminden gelir; **bu sözleşmede henüz yer almazlar, kodda da yokturlar.** İsimler
göstergedir; yol adları implementasyonla birlikte dondurulacak ve `openapi.json`
yeniden export edilecektir.

| Alan | Beklenen uç(lar) | Kaynak | Durum |
|---|---|---|---|
| Kaynaklı sohbet + Sokratik mod | `chat` (soru sor; `mode: qa \| socratic`; cevap şeması: `status / answer / citations[] / hints[]`) | ARCHITECTURE §5, PLAN G5-G7 | **henüz yok** |
| Sınav prova modu | `exam` oturumları (başlat, cevapla, bitir; `mode: practice \| exam`; "neden yanlış?" geri bildirimi) | ARCHITECTURE §5, PLAN G9 | **henüz yok** |
| Soru havuzu | `questions` (üretim + eğitmen onay akışı; `mcq / open / code_trace / bug_hunt`) | PLAN G8, veri modeli §3 | **henüz yok** |
| Analitik / mastery | eğitmen özet ekranı verisi | PLAN G10, ARCHITECTURE §5 (Mastery-Lite) | **henüz yok** |

Frontend bu uçlar için mock'la ilerler; gerçek sözleşme çıktığında mock'lar şemaya
karşı doğrulanır.

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
- Uç ekleyip export'u unutmamak için PR kontrol listesine "sözleşme güncel mi?"
  maddesi eklenir. [NEEDS CLARIFICATION: bu export CI'da otomatik diff kontrolüne
  bağlanacak mı?]
