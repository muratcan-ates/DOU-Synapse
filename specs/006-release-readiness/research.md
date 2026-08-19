# Research: Release Readiness

## Decision 0: PR #17 sonrasında current main'e yeniden tabanlan

**Decision**: Release-readiness commit'lerini, çalışma başladıktan sonra main'e
giren web bağımlılık PR #17'sinin exact SHA'sı
`2f40ac193114b896d33ef73e72ea51cc51f34d26` üzerine yeniden tabanla.

**Rationale**: İlk kapsam tabanı `6c35a7f0bdb44b88205f408ca18e6a4e50cb153e`
korunan tarihsel lineage'dır; ancak eski `package.json`/`bun.lock` değerlerini
yanlışlıkla geri taşımamak için teslim tabanı current main olmalıdır. Bu slice
bağımlılık manifestlerine dokunmaz.

## Decision 1: Deploy workflow değil preflight CLI

Staging target, protected environment, OIDC ve secret'lar henüz yapılandırılmadı. Bu nedenle yeni bir deployment workflow'u gerçekte çalıştırılamaz ve yanlış hazır olma algısı yaratır. İlk dilim yalnız kanıt toplar ve eksikte kapanır.

## Decision 2: Standard library ve dependency injection

`.release` araçları bağımlılıksız çalışıyor. HTTP ve komut yürütme adaptörleri enjekte edilerek ağsız birim testleri yapılır; gerçek koşu `urllib`, `subprocess` ve `json` kullanır.

## Decision 3: Secret yalnız environment'ta

JWT, database URL ve Supabase service-role anahtarı komut satırı argümanı olmaz; process listesi, log ve rapora sızmaz. Çıktıda yalnız configured/sonuç bilgisi yer alır.

## Decision 4: Preflight promotion evidence değildir

Rapor `kind: staging_preflight` taşır. Başarılı preflight bile protected approval, deploy record ve observation kanıtı olmadan `staging-verified` veya production terfisi sayılmaz.

## Decision 5: Browser gate gerçek API kararını sınar

Aktif sınav, yasak `mode: exam` ve kill switch için tarayıcı bağlamından ham fetch kullanılır. UI gizleme tek başına güvenlik kanıtı değildir. Global kill switch ayrı API sürecinde gerçek config ile açılır; UI mesajı sunucu reason'ını korur.
