# DOU-Synapse ajan ve beceri envanteri — 4 Eylül 2026

Kullanıcının “depoya önceden koyduğumuz 90'dan fazla ajan ve beceriler” kontrolü için salt okunur envanter çıkarıldı. İlk015 incelemesi salt okunurdu. 016 devamında mevcut becerilerin Codex karşılıkları hazırlandı; tarihsel tarama bulguları aşağıda korunur.

## 016 güncellemesi

Repo artık `.agents/skills/` altında 17 Codex karşılığı içeriyor; 3 DOU metni `.claude/skills` ile aynı güncel akışı kullanıyor. 14 Claude Speckit kaynağı aynen korundu. Eski uyumsuzluk/kurulum bulguları bu sürümdeki uyarlamanın gerekçesidir. Yeni paket 90+ ajan kütüphanesinin bulunduğu anlamına gelmez; küresel kurulum yapılmadı. [Kullanım ve doğrulama](agent-skills.md).

## İlk tarama sonucu

| Kaynak | Doğrulanan içerik | Durum |
|---|---|---|
| GitHub main ve 015 `.claude/skills/` | 17 SKILL.md: 14 Speckit + 3 DOU | Git'e kayıtlı; iki ağaçta birebir aynı |
| Eski ana checkout `feat/chat-socratic` | 14 Speckit | 3 DOU becerisi bu eski dalda yok |
| DOU-Synapse uzman ajan kataloğu | 0 | 47 ref/40 farklı HEAD ve 863 erişilebilir commit içinde bulunamadı |
| `~/.codex/skills/dou-synapse-*` | 9 yerel Codex becerisi | Sekizi önceki kurulum; completion-loop bu geliştirmede eklendi |
| `~/.claude/plugins` marketplace | 21 ajan tanımı + 3 yardımcı yönerge | Global dosyalar; aktif kurulum kanıtı bulunmadı |
| `~/.codex/plugins/**/agents/openai.yaml` | 44 arayüz/politika dosyası | Bağımsız ajan prompt kataloğu değil |

**90+ ajan paketi doğrulanamadı.** Bu, paketin hiçbir zaman başka konumda bulunmadığı iddiası değildir. İncelenen depo, erişilebilir geçmiş, çalışma ağaçları ve standart global/eklenti konumlarında bulunmadı. Paketin adı, eski bağlantısı veya kurulduğu klasör belirlenirse o kaynak ayrıca karşılaştırılabilir.

## Beceri grupları

- DOU: `dou-entegrasyon`, `dou-kanit`, `dou-kurulum`.
- Speckit: `speckit-analyze`, `speckit-checklist`, `speckit-clarify`, `speckit-constitution`, `speckit-implement`, `speckit-plan`, `speckit-specify`, `speckit-tasks`, `speckit-taskstoissues`.
- Speckit Git: `speckit-git-commit`, `speckit-git-feature`, `speckit-git-initialize`, `speckit-git-remote`, `speckit-git-validate`.

## Codex uyumluluğu

skill-installer listeleme aracı GitHub `muratcan-ates/DOU-Synapse`, `main`, `.claude/skills` yolunda aynı 17 beceriyi doğruladı. Araç bu adların Codex global kurulum dizininde kurulu olmadığını bildirdi; bu sonuç Claude'un repo içi becerilerinin kayıp olduğu anlamına gelmez.

17 dosyanın YAML başlığı ayrıştırıldı ve metindeki somut `.specify` dosya başvuruları mevcut. Codex skill-creator doğrulayıcısı 3 DOU becerisini kabul etti. 14 Speckit dosyası Claude'a özgü `compatibility`, `argument-hint`, `user-invocable` veya `disable-model-invocation` alanları nedeniyle bu doğrulayıcıdan doğrudan geçmiyor. Bu bir Claude çalışma hatası iddiası değildir; Codex'e taşıma için metadata ve komut/hook davranışı uyarlanmalıdır. `$ARGUMENTS` ve slash-hook yönergeleri de Codex araçlarıyla eşleştirilmeden otomatik çalıştırılmamalıdır.

Üç DOU becerisi `a8a8a365df64587dc9ae52a1ec3781a7596a236f` commit'inde eklenmiş. `dou-kurulum` ve `dou-entegrasyon` eski `dou-lead` klasörünü ve paylaşılan geliştirme veritabanını varsayıyor. Ortam dosyası kopyalama, paylaşılan DB'ye göç uygulama ve sabit preview araçları gibi adımlar mevcut izole çalışma düzenine doğrudan taşınamaz. `dou-kanit` de eski teslim/temizlik ve commit biçimi kuralları içeriyor. Bu içerikler mevcut kullanıcı yetkisinin veya güncel güvenlik sınırlarının yerine geçmez.

Codex'te kurulu 9 DOU becerisi: ai-sdlc, completion-loop, engineering-excellence, feature-delivery, product-strategy, product-ui, rag-evaluation, release-verification ve role-security. Yeni completion-loop yerel kurulumdadır; repo içinde paylaşılmış bir beceri paketi değildir. Yapısal doğrulaması ve bağımsız devam senaryosu denemesi tamamlandı; ayrıntı [beceri değerlendirmesi](../specs/015-completion-program/skill-evaluation.md).

## Ajan taramasının kapsamı

`.claude/agents`, `.codex/agents`, `.agents`, `agents`, `agency-agents` ve genel agent/agency dosya yolları tarandı. 863 erişilebilir commit'teki 230 genel eşleşme: 179 mevcut CourseGPT ajan özelliğinin kanıt/test/spec dosyası, 42 AGENTS.md talimat/backup yolu, 9 uygulama ajan modülü. Bunlar uzman ajan kütüphanesi değil. Çalışma ağaçlarında ignored/untracked katalog, Git'e kayıtlı symlink ve submodule bulunmadı. Uzak 5 dalın SHA'ları salt okunur sorguyla doğrulandı; fetch/merge yapılmadı.

Claude marketplace dağılımı: feature-dev 3, plugin-dev 3, pr-review-toolkit 6, code-modernization 5, agent-sdk-dev 2, hookify 1, code-simplifier 1. 21 tanımda 19 farklı ad var; code-reviewer ve code-simplifier iki pakette farklı içerikle bulunuyor. Birebir içerik kopyası yok. Ayrıca skill-creator'ın 3 yardımcı yönergesi var. Codex'in 44 openai.yaml dosyasında yalnız interface veya interface+policy metadata bulundu.

## Takip

1. 90+ ajan paketinin özgün kaynağı hâlâ bekleniyor.
2. Codex uyarlaması ve üç DOU yönergesinin taşınabilir hâle gelmesi 016 kapsamında tamamlandı; doğrulama kaydı specs/016-agent-skills/verification.md.
3. Repo içi paket ile 9 kişisel Codex becerisi ayrı tutuldu; otomatik süreç veya arka plan çalışma iddiası yok.
