# DOU-Synapse — Gereksinim Analizi Raporu

**Proje:** CourseGPT — Yapay Zekâ Destekli Kişiselleştirilmiş Ders ve Sınav Asistanı
**Ders:** COME 491/492 Bitirme Projesi · Doğuş Üniversitesi · Danışman: Yasemin Karagül
**Takım:** Muratcan Ateş (frontend/lead) · Eren (backend/RAG + guardrail) · Metehan (assessment + ölçüm)
**Tarih:** 6 Ağustos 2026 · **Teslim:** 24 Ağustos 2026
**Tam gereksinim metni:** `specs/001-course-assistant-mvp/spec.md` (bu rapor onun akademik özetidir)

---

## 1. Giriş

### 1.1 Amaç

Bu belge, danışmanın CourseGPT proje taslağındaki beklentileri doğrulanabilir sistem
gereksinimlerine dönüştürür. Her taslak maddesi numaralı bir fonksiyonel gereksinime (FR)
izlenir; her başarı hedefi ölçülebilir bir kabul kriterine (SC) bağlanır.

### 1.2 Problem tanımı

Öğrenciler sınava hazırlanırken genel amaçlı yapay zekâ araçlarına yöneliyor; bu araçlar
(1) ders müfredatı dışına çıkıyor, (2) kaynak göstermiyor, (3) ödev sorularının cevabını
doğrudan vererek öğrenmeyi zedeliyor. Literatürde bu üçüncü problem ölçülmüştür: Harvard'ın
CS50 ders asistanı değerlendirmesinde yanıtların %22'sinde öğrenciye doğrudan çalışan kod
sızdırıldığı raporlanmıştır (Liu vd., 2025).

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
| Holdout / kalibrasyon seti | Ölçüm için ayrılmış / eşik ayarı için kullanılan ayrık soru kümeleri |

---

## 2. Genel Tanım

### 2.1 Kullanıcı sınıfları

| Sınıf | İhtiyaç | Ana etkileşimler |
|---|---|---|
| **Eğitmen** | Materyali denetim altında tutmak, sınıfın durumunu görmek | Ders/üye yönetimi, materyal yükleme ve önizleme, soru onayı, analitik özet |
| **Öğrenci** | Sınava müfredat dahilinde, güvenilir kaynakla hazırlanmak | Kaynaklı soru-cevap, Sokratik çalışma, sınav provası, "neden yanlış", ilerleme takibi |

### 2.2 Çalışma ortamı ve kısıtlar

- **Platform:** Web (masaüstü + mobil tarayıcı); Türkçe birinci dildir, materyal TR/EN karışıktır.
- **Bütçe:** ~0 (ücretsiz katmanlar); **takvim:** 15 iş günü, iki sert kapı
  (10 Ağu uçtan uca dikey demo, 17 Ağu özellik dondurma).
- **Teknoloji kilidi:** Next.js · FastAPI/Python 3.12 · PostgreSQL 16 + pgvector ·
  çok dilli embedding (multilingual-e5-large) · LiteLLM (Groq→Gemini otomatik yedekli).
  Ağır çerçeveler (LangChain vb.) bilinçli olarak kullanılmaz — gerekçeler `research.md`'de.
- **Yasal:** KVKK aydınlatma metni; yapay zekâ çıktısı resmî not değildir
  (human-in-the-loop); örnek materyal telifsiz/kendi üretimidir.

### 2.3 Varsayımlar

Öğrenci derse yalnız eğitmen davetiyle katılır (self-enroll v2). Sınav süresi ve soru
sayısı MVP'de yapılandırma sabitidir (eğitmen ayar ekranı v2). Süre dolduğunda cevapsız
sorular boş sayılır, puana katılmaz.

---

## 3. Paydaş Gereksinimi → Sistem Gereksinimi İzlenebilirliği

Danışman taslağındaki **12 maddenin tamamı** karşılanmıştır; hiçbir madde ertelenmemiş
veya kapsam dışına alınmamıştır:

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

---

## 4. Fonksiyonel Gereksinimler (özet)

35 gereksinim yedi kullanıcı hikâyesi altında toplanmıştır (tam metin ve Given/When/Then
kabul senaryoları spec.md'dedir):

**A. Hesap, rol ve izolasyon (FR-001–003).** Rol yetkileri sunucuda zorlanır. Ders verisi
dersler arasında **iki katmanda** izoledir: uygulama katmanı üyelik doğrulaması + PostgreSQL
RLS. İstemciden gelen ders kimliği asla yetki sayılmaz.

**B. Materyal yönetimi (FR-004–008).** PDF/PPTX/Markdown/metin/kod yüklenir; tür beyaz
listesi + 20 MB sınırı + dosya imzası (magic byte) doğrulaması yapılır. İşleme asenkrondur
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

**E. Sınav provası (FR-017–021).** Süreli oturum; sınav modunda ipucu kapalı, soru başına
tek deneme, geri bildirim sonda (practice modunda süresiz + anında geri bildirim). Açık
uçlu cevaplar rubrik + cevap anahtarı + kaynak parçalara göre değerlendirilir; çıktı
şemaya uymalıdır. Her yanlış çoktan seçmeli için çeldiricinin çeliştiği kaynak bölümü
gösterilir ("neden yanlış").

**F. Soru havuzu ve kod inceleme (FR-022–026).** Materyalden dört tipte soru üretilir:
çoktan seçmeli, açık uçlu, `code_trace` (çıktı tahmini), `bug_hunt` (hata buldurma).
Üretilenler taslak düşer; **eğitmen onayı olmadan öğrenciye gösterilmez**. Kod hiçbir
koşulda çalıştırılmaz — değerlendirme statiktir.

**G. İlerleme ve analitik (FR-027–029).** Konu bazlı performans EWMA ile izlenir
(bilinçli sadeleştirme; gerekçesi ve "resmî not değildir" kaydı belgelidir). Eğitmen tek
sayfalık sınıf özeti görür.

**H. Platform ve teslim (FR-030–035).** Tüm kullanıcı metinleri Türkçedir; ham hata/iz
asla gösterilmez. Canlı URL + tek komutla yerel kurulum; örnek İşletim Sistemleri materyal
paketi; eğitmen ve öğrenci kılavuzları; çevrimdışı demo sigortası; istek ve girdi sınırları.

---

## 5. Fonksiyonel Olmayan Gereksinimler

| Kategori | Gereksinim |
|---|---|
| **Güvenlik** | İki katmanlı ders izolasyonu; RLS'in fiilen çalıştığı, politika bilerek bozulup testin başarısız olmasıyla kanıtlanır (CI'da otomatik). Dosya imza doğrulaması; sunucu üretimi depolama anahtarları (path traversal engeli); loglarda kişisel veri/anahtar maskeleme; DEV kimlik doğrulaması üretimde yapılandırma düzeyinde reddedilir. |
| **Doğruluk disiplini** | Rapor edilen her sayı ölçülür; eşikler kalibrasyon setinde ayarlanır, metrikler ayrık holdout sette raporlanır; koşulmayan deney için sonuç yazılmaz. "Deterministik/garanti" sözcükleri yalnız gerçekten deterministik mekanizmalar için kullanılır. |
| **Performans** | Uçtan uca cevap p95 < 10 sn (sıcak replika); işleme ilerlemesi kullanıcıya n/m olarak gösterilir. |
| **Kullanılabilirlik / erişilebilirlik** | WCAG AA kontrast (ölçülmüş); koyu tema zorunlu (gece çalışma senaryosu); mobil öncelikli öğrenci ekranları; abstention hata gibi değil bilgi olarak sunulur; durum renk+metin çiftiyle işaretlenir. |
| **Dil** | Türkçe birinci sınıftır: tüm kullanıcı metinleri, hata mesajları dahil; `uppercase` dönüşümü yasak (i/İ bozulması); TR/EN karışık materyal için çok dilli embedding. |
| **Dayanıklılık** | Fail-closed varsayılanlar: oturum bağlamı yoksa veri görünmez, kanıt yoksa cevap yok, doğrulanamayan çıktı gösterilmez. LLM sağlayıcı kesintisinde otomatik yedek (Groq→Gemini). |
| **Uyumluluk** | KVKK aydınlatma metni; sohbet verisi saklama süresi tanımı; YZ değerlendirmesi öneri niteliğindedir. |

---

## 6. Kabul Kriterleri (ölçülebilir)

| Kriter | Hedef |
|---|---|
| SC-001 Dersler arası veri sızıntısı | 0 vaka |
| SC-002 Kaynaksız akademik cevap (ipuçları dahil) | %0 |
| SC-003 Holdout Recall@5 ve Recall@8 | ≥ %80 |
| SC-004 Atıf hassasiyeti (doğru dosya+sayfa) | ≥ %90 |
| SC-005 Kapsam dışı doğru ret | ≥ %90 (holdout) |
| SC-006 Faithfulness | 20-30 cevaplık çift etiketleyicili manuel örneklem, uyum oranıyla raporlanır |
| SC-007 Sokratik kod/çözüm sızıntısı | Test setinde 0 (set; gizli kod, sözde-kod, sözel çözüm vakalarını içerir) |
| SC-008 Prompt injection (≥15 vaka) | Geçer — "temel kalıplara karşı sınandı" olarak raporlanır |
| SC-009 Soru üretiminde şema geçerliliği | ≥ %98 |
| SC-010 Cevap gecikmesi p95 | < 10 sn |
| SC-011 Demo akışında kritik hata | 0 |

Metodoloji notu: n≈50'lik değerlendirme seti **yön göstergesidir, kesin hüküm değildir**;
baseline-hybrid karşılaştırması eşleştirilmiş anlamlılık kaydıyla verilir. Set,
danışmanın gözden geçirmesine sunulacaktır.

## 7. Kapsam Dışı (gerekçeli)

Dış internet kaynakları (taslaktaki "internet bilgisi karışmaz" şartı gereği; v2'de
*eğitmen onaylı* paket olarak değerlendirilebilir) · kod çalıştırma ortamı · fine-tuning ·
mobil uygulama · LMS entegrasyonu · öğrenci self-enroll · gerçek zamanlı işbirliği.
Tam liste ve nedenleri: `PLAN.md §2`.

## 8. Mevcut Durum (6 Ağustos)

Altyapı tamam ve 68 otomatik testle doğrulanmış durumda: izolasyon (kanıtlı RLS), <!-- docs-check: tarihsel 68 · 2026-08-06 -->
materyal işleme hattı, embedding/indeksleme, arayüzün 6 ekranı. Cevap üretim hattı <!-- docs-check: tarihsel 6 · 2026-08-06 -->
(retrieval→LLM→guardrail) 10 Ağustos dikey demo kapısının işidir; 60 görevlik izlenebilir
iş listesi `specs/001-course-assistant-mvp/tasks.md`'dedir.
