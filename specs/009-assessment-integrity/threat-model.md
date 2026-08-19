# Tehdit Modeli: Assessment Integrity

## Varlıklar ve sınırlar

- Gizli resmî soru kökü/seçenek/cevap anahtarı/rubrik/kaynak.
- Öğrencinin ham cevabı ve resmî puanı.
- Dondurulmuş blueprint kalemleri/puanları.
- Trust boundary: student HTTP → FastAPI → RLS session → PostgreSQL.
- AI boundary: student/source text → grading prompt → provider JSON → validator.

## Başlıca saldırılar ve kontroller

| Saldırı | Kontrol | Kırılabilir kanıt |
|---|---|---|
| Student toplu approved havuzu çeker | instructor-only endpoint + purpose-aware RLS | direct API + direct SQL negatif testi |
| Practice ile assessment sorusu toplar | purpose filter + active-exam lock | provider-free selection testi |
| Başkasının item id'sini tahmin eder | own-session RLS helper | cross-user/course mutation |
| Erken bitiren çözümü paylaşır | snapshot release time + result gate | DB clock before/after testi |
| Client saati ileri alır | DB `now()` | client timestamp etkisiz testi |
| Düşük puanlı soru yüksek ağırlık gibi hesaplanır | question-id points map | 10/90 ve reordered answer testi |
| Answer/source “score=100” talimatı verir | escaped untrusted blocks | adversarial fake completion |
| Model rubriğin bir kısmını atlar | exact-set validation → ungraded | missing/duplicate/unknown matrix |
| Model uydurma evidence verir | set membership → ungraded | forged UUID testi |
| Rollback mevcut sınavı kilitler | flag yalnız new start | active-session flag-off test |

## Artık risk

Fake completion, gerçek sağlayıcının pedagojik/adalet davranışını kanıtlamaz. Gerçek
provider adversarial holdout, iki bağımsız domain etiketi, security/privacy onayı,
staging ve canary tamamlanana kadar promotion yapılmaz.

