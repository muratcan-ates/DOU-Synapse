## Amaç ve kapsam

<!-- Kullanıcı yolculuğunu ve neden bu değişikliğe ihtiyaç duyulduğunu yazın. -->

- Speckit / görev:
- İncelenen base SHA:
- Aday head SHA:
- Kapsam dışı bırakılanlar:

## Değişiklik özeti

<!-- Önemli davranış, sözleşme, migration ve kullanıcı arayüzü değişikliklerini yazın. -->

## Doğrulama kanıtı

<!-- Her satıra tam komut, sonuç ve mümkünse CI/artifact bağlantısı ekleyin.
     Koşulmayan bir kontrolü yeşil işaretlemeyin; KOŞULMADI ve nedenini yazın. -->

- [ ] Hedefli testler:
- [ ] İlgili tam backend/frontend paketi:
- [ ] Ruff / format / mypy / typecheck / build:
- [ ] Migration, RLS ve kırılabilirlik mutasyonu (uygulanıyorsa):
- [ ] OpenAPI ve istemci sözleşmesi (uygulanıyorsa):
- [ ] Tarayıcı veya gerçek HTTP yolculuğu (uygulanıyorsa):
- [ ] `docs_check` ve değişen kılavuzlar:
- [ ] Koşulmayan kontroller ve gerekçeleri açıkça listelendi:

## AI değişiklik dosyası

- [ ] Bu PR AI davranışına duyarlı bir yolu değiştirmiyor.
- [ ] Değiştiriyor; dossier yolu: `.ai/changes/`
- Risk: `R1 / R2 / R3`
- Kanıt etiketi: `fake-provider / offline-replay / real-provider / staging / canary / production`
- Değişen prompt/model/provider/embedding/retrieval/guardrail/evaluator/corpus:
- Artifact yolları ve SHA-256 doğrulaması:
- Kalibrasyon ve holdout ayrımı:
- Değiştirilen evaluator için bağımsız sabit/human-reviewed anchor:
- Yazar olmayan onay sahibi ve rolü:
- Rollout, kill switch ve durdurma koşulları:
- Rollback adımı ve geri dönüş doğrulaması:
- İzlenecek metrikler, gizlilik sınırı ve inceleme tarihi:

> Fake-provider veya yalnız çevrimdışı kanıt, gerçek model kalitesi ya da production
> kanıtı değildir. Production iddiası güncel aday için gerçek sağlayıcı, isimli insan
> değerlendirmesi, kontrollü rollout ve gözlenen telemetry gerektirir.

## Güvenlik, gizlilik ve veri

- [ ] Yetkilendirme/RLS/rol sınırı etkisi açıklandı ve negatif test eklendi ya da etkisizliği gerekçelendirildi.
- [ ] Prompt, cevap, chunk, JWT, öğrenci kimliği ve tam e-posta log/artifact içine girmiyor.
- [ ] Yeni veya değişen bağımlılık/action kimliği, lockfile ve dependency-review kapsamına alındı.
- [ ] Migration varsa geriye uyumluluk, yedekleme ve forward-fix/rollback kararı yazıldı.
- [ ] Secret eklenmedi; örnek yapılandırma yalnız placeholder içeriyor.

## Teslimat ve geri dönüş

- Deployment durumu: `yok / not configured / staging / production`
- Kaynak SHA ve immutable artifact/digest:
- Migration sırası ve uyumluluk kararı:
- Rollback/forward-fix planı:
- Canlı URL ve zaman damgalı smoke kanıtı (yalnız gerçekten koştuysa):

## İnceleyene odak noktaları

<!-- En riskli dosyaları, kabul edilen borcu, istisna sahibini ve son kullanma tarihini yazın. -->
