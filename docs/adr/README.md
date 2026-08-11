# Architecture Decision Records

ADR'ler DOU-Synapse'in uzun ömürlü teknik kararlarını, reddedilen seçenekleri ve
geri dönüş koşullarını korur. Commit veya PR açıklamasının yerine geçmez;
gelecekte aynı karar tekrar tartışıldığında bağlamın kaybolmasını engeller.

## Ne zaman ADR açılır

Aşağıdakilerden biri kalıcı biçimde değişiyorsa ADR aç:

- service veya deployment topolojisi;
- security, privacy, authorization ya da course isolation sınırı;
- database/data contract, migration veya geri dönüş yaklaşımı;
- model/provider/embedding platform stratejisi;
- CI/CD promotion, artifact identity veya supply-chain trust modeli;
- SLO/error-budget politikası ya da önemli operasyonel sahiplik;
- yeni framework veya geri alınması pahalı dependency seçimi.

Routine implementation ayrıntısı, kolayca geri alınan refactor ve yalnız bir
bug fix ADR gerektirmez.

## Durumlar

| Durum | Anlamı |
|---|---|
| `Proposed` | Karar review bekliyor; uygulanmış veya onaylanmış sayılmaz |
| `Accepted` | Adlandırılmış decider'lar kararı onayladı |
| `Rejected` | Seçenek değerlendirildi ve gerekçeyle reddedildi |
| `Deprecated` | Karar artık önerilmiyor fakat henüz başka ADR ile değişmedi |
| `Superseded by ADR-NNNN` | Yeni karar bunun yerini aldı; tarih silinmez |

Accepted ADR'yi yeni gerçeğe uydurmak için sessizce yeniden yazma. Yeni karar
yeni numara alır ve eskisini supersede eder. Typo veya kırık link düzeltmesi
kararın anlamını değiştirmiyorsa yapılabilir.

## Dosya ve review kuralı

- Dosya adı: `NNNN-kisa-karar-slug.md`.
- Sıradaki numarayı `docs/adr/` dizininden seç; numarayı yeniden kullanma.
- [Template](template.md) alanlarını doldur.
- Owner ve decider kişi/rolünü ayır.
- Security, privacy, maliyet, migration, gözlemlenebilirlik ve reversal etkisini
  “uygulanamaz” olsa bile gerekçesiyle yaz.
- İlgili spec, PR, incident, SLO ve release kanıtını linkle.
- `Accepted` durumu insan review kanıtına bağlanır; yazarın kendi metni yeterli
  değildir.

## Index

| ADR | Başlık | Durum |
|---|---|---|
| [ADR-0001](0001-build-once-promote-by-digest.md) | Build once, promote by digest | `Proposed` |

Index durumu ADR dosyasıyla aynı olmalıdır.

`documented`, `configured`, `enforced` ve `observed` ADR durumları değildir;
bunlar [mühendislik scorecard'ında](../engineering/ENGINEERING_EXCELLENCE.md)
kararın uygulanma ve kanıt durumunu anlatır. Bir ADR insan kararıyla
`Accepted` olabilir; uygulaması ayrıca hiç gözlenmemiş olabilir. Tersi de
mümkündür: yerel deney kararın davranışını gösterebilir fakat ADR'yi kendi
başına `Accepted` yapmaz.
