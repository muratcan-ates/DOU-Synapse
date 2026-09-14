# L5 kimlik ve Storage doğrulama devri

Bu kayıt L5'in yerel kanıtını ve açık F6 kabulünü ayırır. Dal `018-l5-auth`, hedef `018-codex-production-line`, [taslak PR #29](https://github.com/muratcan-ates/DOU-Synapse/pull/29). Gerçek Supabase/Entra veya üretim kabulü verilmemiştir.

## Teslim edilen yerel kanıt

| İş | Ölçülen sonuç | Kayıt |
|---|---|---|
| F1 JWT | Gerçek HTTP'de negatif JWT ve başlangıç ayarları; tam yerel API paketi başarılı | [080-r2 dossier](../../.ai/changes/080-jwt-negative-r2.json) |
| F3 web oturumu | Kurulu SDK + sentetik taşıma, Web Lock mutasyonu, geç SDK olayları; web testleri ve production build başarılı | [081 kanıtı](../../.ai/evidence/081-web-auth-r1.json) |
| F4 indirme | Üyelik/sınav → belge-ders → nesne yolu → service_role imzası; üç ayrı kontrol mutasyonu yakalandı | [082 kanıtı](../../.ai/evidence/082-private-storage-r1.json) |
| F5 Storage RLS | Gerçek PG16 çekirdeği + sentetik Storage; read/insert/delete/update mutasyonları yakalandı | [083 kanıtı](../../.ai/evidence/083-storage-rls-evaluation-r1.json) |
| F2 hazırlık | Yalnız JWKS geçiş belgesi; Gün-1 HS256 değişmedi | [Güvenlik belgesi](../security.md#jwks-geçiş-hazırlığı-f2-uygulama-yok) |

F3 manuel yerel dev tarayıcı denemesi Ayşe/Burak giriş-çıkışı, sayfa yenileme, iki gerçek sekmede çıkış, oturum kapalıyken özel sayfanın reddi, jetonsuz callback ve doğrulama ekranını kapsadı. Açık/koyu tema ve 375 px genişlik görüldü. Bu gözlem tam Playwright, reduced-motion emülasyonu veya Supabase e-posta/tenant kabulü değildir. Kesilmiş F3 API tekrarları kanıtta korunur; daha sonraki F4/F5 tam yerel API paketlerinin başarısı bu kayıtları geriye dönük değiştirmez.

## F6 ön koşulları

13 Eylül 2026, 16:23:47 UTC tarihli [ön koşul kaydı](l5-auth-storage-preflight.json):

| Kontrol | Gerçek sonuç |
|---|---|
| `docker --version` | rc127; `command not found: docker` |
| `supabase --version` | rc127; `command not found: supabase` |
| `supabase/config.toml` | Yok |
| `/Applications/Docker.app` | Yok |

Mevcut `docker-compose.yml`, PostgreSQL + API/worker ve yerel dosya backend'i içindir; Supabase Auth/Storage yığını değildir. Docker/CLI ön koşulları yokken `supabase start` denenmedi ve F6 E2E tamamlanmış sayılmadı. Kurulum veya servis değişikliği yapılmadı.

## Açık kabul ve entegrasyon işleri

- **F6 yerel Supabase: `not-run`.** `supabase start` çalıştırılamadı; bu ön koşullar sağlanmadan PostgreSQL + sentetik Storage testi Supabase yığını kabulü sayılmaz.
- **F3/F6 gerçek proje: `not-run`.** Kullanıcı Supabase projesi/anahtarlarının henüz bulunmadığını bildirdi. Gerçek JWT, parola/reset/e-posta, refresh, Entra tenant, Storage signed URL/TTL/iptal ve hosted göç yetkileri ölçülmedi. Sır dosyası oluşturulmadı.
- **Göç sırası: ENGEL.** Taban dalda 0027/0028 bulunmuyor. Yalnız 0029 eklendi; izinli 0017/0021/0022/0023 boşluklarıyla göç denetimi rc1 döndü. Entegrasyon sorumlusu eksik şerit göçlerini birleştirip kapıyı yeniden çalıştırmalı; boş göç veya genişletilmiş allow-gap kullanılmadı.
- **Tam E2E: ENGEL/L1.** [F3 uzak işi](https://github.com/muratcan-ates/DOU-Synapse/actions/runs/34766528658/job/103749261497) `OWNED_E2E_FAILED` ile 902.943 saniyede tamamlanamadan kapandı. Artefakt `10321250051`, giriş ekranında “Oturum açma henüz yapılandırılmadı” durumunu ve giriş bekleyen testlerin zaman aşımını içeriyor. `scripts/run_owned_e2e.py` web ortamı izin listesi `NEXT_PUBLIC_DEV_AUTH` bayrağını taşımıyor; L1 izole sentetik `web_env` içine açık `true` iznini ekleyip tam paketi yeniden koşmalı. Yalnız workflow env eklemek yeterli değil. Üretim kapısı gevşetilmedi; L5 çalıştırıcı/workflow dosyasına dokunmadı.
- **Storage CI: L1.** F5 SQL temel ve mutasyon komutları CI'a eklenmeli; [yerel çalıştırma koşulları](../security.md#018-l5-kimlik-ve-private-storage-işletim-sınırları) mevcut Storage şemasını koruyan ayrı veritabanı şartını açıklar.
- **Aggregate dossier: entegrasyon.** `refresh_aggregate_dossier.py` çalıştırılmadı. Yerel ebeveyn denetimleri başarılıdır; “Govern reviewed AI diff” için toplayıcı kaydı entegrasyon sorumlusu yazmalıdır. İnsan terfi onayları bekliyor ve PR taslak kalıyor.

## Değişmeyen güvenlik kararları

HS256 Gün-1'de kalır; rol e-posta veya metadata'dan türetilmez. API üyeliği ve PostgreSQL RLS ayrı katmanlardır. `service_role` Storage RLS'i atlar; imzadan önce API yetkisi zorunludur. İmzalı URL 60 saniyelik bearer yetkisidir; üyelik iptali veya yeni sınav, verilmiş URL'yi anında geçersiz kılıyor sayılmaz. Yalnız 0029 göçü ve 080–083 L5 dossier numaraları kullanıldı; bağımlılık/lockfile, geçmiş göç, assessment/retrieval uygulama modülleri ve workflow/checker yüzeyleri değiştirilmedi.
