# 015 yerel adayın yeniden hazırlanması

Önceki aday `4f89369a9bcf380d5b671f0ffd323b3ee16396e6` (`015-completion-program`) değiştirilmeden korunmuştur. Kesin `4e948d5fc5ec42f447838cb1e95e22f5881cb0fa` → önceki aday kontrolü `AI_SDLC_CHECK=FAIL`, `HUMAN_ANCHOR:015-completion-program-r1:human_anchor_ref` sonucu verdi. İnsan kabulünün beklediğini anlatan serbest metin, izlenen dosya bağlantısı gereken alana yazılmıştı. Bu, geçmiş adayı geçerli kılan bir düzeltme değildir.

Yeni `015-completion-candidate` dalı aynı014 tabanından hazırlanmıştır. Önceki adayın `.ai/` dışındaki 698 izlenen dosyası bayt düzeyinde aynı alınmıştır. Eski015 denetim kaydı yeni adayın yetkilendiren kaydı olarak kullanılmaz; eski dalda ve SHA'da aynen kalır. 013/014 denetim geçmişi korunur. Yeni kayıt ayrı `completion-candidate` köküdür; tarih değiştirme, karantina veya kural gevşetme uygulanmamıştır.

Eski dossier SHA-256: `eec924e2a5330db3398d40a8c8cf796110bd0b63043b1928cfb2e2cb5dc880c7`. Eski evidence SHA-256: `2849e7e4609555e61630bfd4537dab865b5a7e100708a8e3d692156af5b6aa43`. Eski ürün dosyaları için sıralı path/SHA-256 manifest özeti: `a4ffbf3244fdcd1be9c72ce84bbfad8066a08d6d33638fe43a547e122a6747a4`.

Yeni kaydın insan kabulü başvurusu `evaluation/acceptance/assessment_cases.json` dosyasıdır. Bu dosya hazırlanmış, henüz insan tarafından puanlanmamış kabul taslağıdır. İnsan değerlendirmesi, gerçek model kalitesi ve yayımlama onayı beklemektedir; bağlantının geçerli olması bu işleri tamamlamaz.

Önceki aday için koşulmuş1154 API,421 arayüz,38 tarayıcı ve76 yönetişim birim testi sonuçları yeni adayda yeniden koşulmuş sayılmaz. Yeni rapor bunları eski aday ve log özetlerine bağlı devralınan kanıt olarak taşır. Yeni adayın kendi kontrolü, ürün dosyalarının birebir eşitliği ve kesin base/HEAD denetimidir. Yalnız denetim/belgeleme değiştiği için aynı uygulama testleri tekrarlanmadı.

Yeni adayın kesin denetim çıktısı commit sonrası teslim raporuna eklenir.014→yeni aday başarısı main→aday onayı, insan incelemesi, gerçek sağlayıcı kalitesi veya canlı yayın sayılmaz. Main hedefli birleşim, bütün013+014+015 farkı için ayrıca kesin aday kaydı ve CI gerektirir.
