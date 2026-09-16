# Gelişim günlüğü

Projenin 2 Ağustos 2026'dan sunuma kadar nasıl evrildiği, tarihsel ölçüm kayıtları, şema
yolculuğu ve yol boyunca bulunup kapatılan gerçek kusurlar.

Güncel ölçümler [README](../README.md#ölçülmüş-kanıt) içindedir; **bu dosya tarihsel
kayıttır** — buradaki sayılar alındıkları tarihin ölçümüdür, bugünkü değeri değil.

---

## Tarihsel kanıt koşuları

8 Eylül 2026 yerel OPS turunda 71 geçti; yeni 3 vakanın 1’i gerçek yetkili API yanıtı, 2’si kontrollü dependency yanıtını gösteren UI sözleşmesidir. c45 hosted 68 sonucu yeni kaynağı kapsamaz. [018 doğrulaması](../specs/018-codex-production-line/verification.md) <!-- docs-check: tarihsel 71 · 2026-09-08 -->

005'in 11 Ağustos 2026 tarihli yerel kanıt koşusu ayrıca şunları kaydeder:

- 92 backend dosyasında mypy sonucu; <!-- docs-check: tarihsel 92 · 2026-08-11 -->
- frontend typecheck, açık/koyu tema kontrast kapısı ve production build;
- Ruff;
- 50 OpenAPI yolu ve 119 şema; <!-- docs-check: tarihsel 50 · 2026-08-11 --><!-- docs-check: tarihsel 119 · 2026-08-11 -->
- persona alanlarının istemciden gönderilmesinin reddi;
- cross-course quota yarışları, cache izolasyonu ve exam/export yarış korumaları;
- gerçek API’ye karşı 35/35 seri tarayıcı akışı, teardown sonrası ders/audit kalıntısı <!-- docs-check: tarihsel 35 · 2026-08-11 -->
  <code>0/0</code> ve sabit UUID’li <code>COME 331</code> koruma kanıtı; <!-- docs-check: tarihsel 0 · 2026-08-11 -->
- 8 kapalı sınır, 3 kalıcı kota iddiası ve 11/11 kasıtlı DB/RLS mutasyonunun <!-- docs-check: tarihsel 8 · 2026-08-11 --><!-- docs-check: tarihsel 3 · 2026-08-11 --><!-- docs-check: tarihsel 11 · 2026-08-11 -->
  beklenen sızıntıyı görünür kılması.

Bu kanıt **yerel PostgreSQL + deterministik fake provider** ortamındadır. Gerçek provider,
staging, canary veya production kanıtı değildir.

15 Ağustos entegrasyon adayı ayrıca 894/894 backend, 349/349 frontend (30 test
dosyası), 36/36 seri gerçek-API Playwright, 12/12 uygulama mutasyonu ve 7/7
offline/fake RAG mekanik vakasını geçti. İki-worker yerel yükte kota overshoot 0,
aktif reservation tepesi 1, cache-miss p95 1659.16 ms ve cache-hit p95 493.73 ms
ölçüldü. Yerel kayıtlar final R4 dossier tarafından exact candidate'a bağlanıp
yerel no-ref adayda doğrulandı. Bu, gerçek final commit/PR CI gözlemi veya gerçek
provider/staging kanıtı değildir; bu kapılar geçmeden production iddiası kurulmaz.

### Migration yolculuğu

<code>0001,0002,0003,0004,0005,0006,0007,0008,0009,0010,0011,0012,0013,0014,0015,0016,0018,0019,0020,0024,0025,0026,0027,0029</code> <!-- docs-check: migrations.list = 0001,0002,0003,0004,0005,0006,0007,0008,0009,0010,0011,0012,0013,0014,0015,0016,0018,0019,0020,0024,0025,0026,0027,0029 -->

| Migration | Ürüne eklediği katman |
|---|---|
| 0001 | Çekirdek ders, üyelik, belge/chunk, RLS ve request-scoped kullanıcı |
| 0002 | Supabase Auth köprüsü |
| 0003 | Sohbet oturumları, mesajlar, cache ve request log |
| 0004 | Konu, soru, sınav, cevap ve mastery |
| 0005 | Mahremiyetli analitik |
| 0006 | Embedding provenance |
| 0007 | Dar soru silme ve sınav grant’leri |
| 0008 | Sürümlü sınav blueprint’i |
| 0009 | Ders bazlı AI politikası |
| 0010 | Ingestion retry zamanlaması |
| 0011 | Pagination indeksleri |
| 0012 | KVKK/veri hakları |
| 0013 | AI sohbet geri bildirimi ve paylaşım onayı |
| 0014 | Platform-admin konsolu ve audit |
| 0015 | Rol farkındalıklı ajan, audience izolasyonu ve atomik AI kotaları |
| 0016 | API sözleşmesine platform-admin erişimi |
| 0018 | Eğitmen soru yazımı ve öğrenme çıktısı sınıflandırması |
| 0019 | Öğrenci sınav süresi projeksiyonu |
| 0020 | Ders politikası denetim kaydının cascade yaşam döngüsü |
| 0024 | Sohbet silme kapsam sürümü ve bekleyen yazımın engellenmesi |
| 0025 | PostgreSQL ortak istek politikası/kota pencereleri ve dar SQL işlevleri |
| 0026 | Sonlu iş claim/lease, kaynak revizyonu ve eski writer engeli |

## Gelişim yolculuğu

### 1. 2 Ağustos — fikir depoya dönüştü

İlk commit proje iskeletini ve MIT lisansını kurdu. Henüz “ürün” iddiası yoktu; amaç
hocanın CourseGPT taslağını izlenebilir bir mühendislik çalışmasına çevirmekti.

### 2. 4 Ağustos — mimari ve güvenli çekirdek

Üç haftalık plan, mimari kararlar, FastAPI, PostgreSQL/pgvector, ilk CI ve ders bazlı
iki katmanlı izolasyon geldi. <code>0001</code>, request-scoped kullanıcı bağlamı,
uygulama rolleri ve fail-closed RLS’in temelini attı.

**Öğrenilen:** Yetki yalnız frontend sekmesi veya API if’i olamaz; veritabanı ikinci
savunma katmanı olmalıdır.

### 3. 4–5 Ağustos — materyal aranabilir öğrenme tabanına dönüştü

Dosya doğrulama, parser, sayfa/slayt koruyan chunking, worker, embedding ve ilk
Next.js ders ekranları eklendi. Ardından Speckit, proje anayasası ve
<code>001-course-assistant-mvp</code> ile geliştirme “önce kod”dan “önce sözleşme ve
kabul kriteri” modeline geçti.

**Öğrenilen:** Atıf kalitesi üretim sonunda eklenen bir metin değil, ingestion sırasında
korunan provenance’ın sonucudur.

### 4. 6–9 Ağustos — chatbot’tan tam öğrenme döngüsüne

Auth köprüsü, sohbet/cache/log, soru/sınav/mastery, analitik, embedding provenance ve dar
grant’ler geldi. Retrieval, generation ve Sokratik akış birleştirildi. Soru üretimi,
öğretmen onayı, server-timed sınav, grading ve “Neden yanlış?” aynı ürün döngüsüne
bağlandı. Gold set, holdout ve RLS mutasyon kanıtları eklendi.

**Dönüm noktası:** Ürün artık yalnız soru cevaplayan bir bot değildi; eğitmenin
materyali yüklediği, soruyu onayladığı, öğrencinin çalıştığı ve sonucun ölçüldüğü
kapalı bir öğrenme çevrimiydi.

### 5. 9–10 Ağustos — demo varsayımları production-hardening’e dönüştü

<code>002-production-hardening</code> şu gerçek kusurları görünür kıldı:

- sınav yardımı yalnız UI/mod ile değil, aktif oturum durumuyla kilitlenmeli;
- ikinci sekme ve doğrudan API yolu aynı sınırdan geçmeli;
- senkron parsing/embedding event loop’u kilitlememeli;
- embedding hazırlığı readiness’ten ayrılmalı;
- pahalı üretim uçlarında hız ve eşzamanlılık sınırı olmalı;
- belgelerdeki sayılar elle değil kaynak koddan ölçülmeli.

Bu dalda <code>0008–0013</code> ile blueprint, ders AI politikası, retry, pagination,
KVKK hakları ve consent-based feedback eklendi.

### 6. 10 Ağustos — uygulama gerçek bir portala dönüştü

<code>003-product-portal</code>, ürüne dashboard, profil, hesap/veri hakları ve ayrı
Bilgi İşlem paneli getirdi. <code>0014</code>, platform admini ders eğitmenliğinden
ayırdı; salt okunur, içeriksiz ve audit edilebilir operasyon yüzeyi kurdu.

**Öğrenilen:** Admin observability, öğrenci sohbetini veya akademik cevabı görme yetkisi
anlamına gelmez.

### 7. 11 Ağustos — doğrulanmış baseline main’e ulaştı

PR #4, production-hardening ve portalı <code>origin/main</code> dalına
<code>2c17886</code> ucu olarak taşıdı. Bu; runtime, security, reliability,
modularizasyon, docs gate, E2E ve RLS çalışmalarının birleşmiş repository baseline’ıdır.

Bu adım **canlı production deploy** değildir.

### 8. 11 Ağustos — AI-SDLC ve engineering governance

<code>004-ai-sdlc-excellence</code> dalında:

- AI artifact policy/schema/dossier;
- AI-sensitive diff gate;
- CODEOWNERS, PR şablonu ve dependency/security workflow’ları;
- release evidence doğrulaması;
- build-once/promote-by-digest ADR;
- SLO, incident response ve release/rollback belgeleri

hazırlandı. Dal uzak repoya gönderildi ancak main’e birleşmedi. Canlı ruleset,
protected environment ve release gözlemi hâlâ dış doğrulama gerektirir.

### 9. 11 Ağustos — rol farkındalıklı ders ajanı

<code>005-role-aware-course-agent</code>:

- öğrenci için Ders Koçu;
- eğitmen için Eğitmen Asistanı;
- immutable audience ve persona spoof reddi;
- öğrenci/eğitmen cache izolasyonu;
- atomik kullanıcı/ders/platform token rezervasyonu;
- hard cap, concurrency, output limit ve kill switch;
- exam/chat/export yarış kilitleri;
- içeriksiz guard ledger;
- native course-assistant UI

ekledi. Dal uzak repoya gönderildi fakat PR/CI/main birleşmesi açık.

**Öğrenilen:** Bir eğitim ajanının değeri “daha otonom” olmasından değil, yetkisi,
kaynağı, maliyeti ve pedagojik davranışının sınırlarının görünür olmasından gelir.

### 10. 11 Ağustos — AI slop’tan uzak ürün tasarımı

<code>design/product-ui-refresh</code> adayı giriş, AppShell, dashboard,
ders ana sayfası, profil ve admin yüzeylerini daha editoryal bir akademik stüdyoya
dönüştürdü. Tek kırmızı aksan, daha net tipografik hiyerarşi, düz veri rayları,
responsive/dark-mode davranışı ve dürüst durum dili kullanıldı.

11 Ağustos adayında 325 frontend testi, typecheck, açık/koyu tema kontrast kontrolü ve <!-- docs-check: tarihsel 325 · 2026-08-11 -->
production build geçti. Benzersiz PostgreSQL ile gerçek API’ye karşı seri Playwright
paketi 35/35 geçti; ders/audit kalıntısı 0/0 ölçüldü. <!-- docs-check: tarihsel 35 · 2026-08-11 --><!-- docs-check: tarihsel 0 · 2026-08-11 --> Manuel ekran okuyucu ve
<code>prefers-reduced-motion</code> gözlemi ile bütün uygulama-katmanı mutasyon matrisi
ayrı kapılar olarak açık tutuldu.

### 11. 14–15 Eylül — gerçek modelle çalışan sisteme

Ağustos'ta altyapı ve arayüz kuruldu; Eylül'ün iki günü sistemi **gerçek modelle
çalıştırmaya** ve kanıtlamaya gitti.

**Gerçek sağlayıcı bağlandı.** Demo yığını sahte sağlayıcıdan gerçek Groq'a
(`openai/gpt-oss-120b`) geçti. Kapsam dışı ret, Sokratik merdiven ve atıflı cevap tek tek
gerçek modelle doğrulandı. Sahnede sorulacak 16 soru ölçülüp sabitlendi ve
`answer_cache`'e yazıldı — bu sorular modele hiç gitmediği için hem jeton harcamıyor hem de
ağ kesilse bile geliyor (Plan C).

**Kampüs arayüzü birleşti.** Sinaps kapakları, erişilebilirlik sağlayıcısı, hızlı geçiş ve
ayarlar/çalışma sayfaları ürüne girdi. Birleşmede tek istisna yapıldı: tasarım turu mobil
gezinmeyi DOM'un sonuna almıştı; `fixed` konumlandığı için görünüm aynı kalıyor ama klavye
kullanıcısı ana menüye ancak bütün sayfayı geçerek ulaşıyordu. Geri taşındı ve gerçek
tarayıcıyla ölçüldü: **4 sekme** (regresyonda 30+ sekmede ulaşılamıyordu), odak halkası
`2px solid`, 375×812'de yatay taşma yok.

**İki güvenlik açığı kapatıldı.** Soru havuzu, öğrenciye her sorunun kaynak pasajından 320
karakter veriyordu — yürüyen sınavdaki öğrenci tek istekle kâğıdındaki her sorunun kaynağını
okuyabiliyordu. Öğrenci projeksiyonu artık yalnız dosya adı ve konum taşıyor. Ayrıca sohbet
oturumu sahipliği yalnız RLS'e bağlıydı; depo "iki bağımsız katman" doktrinini yazılı ilan
ederken sohbet yolunda ikinci katman yoktu. Üç yerde eklendi — biri yazma yolu.

**Taranmış ve el yazısı materyal okunur oldu.** Gerçek bir el yazısı ders notu (tablet
üzerine, matematik notasyonu ve çizimlerle) yüklendiğinde ayrıştırıcı doğru olarak "metin
yok" diyordu ama üç kez boşuna deniyor ve "Lütfen yeniden deneyin" yazıyordu. İçerik hatası
artık kalıcı sayılıyor; metinsiz sayfalar görsel modelle transkribe ediliyor, düşük güvenli
sayfa atılıyor, her parça "AI okuması" köken etiketi taşıyor. Ölçüldü: 4 sayfa, atılan
sayfa 0, 5828 karakter.

**Pedagojik filtre güçlendi.** Uçtan uca provada görüldü ki teşhis kademesinde model, soru
sormadan önce cevabı düzyazıyla anlatıyor; mevcut dedektörler bunu göremiyordu çünkü kod,
adım ya da "cevap:" kalıbı yoktu. Yeni `exposition` dedektörü kalıp değil **örtüşme**
ölçüyor: soru cümleleri hariç, düz cümlelerin kaynakla örtüşmesi yarıyı geçerse yanıt
bloklanıp deterministik şablon ipucuna düşülüyor.

**Uçtan uca prova.** 15 Eylül sabahı sıfırdan yeni ders açılıp hiç indekslenmemiş belge
yüklenerek gerçek tarayıcıda tek oturumda koşuldu: **10/10 adım geçti.**

**İki çalışma özelliği eklendi (15 Eylül öğleden sonra).** *Hızlı tekrar*: planın "onaylı havuzu
kart yap" tasarımı uygulanamadı — öğrenciye giden havuz cevap anahtarını taşımıyor ve bu bir
sınav bütünlüğü kararı; deste bu yüzden öğrencinin kendi bitirdiği alıştırmadan kuruldu ve backend
hiç değişmedi. *Kavram haritası*: materyalden 40 terim, 60 bağ, model çağrısı yok. Aynı gün ölçülen
bir ders daha: sahne sorularının cevap önbelleği korpus revizyonuna bağlı; sabah bir belge yeniden
indekslenince gece ısıtılan 13 satır ıskaladı ve akşam provası gerçek modele gitti. Isıtma betiği
(`scripts/demo/onbellek_isit.py`) ve "ısıtmadan sonra derse belge yüklenmez" kuralı bundan doğdu.

## Yol boyunca bulunan ve kapatılan gerçek kusurlar

| Kusur | Nasıl bulundu? | Kalıcı ders |
|---|---|---|
| RLS mastery/answer izolasyon açığı | Temiz DB’de saldırı + mutasyon | “Policy var” değil, policy kaldırılınca test kırmızı mı? |
| GitHub Actions hiç job başlatmıyordu | İlk gerçek CI incelemesi | Yerel yeşil, CI’ın çalıştığını kanıtlamaz |
| Kurulum yeni migration’ları atlıyordu | Sıfırdan kurulum | Migration’ları tek tek belgelemek yerine sıralı glob uygula |
| Aktif sınavda ikinci sekmeden sohbet | Gerçek kullanıcı akışı | Exam integrity bir UI değil, state/race problemidir |
| Sync ONNX embedding event loop’u donduruyordu | Runtime ölçümü | CPU işini async fonksiyon içinde çağırmak onu async yapmaz |
| JWT issuer env adı sessizce yutuluyordu | Config-kod karşılaştırması | Örnek env ile Settings sözleşmesi test edilmelidir |
| GET retry ve timeout eksikti | Frontend reliability turu | POST otomatik retry edilmez; request ID görünür olmalıdır |
| E2E verisi birikiyor ve paylaşılan DB’yi bozuyordu | Seri/paralel test farkı | Run-scoped veri + fail-closed cleanup gerekir |
| Test DB kimliği CI ile fixture’da ayrışıyordu | Draft PR CI | DB’yi kuran ve kullanan süreç aynı identity’yi paylaşmalı |
| ONNX symlink/hardlink imajda reddediliyordu | Docker/CI kapısı | “Gerçek dosya” tek bağlantılı inode sözleşmesidir |
| Belgelerde farklı test sayıları vardı | Kod-belge karşılaştırması | <code>docs_check</code> sayıların kaynağını komut yapar |
| Admin metriği özel veriyi eşleyebilirdi | Adversarial security review | Operasyon paneli aggregate ve içeriksiz olmalıdır |
| Chat finalizasyonu sınav başlangıcıyla yarışabiliyordu | Forced interleaving review | Entry check yetmez; paylaşılan DB kilidi gerekir |
| KVKK export eski cevapları sınavda sızdırabiliyordu | Yan yol tehdit analizi | Güvenlik sınırı bütün veri çıkışlarını kapsamalıdır |

