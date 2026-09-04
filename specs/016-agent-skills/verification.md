# 016 doğrulama kaydı

Dal: 016-agent-skills. Temel: `ed6103fbe53be3888252074db0a722cfe1be617c`. Kanıt yalnız bu yerel beceri/araç/belge değişikliğine aittir. Ürün dosyaları, API testleri, evaluation, migration, .ai kayıtları ve 14 Claude Speckit kaynağı temel ile aynıdır. Çalışma ağacına özel Python ortamının bu ağacın app paketini yüklediği doğrulandı.

## Koşulan kontroller

| Kontrol | Sonuç | Kanıt |
|---|---|---|
| skill-creator yapısal doğrulaması | 17/17 geçti | evidence/creator-validation.json |
| Repo paketi ve yerel bağlantılar | 17 Claude / 17 Codex, 73 bağlantı geçti | evidence/package.json |
| Doğrulayıcı karşı testleri | 17 geçti | evidence/checker-tests.log |
| Önceki inceleme bulgularının bağımsız tekrarı | 8/8 geçti; çökme/dosya mutasyonu yok | evidence/boundary-review.json |
| Gerçek script sözleşmesi denemesi | 5 geçici depo kontrolü geçti | evidence/script-contract-smoke.json |
| Bağımsız beceri kullanımı | 4 senaryo uygulandı; sahiplik, pin, plan kararı ve tamamlanmış görev korundu | evidence/forward-trial.md ve forward-scope.json |
| Ruff ve biçim | İki yeni araç temiz | Proje API Ruff ayarlarıyla kontrol |
| Yeni CI yapılandırması | YAML geçerli; action SHA'ları sabit; contents:read, credential persistence kapalı | .github/workflows/agent-skills.yml |
| Tam depo belge ölçümü | Geçti | evidence/docs-check.log |
| Çalışma ağacı/ürün kapsamı | Uygulama, test, AI ve migration farkı yok; 14 Claude kaynak aynı | Tam base farkı ve git diff --check |

Yapı doğrulayıcısı duplicate YAML/ad, yanlış metadata tipi ve çağrı adı, eksik eşleme, bozuk inline/reference-style bağlantı, dış dosya/symlink, NUL yol ve aşırı derin YAML durumlarını kontrollü hata olarak yakalar. Bu sınırlar karşı testlerle ve ayrı inceleyicinin geçici fixture'larıyla doğrulandı. Beceri anlamının tamamını bir regex/linter'ın doğruladığı iddia edilmez.

Bağımsız denemede dar fixture tam evaluation ağacını içermediğinden genel belge kapısı koşulamadı; bu sonuç başarılı sayılmadı. Tam 16 çalışma ağacındaki ayrı belge kapısı geçti. İlk template resolver denemesinde eksik kök argümanı görüldü; dört ilgili beceri fonksiyonun iki argümanını açıkça belirtmek üzere düzeltildi. Sonraki doğru çağrı geçerli template'i buldu.

## Tekrarlama

```bash
uv run --project apps/api --frozen --extra dev python scripts/check_agent_skills.py --json
uv run --project apps/api --frozen --extra dev python -m unittest scripts.test_agent_skills -v
uv run --project apps/api --frozen --extra dev ruff check --config apps/api/pyproject.toml scripts/check_agent_skills.py scripts/test_agent_skills.py
uv run --project apps/api --frozen --extra dev ruff format --check --config apps/api/pyproject.toml scripts/check_agent_skills.py scripts/test_agent_skills.py
```

Beceri oluşturucu doğrulayıcısı bu makinede sistem becerisinin scripts/quick_validate.py dosyasıyla çalıştırıldı; tekrar için aynı araç kurulu olmalı. CI ise yalnız repo içi doğrulayıcı ve mevcut kilitli Python bağımlılıklarını kullanır. Gerçek ağ çağrısı veya test veritabanı gerekmez.

## Sınırlar ve kalan kapılar

API/tarayıcı paketi tekrar koşulmadı; önceki 1154/421/38 sonuçları 016 ürünü yeniden ölçülmüş gibi gösterilmez. Belge aracı web kütüphane testlerini çalıştırır; API ve tarayıcı testlerini yalnız listeler. GitHub CI henüz uzak ortamda çalışmadı. Bu çalışma Codex uygulamasının yeni becerileri aynı görevde otomatik keşfettiğini kanıtlamaz; repo kapsamı doğru çalışma dizinini gerektirir.

Gerçek model, öğretmen/insan kabulü, main birleşimi ve staging/canlı yayın hâlâ ayrı girdilerdir. 90+ ajan paketi kaynağı bulunmuş değildir. Kesin commit ve base→HEAD AI denetimi commit sonrası teslim kaydına eklenecek.
