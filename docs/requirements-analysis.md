# DOU-Synapse — Gereksinim Analizi Raporu (v2)

**Proje:** CourseGPT — Yapay Zekâ Destekli Kişiselleştirilmiş Ders ve Sınav Asistanı
**Ders:** COME 491/492 Bitirme Projesi · Doğuş Üniversitesi · Danışman: Yasemin Karagül
**Takım:** Muratcan Ateş (lead, frontend) · Eren Onur (backend/RAG + guardrail) · Metehan (assessment + ölçüm) · Dursun Berkay Özgür · Burhan Şener Şenkal
**Sürüm:** v2 — 14 Eylül 2026 (v1: 6 Ağustos 2026) · **Sunum:** 16 Eylül 2026
**Tam gereksinim metni:** `specs/001-course-assistant-mvp/spec.md` ve sonraki spec dizinleri (bu rapor onların akademik özetidir)

Danışmanın 6 Ağustos toplantısındaki isteği bu sürümün çerçevesidir: *fonksiyonel
gereksinimler, kullanım senaryoları ve arayüzler; fonksiyonel olmayan gereksinimler gerekmez.*
Buna göre §2.4 (kullanım senaryoları), §2.5 (arayüzler) ve §3.1 (yapay zekânın üç rolü) yeni;
§5 yalnız kayıt amacıyla kısaltılmış hâlde duruyor.

---

## 1. Giriş

### 1.1 Amaç

Bu belge, danışmanın CourseGPT proje taslağındaki (27 Temmuz e-postası) ve 6 Ağustos
toplantısındaki beklentileri doğrulanabilir sistem gereksinimlerine dönüştürür. Her taslak
maddesi numaralı bir fonksiyonel gereksinime (FR) izlenir; her başarı hedefi ölçülebilir bir
kabul kriterine (SC) bağlanır.

### 1.2 Problem tanımı

Öğrenciler sınava hazırlanırken genel amaçlı yapay zekâ araçlarına yöneliyor; bu araçlar
(1) ders müfredatı dışına çıkıyor, (2) kaynak göstermiyor, (3) ödev sorularının cevabını
doğrudan vererek öğrenmeyi zedeliyor. Literatürde bu üçüncü problem ölçülmüştür: Harvard'ın
CS50 ders asistanı değerlendirmesinde yanıtların %22'sinde öğrenciye doğrudan çalışan kod
sızdırıldığı raporlanmıştır (Liu vd., 2025; bkz. `docs/references.md` A1).

### 1.3 Çözüm yaklaşımı

Eğitmenin yüklediği materyalle **sınırlı** bir RAG (Retrieval-Augmented Generation)
asistanı. Ayırt edici ilke: **kaynak yoksa cevap yoktur** — her akademik cevap, gerçekten
getirilmiş bir materyal parçasına mekanik olarak doğrulanan atıfla sunulur; kanıt
bulunamazsa sistem cevap üretmek yerine bunu açıkça söyler.

### 1.4 Tanımlar

| Terim | Anlam |
|---|---|
| Chunk / parça | Materyalden çıkarılan, sayfa/slayt numarası taşıyan metin birimi |
| Retrieval | Soruyla ilgili parçaların hibrit aramayla (anlamsal + anahtar kelime) getirilmesi |
| Abstention | Yeterli kanıt yokken cevap vermeme davranışı (hata değil, tasarlanmış sonuç) |
| Guardrail | Cevap kullanıcıya gösterilmeden önce çalışan doğrulama katmanları zinciri |
| RLS | Row-Level Security — veritabanı satır düzeyi erişim politikaları |
| Blueprint | Eğitmenin kurduğu sınav çerçevesi: öğrenme çıktısı × zorluk × soru tipi matrisi |
| Holdout / kalibrasyon seti | Ölçüm için ayrılmış / eşik ayarı için kullanılan ayrık soru kümeleri |

---

## 2. Genel Tanım

### 2.1 Kullanıcı sınıfları

| Sınıf | İhtiyaç | Ana etkileşimler |
|---|---|---|
| **Eğitmen** | Materyali denetim altında tutmak, sınav çerçevesini kurmak, sınıfın durumunu görmek | Ders/üye yönetimi, materyal yükleme ve önizleme, yapay zekâ politikası, soru üretimi ve onayı, blueprint, analitik özet |
| **Öğrenci** | Sınava müfredat dahilinde, güvenilir kaynakla hazırlanmak | Kaynaklı soru-cevap, Sokratik çalışma, alıştırma ve sınav provası, "neden yanlış", ilerleme takibi |
| **Bilgi İşlem (platform yöneticisi)** | Kurum düzeyinde kullanım ve sağlık görünürlüğü | Yönetim konsolu (kullanıcılar, dersler, istekler, işleme kuyruğu), API sözleşmesine erişim |

### 2.2 Çalışma ortamı ve kısıtlar

- **Platform:** Web (masaüstü + mobil tarayıcı); Türkçe birinci dildir, materyal TR/EN karışıktır.
- **Bütçe:** ~0 (ücretsiz katmanlar).
- **Teknoloji:** Next.js 16 · FastAPI / Python 3.12 · PostgreSQL 16 + pgvector · çok dilli
  embedding `intfloat/multilingual-e5-large` (fastembed, yerel ve ağsız) · LiteLLM üzerinden
  Groq (birincil `openai/gpt-oss-120b`, yedek `qwen/qwen3.6-27b`; Gemini ikinci sağlayıcı
  seçeneği). Sunum kurulumu tek makinede, Docker'sız yerel yığındır.
- **Danışmanın yığın önerisiyle fark:** LangChain/LlamaIndex kullanılmaz; retrieval → kanıt
  eşiği → LLM → guardrail zinciri kendi kodumuzdadır, çünkü "kaynak yoksa cevap yok" kuralı
  her katmanda ölçülebilir olmalıdır ve ağır çerçeveler bu kanıtı gizler. Vektör deposu
  olarak FAISS/Chroma yerine pgvector seçildi: ders izolasyonu (RLS) ve vektör arama aynı
  veritabanında, aynı işlemde kanıtlanır. Arayüz Streamlit yerine Next.js'tir; e-posta buna
  açıkça izin verir. OpenAI'ın açık ağırlıklı `gpt-oss-120b` modeli Groq API üzerinden
  kullanılır; böylece "OpenAI API / Groq API" önerisinin ikisi de karşılanır.
- **Yasal:** KVKK aydınlatma metni; yapay zekâ çıktısı resmî not değildir
  (human-in-the-loop); örnek materyal telifsiz/kendi üretimidir.

### 2.3 Varsayımlar

Öğrenci derse yalnız eğitmen davetiyle katılır (self-enroll v2). Sınav süresi ve soru
sayısı ders politikasından gelir. Süre dolduğunda cevapsız sorular boş sayılır, puana
katılmaz. Kod hiçbir koşulda çalıştırılmaz; kod soruları statik değerlendirilir.

### 2.4 Kullanım senaryoları

Her senaryo gerçek arayüzde uçtan uca çalıştırılmıştır (14 Eylül 2026 yerel duman koşusu,
`docs/jury-demo.md`); "Kanıt" sütunu ilgili otomatik testi ya da koşuyu gösterir.

| # | Senaryo | Aktör | Ön koşul | Ana akış | Alternatif / hata | FR | Kanıt |
|---|---|---|---|---|---|---|---|
| UC-01 | Ders açma ve materyal yükleme | Eğitmen | Giriş yapılmış | Ders oluştur → PDF/PPTX/MD/kod yükle → işleme durumunu izle → "Hazır" | Tür/boyut/imza reddi; mükerrer içerik hash ile reddedilir; işleme hatası yeniden dene | FR-004–008 | `test_documents*`, duman koşusu: 5 belge, 22 parça |
| UC-02 | Öğrenci ekleme | Eğitmen | Ders var | Üye ekle (e-posta, rol) → üyelik aktif | Var olan üye; ders dışı kullanıcı okuma yetkisi almaz | FR-001–003 | RLS izolasyon kanıtı + mutasyon (CI) |
| UC-03 | Kaynaklı soru-cevap | Öğrenci | Üyelik aktif, materyal hazır | Soru sor → parçalar getirilir → cevap + atıf kartları (dosya, sayfa/slayt) → karta tıkla, kaynak bağlamını gör | Kanıt yetersiz → `insufficient_context` mesajı; kapsam dışı → nazik ret; atıf doğrulanamazsa cevap gösterilmez | FR-009–013 | Gerçek modelle 14 Eyl: 5,7 sn, 3 kaynak; `flows.spec.ts` |
| UC-04 | Kapsam dışı soru | Öğrenci | UC-03 | "İtalya'nın başkenti neresidir?" → ret, nedeniyle | Ret hata gibi değil olağan sonuç olarak sunulur | FR-011 | Gerçek modelle doğrulandı; `demo_questions.json` kapsam dışı kümesi |
| UC-05 | Sokratik çalışma | Öğrenci | Ders politikasında Sokratik mod açık | Soru → yönlendirme → ipucu → benzer örnek → kaynaklı açıklama; "cevabı söyle" ısrarında merdiven ilerlemez | Kod/çözüm sızıntısı tespitinde şablon ipucuna düşülür (fail-closed) | FR-014–016 | Gerçek modelle 14 Eyl; Sokratik test kümesi |
| UC-06 | Sınav çerçevesi kurma | Eğitmen | Materyal hazır | Konu (öğrenme çıktısı) → tip (test / klasik / kısa cevap / kod) → zorluk → isterse ≤5 örnek soru → blueprint sürümü | Blueprint hazır değilse yayınlanamaz (readiness) | FR-022–024, FR-036 | `blueprint-topic-readiness.spec.ts`, RLS blueprint kanıtı |
| UC-07 | Soru üretimi ve onayı | Eğitmen | UC-06 | Üret → taslaklar havuza düşer → tek tek onayla / reddet / düzenle | Şema geçersiz üretim reddedilir; onaysız soru öğrenciye görünmez | FR-022–026 | `question-authoring.spec.ts`; şema geçerliliği SC-009 |
| UC-08 | Alıştırma ve sınav provası | Öğrenci | Onaylı soru var | Alıştırma: anında geri bildirim; Sınav: süreli, tek deneme, geri bildirim sonda; yanlış çoktan seçmelide "neden yanlış" kaynak bölümü | Süre dolunca boş sorular puana katılmaz; sınav modunda asistan kilitli | FR-017–021 | `exam-completion-guards`, `grounded-wrong-feedback`, `exam-assistant-killswitch` spec'leri |
| UC-09 | Sınıf analitiği | Eğitmen | Öğrenci etkinliği var | Konu bazlı ilerleme, soru kalitesi, sohbet geri bildirimi özetleri | Veri yoksa boş durum metni | FR-027–029 | `analytics`, `chat-quality` uçları; `learning-events.spec.ts` |
| UC-10 | Kişisel veri hakları | Öğrenci | Giriş yapılmış | Sohbet geçmişini sil, verimi dışa aktar, hesabı anonimleştir | Aydınlatma metni girişten önce erişilebilir | FR-030–035 | `chat-history-deletion.spec.ts`, `/kvkk` |
| UC-11 | Taranmış / el yazısı materyal işleme | Eğitmen | Ders var | Metin katmanı olmayan PDF yükle → sistem kendisi görsel okumaya yönlendirir → sayfalar transkribe edilir → "Hazır" | Görsel okuma kapalıysa net mesajla ret, yeniden denenmez; güven eşiğini geçemeyen sayfa atılır, hiçbiri geçmezse belge reddedilir | FR-037–039 | 15 Eyl ölçümü: 4 sayfalık el yazısı ders notu, atılan sayfa 0, 5828 karakter, 5 parça |
| UC-12 | Platform yönetimi | Bilgi İşlem | Yönetici yetkisi | Genel bakış, kullanıcılar, dersler, istek günlüğü, işleme kuyruğu; API sözleşmesi | Reddedilen erişim de denetim kaydına yazılır | Platform konsolu spec'i | `admin-readiness.spec.ts`, yetki mutasyon kanıtı |

### 2.5 Arayüzler

**Kullanıcı arayüzü (web, 22 rota).** Tüm metinler Türkçe; açık ve koyu tema; mobil düzen.

| Rota | Rol | Amaç |
|---|---|---|
| `/` · `/forgot-password` · `/reset-password` · `/verify-email` · `/auth/callback` | herkes | Giriş ve hesap akışları |
| `/kvkk` | herkes | Aydınlatma metni (girişten önce erişilebilir) |
| `/dashboard` | eğitmen · öğrenci | Genel bakış: dersler, son etkinlik, öğrenci için ilerleme |
| `/courses` | eğitmen · öğrenci | Ders listesi; eğitmen yeni ders açar |
| `/courses/[id]` | eğitmen · öğrenci | Ders ana sayfası; eğitmen için materyal yükleme ve işleme durumu |
| `/courses/[id]/sources` · `/sources/[chunkId]` | eğitmen · öğrenci | Kaynak parçaları ve atıf bağlamı |
| `/courses/[id]/chat` | öğrenci | Ders asistanı: kaynaklı soru-cevap ve Sokratik mod |
| `/courses/[id]/exam` | öğrenci | Alıştırma ve sınav provası, "neden yanlış" |
| `/courses/[id]/questions` | eğitmen | Soru havuzu: üretim, taslak onayı, filtreler |
| `/courses/[id]/blueprints` | eğitmen | Sınav çerçevesi (öğrenme çıktısı × zorluk × tip) |
| `/courses/[id]/members` | eğitmen | Katılımcılar |
| `/courses/[id]/analytics` · `/quality` | eğitmen | Sınıf analitiği ve yapay zekâ kalite göstergeleri |
| `/courses/[id]/settings` | eğitmen | Yapay zekâ politikası (Sokratik, sınav modu, günlük bütçe) |
| `/profile` · `/account` | herkes | Profil; veri dışa aktarma, silme, anonimleştirme |
| `/admin` | Bilgi İşlem | Platform yönetim konsolu |

**Programlama arayüzü (HTTP API).** OpenAPI 3.1; 61 yol, 77 işlem, 15 uç ailesi:
`health`, `profile`, `dashboard`, `admin`, `courses`, `documents`, `sources`, `privacy`,
`chat`, `policy`, `assessment`, `chat-quality`, `exams`, `blueprints`, `analytics`.
Kimlik `Bearer` jetonu (yerel geliştirmede `dev:<uuid>`, canlıda kurum kimliği); hata zarfı
`error.code · message · request_id`; sayfalama `items + next_cursor`. Belge sayfası `/docs`
(şema yalnız platform yöneticisine).

**Dış arayüzler.**

| Sistem | Yön | Kullanım | Sunumda |
|---|---|---|---|
| Groq API (LiteLLM) | çıkış | Cevap üretimi, Sokratik ipucu, soru üretimi, rubrikli değerlendirme | Gerçek model; ağ kesilirse `answer_cache` + sahte sağlayıcı (Plan C) |
| Google Gemini API (LiteLLM) | çıkış | Yedek sağlayıcı; değerlendirme yargıcı seçeneği | Anahtar girildiyse yedek |
| PostgreSQL 16 + pgvector | iç | Tüm veri, vektör arama, RLS izolasyonu | Yerel |
| fastembed (ONNX) | iç | Embedding; ağ gerektirmez, model önbelleği yerel | Yerel |
| Dosya depolama | iç | Yüklenen materyaller (yerel dizin; v2'de Supabase Storage) | Yerel |

---

## 3. Paydaş Gereksinimi → Sistem Gereksinimi İzlenebilirliği

### 3.1 Yapay zekânın üç rolü (danışmanın istediği ayrım)

| Rol | Danışmanın adı | Arayüzdeki yüzey | Yapar | Yapmaz | Kanıt |
|---|---|---|---|---|---|
| **Ders Asistanı** | Class Assistant | `/courses/[id]/chat` — "Ders Koçu" kimliği | Materyal içi soruyu kaynak göstererek yanıtlar; Sokratik modda ipucu merdiveni | Materyalde karşılığı olmayan soruya cevap üretmez; kod/çözüm sızdırmaz | UC-03/04/05; SC-002, SC-005, SC-007 |
| **Sınav Mentoru** | Exam Mentor | `/courses/[id]/exam` — alıştırma ve sınav provası | Cevabı değerlendirir, yanlış çeldiricinin çeliştiği kaynak bölümünü gösterir; sınav modunda ipucu kapalı | Sınav sırasında cevap vermez; resmî not vermez (öneri niteliğinde) | UC-08; `grounded-wrong-feedback`, `exam-assistant-killswitch` |
| **Soru Üretici** | CourseGPT | `/courses/[id]/questions` + `/blueprints` — "Eğitmen Asistanı" kimliği | Eğitmenin kurduğu çerçevede (tip, biçim, konu, örnek sorular) materyalden soru ve cevap anahtarı üretir | Eğitmen onayı olmadan hiçbir soruyu öğrenciye göstermez | UC-06/07; SC-009 |

### 3.2 E-posta taslağı (27 Temmuz)

Danışman taslağındaki **12 maddenin tamamı** karşılanmıştır:

| # | Danışman taslağı maddesi | Karşılayan FR'ler |
|---|---|---|
| 1 | Eğitmen: PDF/Markdown/kod yükleme | FR-004, FR-005, FR-006 |
| 2 | Yüklenenler dersin bilgi tabanı | FR-002, FR-007, FR-008 |
| 3 | Sokratik mod (cevabı verme, ipucuyla çözdür) | FR-014, FR-015, FR-016 |
| 4 | Sınav Prova modu (süreli, puanlama, detaylı geri bildirim) | FR-017, FR-018, FR-019 |
| 5 | İçerikten soru + cevap anahtarı üretimi | FR-022, FR-023, FR-024 |
| 6 | Öğrenci: interaktif çözüm, eksik söylenir | FR-019, FR-020 |
| 7 | "Neden yanlış?" (çelişen slayt bölümü gösterilir) | FR-021 |
| 8 | Kod/senaryo inceleme (çıktı analizi, hata buldurma) | FR-025, FR-026 |
| 9 | Müfredat dışına nazik ret | FR-011 |
| 10 | Her yanıtta slayt/sayfa referansı zorunlu | FR-010, FR-012, FR-013, FR-016 |
| 11 | İnternet bilgisi karıştırılmaz | FR-009, FR-011 |
| 12 | Teslim: platform + örnek paket & rapor + kılavuzlar | FR-031, FR-032, FR-033 |

### 3.3 Toplantı istekleri (6 Ağustos)

| # | İstek | Karşılık |
|---|---|---|
| T1 | Yapay zekânın rolü net tanımlansın | bkz. §3.1 (rol × yüzey × kanıt); arayüz kimlikleri |
| T2 | Çoklu soru biçimi: test / klasik / kısa cevap; çerçeve önce kurulsun | `mcq`, `open` (`essay` / `short_answer`), `code_trace`, `bug_hunt`; blueprint; örnek soruyla üslup (FR-036, UC-06) |
| T3 | İzlence/kitaptan örnek soru üret, cevabı vermeden yönlendir | Yüklenen materyalden üretim + Sokratik yönlendirme; izlenceden otomatik konu çıkarımı v2 |
| T4 | Hocanın istediği çözüm yöntemi denetimi | Kısmen: rubrik ölçütleri; ayrı "beklenen çözüm yolu" alanı v2 |

---

## 4. Fonksiyonel Gereksinimler (özet)

Gereksinimler kullanıcı hikâyeleri altında toplanmıştır (tam metin ve Given/When/Then kabul
senaryoları spec dizinlerindedir):

**A. Hesap, rol ve izolasyon (FR-001–003).** Rol yetkileri sunucuda zorlanır. Ders verisi
dersler arasında **iki katmanda** izoledir: uygulama katmanı üyelik doğrulaması + PostgreSQL
RLS. İstemciden gelen ders kimliği asla yetki sayılmaz.

**B. Materyal yönetimi (FR-004–008).** PDF/PPTX/Markdown/metin/kod yüklenir; tür beyaz
listesi + boyut sınırı + dosya imzası (magic byte) doğrulaması yapılır. İşleme asenkrondur
ve durum izlenir. Sayfa/slayt/bölüm metadata'sı korunarak parçalanır; mükerrer içerik
hash ile reddedilir.

**C. Kaynaklı cevap ve guardrail (FR-009–013).** Cevaplar yalnız o dersin işlenmiş
materyalinden üretilir. Her cevap dosya adı + sayfa/slayt referansı taşır; referans model
metninden değil parça metadata'sından üretilir. Atıflar, gerçekten getirilen parça
kümesine üyelik açısından **mekanik olarak** doğrulanır; geçerli atıf kalmazsa cevap
gösterilmez. Yetersiz kanıt (`insufficient_context`) ile müfredat dışılık (`out_of_scope`)
ayrı durumlardır ve ikisi de nazik Türkçe mesajla, hata gibi değil olağan sonuç olarak sunulur.

**D. Sokratik mod (FR-014–016).** Cevap doğrudan verilmez; sunucuda tutulan kademeli
durum makinesi (yönlendirme → kavram ipucu → benzer örnek → kaynaklı açıklama) işler.
İpuçları da kaynak parçadan türetilir ve atıf taşır. Kod bloğu/doğrudan çözüm sızıntısı
kural tabanlı son kontrolle engellenir; ihlalde şablon ipucuna düşülür (fail-closed).

**E. Sınav provası (FR-017–021, FR-036).** Süreli oturum; sınav modunda ipucu kapalı, soru
başına tek deneme, geri bildirim sonda (alıştırma modunda süresiz + anında geri bildirim).
Açık uçlu sorular iki biçimde değerlendirilir: `essay` rubrik + cevap anahtarı + kaynak
parçalarla LLM'e, `short_answer` kabul edilen cevap listesiyle deterministik. Her yanlış
çoktan seçmeli için çeldiricinin çeliştiği kaynak bölümü gösterilir ("neden yanlış").

**F. Soru havuzu, blueprint ve kod inceleme (FR-022–026).** Materyalden dört tipte soru
üretilir: çoktan seçmeli, açık uçlu, `code_trace` (çıktı tahmini), `bug_hunt` (hata
buldurma). Eğitmen çerçeveyi kurar (konu, tip, biçim, isterse örnek sorular; blueprint ile
hedef × zorluk × tip). Üretilenler taslak düşer; **eğitmen onayı olmadan öğrenciye
gösterilmez**. Kod hiçbir koşulda çalıştırılmaz — değerlendirme statiktir.

**F2. Taranmış ve el yazısı materyal (FR-037–039).** PDF'te metin katmanı varsa doğrudan
okunur. Yoksa eğitmenin "bu tarama, önce OCR'dan geçireyim" demesi beklenmez: sistem
kendisi karar verir. Görsel okuma AÇIKSA sayfa görüntüye çevrilip görsel modele
transkribe ettirilir; KAPALIYSA belge net bir mesajla reddedilir ("Taranmış ya da el yazısı
belgeler için görsel okuma gerekir; bu ders için şu an kapalı") ve **yeniden denenmez** —
içerik hatası kalıcıdır, üç kez denemek yalnız yanlış tavsiye verir.

Görsel okumanın üç koruması vardır: (a) transkripsiyon istemi harfi harfine aktarım ister,
düzeltmeyi ve tahmini yasaklar; okunamayan yer `[okunamadı]`, çizimler transkribe edilmez,
`[çizim: …]` diye işaretlenir; (b) `[okunamadı]` sayısı/oranı eşiği aşan sayfa ATILIR ve
hiçbir sayfa geçemezse belge reddedilir — yani en kötü durum "görsel okuma hiç yokmuş gibi"
davranmaktır, anlamsız metin asla indekslenmez; (c) görsel okumadan gelen her parça
**"AI okuması" köken etiketi** taşır ve atıf yüzeyinde bu etiket görünür.

**G. İlerleme ve analitik (FR-027–029).** Konu bazlı performans izlenir; öğrenme olayları
kaydedilir; eğitmen tek sayfalık sınıf özeti ve yapay zekâ kalite göstergelerini görür.

**H. Platform ve teslim (FR-030–035).** Tüm kullanıcı metinleri Türkçedir; ham hata/iz
asla gösterilmez. Tek komutla yerel kurulum (`scripts/demo/*.sh`); örnek İşletim Sistemleri
materyal paketi; eğitmen ve öğrenci kılavuzları; çevrimdışı demo sigortası (`answer_cache`);
istek ve günlük jeton sınırları; KVKK hakları.

---

## 5. Fonksiyonel Olmayan Gereksinimler (kayıt için)

Danışman bu belge için fonksiyonel olmayan gereksinim istemedi; aşağıdaki satırlar teslimin
kabul ölçütü değil, projenin kendi disiplininin kaydıdır.

| Kategori | Gereksinim |
|---|---|
| **Güvenlik** | İki katmanlı ders izolasyonu; RLS'in fiilen çalıştığı, politika bilerek bozulup testin başarısız olmasıyla kanıtlanır (CI'da 6 SQL kanıtı + 8 mutasyon betiği). Dosya imza doğrulaması; loglarda kişisel veri/anahtar maskeleme; DEV kimlik doğrulaması üretimde reddedilir. |
| **Doğruluk disiplini** | Rapor edilen her sayı ölçülür; koşulmayan deney için sonuç yazılmaz; sahte sağlayıcı ölçümü gerçek model kalitesi olarak sunulmaz. |
| **Performans** | Uçtan uca cevap p95 < 10 sn (14 Eylül gerçek model tek ölçüm: 5,7 sn). |
| **Erişilebilirlik** | WCAG AA kontrast (ölçülmüş); koyu tema; mobil düzen; durum renk+metin çiftiyle. |
| **Dayanıklılık** | Fail-closed varsayılanlar; LLM kesintisinde yedek model/sağlayıcı ve önbellek. |
| **Uyumluluk** | KVKK aydınlatma metni; veri silme/dışa aktarma; YZ değerlendirmesi öneri niteliğindedir. |

---

## 6. Kabul Kriterleri (ölçülebilir)

| Kriter | Hedef | Durum (15 Eylül) |
|---|---|---|
| SC-001 Dersler arası veri sızıntısı | 0 vaka | RLS kanıtları CI'da yeşil |
| SC-002 Kaynaksız akademik cevap (ipuçları dahil) | %0 | Mekanik atıf doğrulama; test kümesi |
| SC-003 Holdout Recall@5 ve Recall@8 | ≥ %80 | Sahte sağlayıcı/hash ile ölçüldü; **gerçek modelle koşu 15 Eylül** |
| SC-004 Atıf hassasiyeti (doğru dosya+sayfa) | ≥ %90 | aynı |
| SC-005 Kapsam dışı doğru ret | ≥ %90 (holdout) | aynı; tekil gerçek model denemeleri geçti |
| SC-006 Faithfulness | Çift etiketleyicili manuel örneklem | Planlı |
| SC-007 Sokratik kod/çözüm sızıntısı | Test setinde 0 | Test kümesi yeşil |
| SC-008 Prompt injection (≥15 vaka) | Geçer | `evaluation/` injection kümesi |
| SC-009 Soru üretiminde şema geçerliliği | ≥ %98 | Şema doğrulama; sahte sağlayıcıda ölçüldü |
| SC-010 Cevap gecikmesi p95 | < 10 sn | Tekil ölçüm 5,7 sn; p95 15 Eylül |
| SC-011 Demo akışında kritik hata | 0 | 15 Eylül: sıfırdan ders + yeni belge ile uçtan uca prova **10/10** (§8) |
| SC-012 Sahne sorularının çevrimdışı çalışması | 16/16, 0 jeton | 15 Eylül ölçüldü: `scripts/demo/sahne_provasi.py` |

Metodoloji notu: değerlendirme seti **yön göstergesidir, kesin hüküm değildir**; gerçek
modelle koşulmamış her sayı belgede öyle etiketlenir.

## 7. Kapsam Dışı (gerekçeli)

Dış internet kaynakları (taslaktaki "internet bilgisi karışmaz" şartı gereği) · kod
çalıştırma ortamı · fine-tuning · mobil uygulama · LMS entegrasyonu · öğrenci self-enroll ·
gerçek zamanlı işbirliği · izlenceden otomatik konu çıkarımı (v2) · bulut barındırma ve
kurum kimliğiyle giriş (sunum sonrası).

## 8. Mevcut Durum (15 Eylül 2026)

**Danışmanın istediği uçtan uca akış ölçüldü: 10/10.** 15 Eylül sabahı, sıfırdan yeni bir
ders açılıp hiç indekslenmemiş bir belge yüklenerek gerçek tarayıcıda tek oturumda koşuldu
(`scratchpad/prova/hoca-provasi.mjs`): ders açma · öğrenci ekleme · yapay zekâ politikası ·
materyal yükleme ("Hazır", 6 parça) · kaynaklı cevap (atıf `05-deadlock-demo.md`) · kapsam
dışı ret (`out_of_scope`) · Sokratik ipucu ve ısrarda merdivenin ilerlememesi · soru üretimi
(3 istendi, 3 kabul, 0 ret) · eğitmen onayı · alıştırma ve "neden yanlış" geri bildirimi.

**Sahne provası ayrıca ölçüldü** (`scripts/demo/sahne_provasi.py`): 12 kaynaklı cevap +
4 ret sorusunun 16'sı da beklendiği gibi; harcanan jeton **0** — sahne soruları
`answer_cache`'ten döndüğü için modele hiç gitmiyor. Bu aynı zamanda çevrimdışı planın
(Plan C) kanıtıdır.

**Provanın bulduğu kusur kapatıldı.** Teşhis kademesinde model, soru sormadan önce cevabı
düzyazıyla anlatıyordu; mevcut sızıntı dedektörleri bunu göremiyordu (kod yok, adım yok,
"cevap:" kalıbı yok). Yeni `exposition` dedektörü kalıp değil **örtüşme** ölçüyor: soru
cümleleri hariç tutuluyor, düz cümlelerin içerik sözcükleri getirilen parçayla
karşılaştırılıyor ve yarıdan fazlası kaynaktan geliyorsa yanıt bloklanıp aynı kademenin
deterministik şablon ipucuna düşülüyor. Yalnız `DIAGNOSE` ve `NUDGE` kademelerinde geçerli —
üst basamaklarda açıklamak zaten kuralın kendisi.

Ölçülen: 2159 otomatik API testi toplanıyor <!-- docs-check: tarihsel 2159 · 2026-09-15 -->,
24 veritabanı göçü <!-- docs-check: tarihsel 24 · 2026-09-15 -->,
22 web rotası <!-- docs-check: tarihsel 22 · 2026-09-15 -->,
61 API yolu <!-- docs-check: tarihsel 61 · 2026-09-15 --> / 77 işlem <!-- docs-check: tarihsel 77 · 2026-09-15 -->.

**Dürüstçe eksik olanlar.** Gerçek modelle holdout değerlendirmesi (SC-003/004/005) hâlâ
koşulmadı; sayılar sahte sağlayıcı koşusundan geliyor ve belgede öyle etiketli. Faithfulness
(SC-006) ve atıf hassasiyeti ayrı ayrı ölçülmedi — mekanik atıf geçerliliği mimari olarak
garantili, ama "atıf iddiayı gerçekten destekliyor mu" ayrı bir ölçümdür ve yapılmadı.
Sistem tek makinede çalışıyor, bulut kurulumu ve kurum kimliğiyle giriş yok. Sınav planı ve
yayımlanmış sınav sürümü demo veritabanında bulunmadığı için "Sınav Mentoru" rolü sahnede
yalnız alıştırma moduyla gösterilebilir. Eksikler ve saatli plan:
`docs/team/YOL-HARITASI-16-EYLUL.md`.
