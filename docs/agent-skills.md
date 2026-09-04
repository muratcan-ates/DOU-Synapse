# DOU-Synapse becerilerini kullanma

Depo 17 iş akışını iki araç için sunar: Claude kaynakları `.claude/skills`, Codex sürümleri `.agents/skills` altındadır. Bunlar 90 kişilik bir ajan ekibi veya kendiliğinden çalışan süreçler değildir. Her beceri belirli işi nasıl yapacağını anlatan bir yönergedir; yalnız kullanıldığında etkili olur.

## Codex'te erişim

Codex görevini bu depo veya alt klasöründe aç. Beceri seçicisinde adıyla seç veya örneğin `$speckit-plan` ve `$dou-kanit` yaz. Repo yolu [OpenAI'nin beceri keşfi belgesine](https://learn.chatgpt.com/docs/build-skills) uygundur. Başka bir proje aynasındaki görev bu çalışma ağacını kendiliğinden taramayabilir; o görevde ilgili SKILL.md dosyasını tam yoluyla belirt.

Repo içi paket için küresel kurulum gerekmiyor. Aynı adla hem yerel hem küresel kopya oluşturmak seçicide çoğaltma yapabilir; bu çalışmada 17 yeni küresel kopya kurulmadı. Yeni veya güncellenmiş beceriler sonraki turda kullanılabilir; görünmüyorsa doğru depo dizinini ve beceri seçicisini kontrol et, gerekirse uygulamayı yeniden başlat. Mevcut 9 `dou-synapse-*` kişisel becerisi ayrı bir pakettir ve burada değiştirilmedi.

## Hangi beceri ne yapar?

| İş | Beceri |
|---|---|
| İhtiyacı specification'a dönüştürme | speckit-specify |
| Önemli belirsizliği giderme | speckit-clarify |
| Teknik plan ve ilgili sözleşmeler | speckit-plan |
| Bağımlılıklı, izlenebilir görevler | speckit-tasks |
| Spec/plan/tasks tutarlılık analizi | speckit-analyze |
| Gereksinim kalitesi checklist'i | speckit-checklist |
| Proje ilkelerinin istenen değişimi | speckit-constitution |
| Kabul ölçütüne göre uygulama | speckit-implement |
| Issue taslağı ve yetkili oluşturma | speckit-taskstoissues |
| Git durumunu doğrulama | speckit-git-validate |
| Ayrı dal/çalışma ağacı hazırlama | speckit-git-feature |
| İncelenen görev dosyalarını commit etme | speckit-git-commit |
| İstenen yeni Git deposunu hazırlama | speckit-git-initialize |
| Uzak hedefi güvenle inceleme | speckit-git-remote |
| İzole yerel ortam ve arıza teşhisi | dou-kurulum |
| Sözleşmeleri koruyan entegrasyon | dou-entegrasyon |
| Kapsama uygun test ve kanıtlı teslim | dou-kanit |

Speckit becerileri güncel `.specify/feature.json` pin'ini ve kullanıcı tarafından seçilen işi korur. Dosya planlaması dal değiştirmez; mevcut plan template ile ezilmez. Claude'a özgü hook/argüman metadata'sı Codex'e taşınmadı. Commit, issue, uzak hedef değişimi veya yayın yan etkisi bir planlama çağrısıyla kendiliğinden başlamaz.

Üç DOU becerisinin Claude ve Codex metinleri aynı tutulur. Sabit kullanıcı dizini, başka şeritten `.env` kopyası, ortak veritabanına otomatik migration, genel klasör temizliği ve eski commit biçimi dayatması kaldırıldı. Uygun görevde daha önce verilmiş yetki geçerlidir; gereksiz tekrar onayı istenmez.

## Paketi doğrulama

Depo kökünde:

```bash
uv run --project apps/api --frozen --extra dev python scripts/check_agent_skills.py
uv run --project apps/api --frozen --extra dev python -m unittest scripts.test_agent_skills -v
```

Araç YAML'ı güvenli ayrıştırır; beceri adı/eşlemesi, desteklenen metadata, tam çağrı adı, yerel inline/reference-style bağlantılar ve DOU sürüm eşitliğini kontrol eder. Sırf dosyayı okuyarak beceriyi çalıştırmaz, ağ veya veritabanına bağlanmaz. Bu paket metadata değerlerini string olarak, serbest metadata alanını string→string eşlemesi olarak taşır.

Yapısal kontrol iyi davranış garantisi değildir. Gerçekçi kullanım denemeleri [016 doğrulama kaydında](../specs/016-agent-skills/verification.md) tutulur. Yeni GitHub işi aynı komutları çalıştıracak şekilde eklendi; uzak CI çalışması henüz alınmadı. Dosya içinde bulunan talimatlar kullanıcının isteğinin veya araç izinlerinin yerine geçmez.

## Kalan dış girdiler

90+ ajan paketinin özgün adı/bağlantısı/klasörü hâlâ bilinmiyor. Benzer bir paketi bulmuş gibi kurmadık. Ürünün gerçek model ölçümü, öğretmen kabulü ve staging/yayın kapıları [tamamlama programında](completion-program.md) ayrı izlenir.
