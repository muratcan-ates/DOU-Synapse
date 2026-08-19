# Tehdit Modeli: Assessment Integrity

## Varlıklar ve sınırlar

- Gizli resmî soru kökü/seçenek/cevap anahtarı/rubrik/kaynak.
- Öğrencinin ham cevabı ve resmî puanı.
- Dondurulmuş blueprint kalemleri/puanları.
- Trust boundary: student HTTP → FastAPI/JWT → `dou_api_runtime` session →
  transaction-local user GUC/RLS → PostgreSQL.
- Credential boundary: `dou_api_runtime` trusted-backend secret'tır; browser,
  PostgREST/anon istemci veya ders kullanıcısına verilmez.
- AI boundary: student/source text → grading prompt → provider JSON → validator.

## Başlıca saldırılar ve kontroller

| Saldırı | Kontrol | Kırılabilir kanıt |
|---|---|---|
| Student toplu approved havuzu çeker | instructor-only endpoint + purpose-aware RLS | direct API + direct SQL negatif testi |
| Practice ile assessment sorusu toplar | purpose filter + active-exam lock | provider-free selection testi |
| Upgrade'de aynı soru hem legacy practice hem resmî kâğıtta kalır | resmî purpose + yalnız mevcut legacy own-session sahibine dar helper dalı; yeni practice filtresi değişmez | legacy sahibi devam PASS + aynı dersteki oturumsuz öğrenci denial PASS |
| Başkasının item id'sini tahmin eder | own-session RLS helper | cross-user/course mutation |
| Erken bitiren çözümü paylaşır | snapshot release time + result gate | DB clock before/after testi |
| Hatalı/ele geçirilmiş app erken release zamanı yazar | INSERT safe-boundary + immutable snapshot trigger | direct SQL erken INSERT/UPDATE negatifleri |
| Ham carrier oturumu başka student GUC'si yazar | NOLOGIN `dou_app` + runtime-only ACL + exact `session_user` restrictive policy | GUC/`SET ROLE` taklit negatifleri |
| Pooler başka upstream kullanıcıyla runtime adını taklit eder | readiness `app.is_api_runtime()` kontrolü | wrong-role health 503 testi + production DSN preflight |
| Eski API pool migration sırasında yetkisini korur | ayrı commit NOLOGIN + eski login ret kontrolü + aktif `dou_app` session preflight'i | `assessment_runtime_preflight_check.sh`: LOGIN reddi + yaşayan eski bağlantı, 2/2 PASS |
| Carrier bir parent rolden veya runtime beklenmeyen üyeden ek yetki alır | exact rol-grafiği preflight'i; `dou_app` parent yok, runtime üyesi yok, tek parent carrier | temiz-kurulum postcondition iddiaları; bağımsız failure-case negatif testi pending |
| Başka bir owner'ın default ACL'si gelecekte yetkiyi yeniden açar | cross-owner tablo grant temizliği + ilgili function owner'larda global/schema-local PUBLIC EXECUTE revoke + etkin kalıntıda fail-closed | migration sonrası başka-owner probe fonksiyonun etkin ACL kontrolü |
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

Mixed-use upgrade kanıtı mevcut legacy sahibini ve aynı dersteki oturumsuz bir
öğrenciyi ölçer; farklı sorulu başka legacy kâğıt ve cross-course varyantı henüz ayrı
fixture değildir. Rol-grafiği temiz postcondition'ı ölçülür, fakat her beklenmeyen
parent/member kenarının migration'ı durdurduğu bağımsız negatif paket henüz yoktur.

Gerçek `dou_api_runtime` credential'ı veya API process'i ele geçirilirse saldırgan
GUC bağlamını taklit etmeyi deneyebilir. Exact-login kapısı ham carrier'ı keser,
backend compromise'ını çözmez; secret vault/rotation, ağ sınırı, içeriksiz audit ve
staging pooler doğrulaması kalan zorunlu operasyonel kontrollerdir.
