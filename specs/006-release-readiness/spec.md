# Feature Specification: Release Readiness

**Feature Branch**: `006-release-readiness`

**Created**: 2026-08-19

**Status**: In Progress

**Input**: PR #16 sonrasında, canlı ortama geçmeden önce yanlış başarı iddialarını engelleyen bir staging preflight aracı ve eksik sınav/kill-switch tarayıcı kapıları geliştir.

## User Scenarios & Testing

### User Story 1 - Staging engellerini tek komutla gör (Priority: P1)

Release sorumlusu bir candidate kaydı, staging adresleri ve dış kanıt referanslarıyla tek komut çalıştırır. Araç; kaynak SHA, candidate digest, health/readiness, kimlik doğrulama, kalıcı storage, migration ledger, gerçek sağlayıcı smoke'u, yedek ve rollback hazırlığını fail-closed değerlendirir.

**Why this priority**: Repository testlerinin yeşil olması canlı ortamın hazır olduğunu kanıtlamıyor. Bu ayrım yapılmadan yeni ürün geliştirmek yanlış güven üretir.

**Independent Test**: Tüm bağımlılıklar sahte HTTP/komut adaptörleriyle verildiğinde araç başarılı rapor ve `0`; eksik dış kanıtta blocked rapor ve `2`; gerçek kontrolde hatada failed rapor ve `1` üretir.

**Acceptance Scenarios**:

1. **Given** exact current-main candidate ve tüm canlı kontroller geçiyor, **When** preflight çalışıyor, **Then** JSON ve Markdown raporları `overall: passed` olur ve çıkış kodu `0` döner.
2. **Given** candidate, secret veya dış kanıt eksik, **When** preflight çalışıyor, **Then** açık `blocked` kontrolü yazılır, hiçbir değer tahmin edilmez ve çıkış kodu `2` olur.
3. **Given** canlı uç beklenmeyen cevap veriyor, **When** preflight çalışıyor, **Then** başarısızlık raporu yine yazılır ve çıkış kodu `1` olur.

---

### User Story 2 - Kanıt paketini güvenle paylaş (Priority: P1)

Release sorumlusu makinece okunabilir JSON ile kısa Markdown özetini paylaşabilir. Rapor; token, DSN, servis anahtarı, öğrenci içeriği, prompt veya ham cevap gövdesi içermez ve kendisini promotion evidence olarak tanıtmaz.

**Why this priority**: Kanıt üretirken sır sızdırmak veya `staging-verified` iddiasını erken yapmak doğrudan güvenlik ve yönetişim kusurudur.

**Independent Test**: Sentinel secret değerleriyle üretilen bütün çıktılar taranır; hiçbir secret görülmez ve rapor türü `staging_preflight` kalır.

**Acceptance Scenarios**:

1. **Given** ortamda gerçek sır biçiminde sentinel değerler var, **When** başarılı veya başarısız rapor yazılıyor, **Then** rapor yalnız configured/boolean ve güvenli referans bilgisi içerir.
2. **Given** bazı kontroller çalıştırılmadı, **When** rapor yazılıyor, **Then** `not_run` ile açıkça listelenir ve genel durum başarılı olamaz.

---

### User Story 3 - UI dışından sınav ve kill switch atlanamasın (Priority: P1)

Test sorumlusu gerçek tarayıcı bağlamından ham sohbet POST'u göndererek aktif sınav kilidini ve operasyonel kill switch'i doğrular. Global kapatma UI'da sınav kilidi gibi yanlış adlandırılmaz.

**Why this priority**: Butonu gizlemek sunucu kapısı değildir. Tarayıcıdan ham istek, iki fail-closed kuralın gerçekten API'de uygulandığını kanıtlar.

**Independent Test**: Aktif sınavda ham POST `403 exam_in_progress`; yasak `mode: exam` isteği `422 validation_error`; kapalı feature flag'de availability `globally_disabled` ve POST `503 course_agent_disabled` döner.

**Acceptance Scenarios**:

1. **Given** öğrenci için aktif sınav var, **When** tarayıcı bağlamı doğrudan `/chat` çağırıyor, **Then** istek `403 exam_in_progress` ile reddedilir ve request ID döner.
2. **Given** course agent global olarak kapalı, **When** availability ve ham POST tarayıcıdan sınanıyor, **Then** UI bakım mesajı gösterir, besteci görünmez ve API `503 course_agent_disabled` döner.

### Edge Cases

- Candidate dosyası bozuk, promotion türünde veya checkout SHA ile uyuşmuyor.
- API URL'si HTTPS değil, timeout oluyor ya da readiness kısmi cevap veriyor.
- Uzak migration ledger yok, eksik, fazla veya yerel checksum ile uyumsuz.
- LLM smoke'u cache'den geliyor, atıfsız cevap veriyor veya source-bounded yanıt üretmiyor.
- Bucket public, dev-auth kabul ediliyor veya kill switch beklenen durumdan farklı.
- Rapor hedefi yazılamıyor; araç terminale secret dökmeden açık hata verir.

## Requirements

### Functional Requirements

- **FR-001**: Preflight mevcut `.release/evidence.schema.json` sözleşmesiyle candidate kaydını doğrulamalıdır.
- **FR-002**: Candidate source SHA checkout SHA ile, image digest ise candidate immutable digest'iyle eşleşmelidir.
- **FR-003**: Araç live ve ready uçlarını timeout ile çağırmalı; production guard, database, pgvector ve embedding durumlarını fail-closed değerlendirmelidir.
- **FR-004**: Anonim ve `dev:` kimliği reddedilmeli; staging JWT yalnız ortam değişkeninden okunmalıdır.
- **FR-005**: Storage bucket'ın varlığı ve private oluşu salt-okunur bir kontrolle doğrulanmalıdır.
- **FR-006**: Yerel migration envanteri sıralı, tekil ve SHA-256 bağlı olmalı; remote ledger ile tam eşleşme yoksa blocked/failed olmalıdır.
- **FR-007**: Gerçek sağlayıcı smoke'u cache dışı, atıflı ve kaynakla sınırlı yanıt göstermelidir.
- **FR-008**: Backup, rollback ve previous digest referansları eksikse araç başarılı sonuç üretememelidir.
- **FR-009**: Her zorunlu kontrol `passed`, `failed`, `blocked` veya `not_run` durumlarından birini taşımalıdır.
- **FR-010**: JSON ve Markdown başarısızlıkta da yazılmalı; `not_run` kontroller açık listelenmelidir.
- **FR-011**: Çıktılar secret, token, DSN, prompt, öğrenci içeriği veya ham provider cevabı içermemelidir.
- **FR-012**: Çıkış kodları `0=passed`, `1=failed`, `2=blocked` olmalıdır.
- **FR-013**: Rapor açıkça preflight olmalı ve promotion/staging-verified iddiası üretmemelidir.
- **FR-014**: Aktif sınav ham sohbet POST'u tarayıcı bağlamından `403 exam_in_progress` ile reddedilmelidir.
- **FR-015**: `mode: exam` ham POST'u `422 validation_error` ile reddedilmelidir.
- **FR-016**: Global kill switch availability'yi kapatmalı, provider çağrısından önce `503 course_agent_disabled` dönmeli ve UI bakım mesajı göstermelidir.
- **FR-017**: Yeni migration veya yeni runtime bağımlılığı eklenmemelidir.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Tam başarılı, blocked ve failed akışların her biri deterministik çıkış kodu ve iki rapor biçimi üretir.
- **SC-002**: Sentinel taraması, tüm test raporlarında `0` secret sızıntısı bulur.
- **SC-003**: Zorunlu kontrollerin `%100`'ü isimli durum ve güvenli gerekçe taşır; sessiz skip yoktur.
- **SC-004**: Üç tarayıcı güvenlik senaryosu exact HTTP status, hata kodu ve request ID ile kanıtlanır.
- **SC-005**: Mevcut API, web, OpenAPI ve migration sözleşmelerinde davranış dışı değişiklik olmaz.

## Assumptions

- Candidate artifact henüz yoksa ilk gerçek koşunun blocked olması doğru sonuçtur.
- Staging production guard'larıyla çalışır; `ENVIRONMENT=production`, dev-auth kapalı ve kalıcı storage zorunludur.
- Protected environment, OIDC, deploy ve gerçek secret kurulumu repo dışı işlemlerdir.
- İlk dilim yeni bir deploy workflow'u yazmaz ve production'a otomatik terfi yapmaz.
- Browser kanıtı CI'da ikinci, hafif bir API süreciyle kill switch kapalı olarak çalışabilir.

