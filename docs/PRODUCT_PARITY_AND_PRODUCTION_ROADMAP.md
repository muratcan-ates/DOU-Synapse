# DOU-Synapse: Güncel Ürün Paritesi ve Production Yol Haritası

**Tarih:** 10 Ağustos 2026  
**Kapsam:** Hocanın ilk toplantı gereksinimleri, güncel kod tabanı, benzer ürünlerin resmî kaynakları ve production çıkış kapıları  
**Durum dili:** “Var” yalnız kod + test veya görünür ürün kanıtı varsa kullanılır. Gerçek Supabase, gerçek LLM ve canlı URL olmadan “production tamam” denmez.

## 1. Net hüküm

DOU-Synapse artık basit bir RAG demosu değildir. Öğretmen/öğrenci rolleri, kaynak yükleme ve parçalama, kaynaklı sohbet, Sokratik merdiven, kapsam dışı ret, soru havuzu, sınav blueprint’i, onaylı soru kapısı, ders bazlı AI politikası, süreli sınav, sınav sırasında asistan kilidi, analitik, KVKK hakları ve retrieval laboratuvarı vardır.

Kalan ana boşluk “bir ekran daha yapmak” değildir. Ürünün gerçek kullanıcı ve gerçek sağlayıcıyla işletildiğini kanıtlamaktır:

1. Gerçek Supabase projesi ve gerçek kullanıcı hesapları.
2. Groq/Gemini gibi gerçek LLM ile pedagojik ve kaynak sadakati değerlendirmesi.
3. Staging ve production ortamları, canlı URL, e-posta teslimi, yedekleme ve gözlemleme.
4. Gerçek ders materyali üzerinde öğretmen kabul oranı ve periyodik insan incelemesi.

Bu belgede ayrıca üç yeni ürün boşluğu kapatılmıştır:

- Her asistan yanıtında öğrenci geri bildirimi ve gerekçe seçimi.
- Varsayılan sohbet gizliliğini bozmadan, yalnız öğrenci izniyle öğretmen inceleme kuyruğu.
- Gerçek Supabase Auth için parola kurtarma ve parola yenileme akışı.
- CourseGPT, Exam Mentor ve Class Assistant rollerinin çalışan ekranlara bağlı görünür ürün yüzeyi.

## 2. Hocanın gereksinimleri: güncel karşılık

| Gereksinim | Güncel durum | Production için kalan kanıt |
|---|---|---|
| Öğretmen ve öğrenci girişi | Var. Yerel demo rolleri ve Supabase Auth istemcisi var. | Gerçek proje, gerçek hesap, SMTP ve parola kurtarma e-postasıyla canlı test. |
| Öğretmen dashboard’u | Var. Ders, materyal, soru havuzu, blueprint, AI politikası, analitik ve kalite ekranları var. | Canlı ortamda en az bir gerçek dersle jüri senaryosu. |
| PDF, PPTX, Markdown ve kod yükleme | Var. Boyut/tip doğrulama, ingestion işi, retry, provenance ve önizleme var. | Uzak Supabase Storage ve farklı dosya örnekleriyle smoke test. |
| Yalnız öğretmen kaynağından cevap | Var. Retrieval kanıt eşiği, atıf guardrail’i ve ders izolasyonu var. | Gerçek LLM holdout değerlendirmesinde faithfulness ölçümü. |
| Kapsam dışı soruyu reddetme | Var. `out_of_scope` ve `insufficient_context` ayrı sonuçlar. | Hedef en az %90 doğru ret; güncel gerçek-model holdout raporu. |
| Sokratik yönlendirme | Var. Beş kademeli, sunucu kontrollü merdiven ve ipucu limiti var. | Öğretmen rubric’iyle pedagojik kalite ve “cevabı erken verdi mi?” ölçümü. |
| Çoktan seçmeli, klasik, kısa cevap ve kod soruları | Var. Onay akışı ve kaynak ilişkisiyle birlikte. | Gerçek LLM üretiminde kabul/ret nedenleri ve öğretmen kabul oranı. |
| “Önce sınav çatısı” | Var. Öğrenme çıktısı, zorluk, soru tipi, puan, süre, deneme, tarih ve sürüm içeren blueprint var. | Gerçek ders blueprint’i yayımlanıp uçtan uca sınav koşulmalı. |
| Sınav sırasında yardım yasağı | Var. UI ve API düzeyinde aktif sınav kilidi var. | Canlı deployment üzerinde ikinci sekme ve doğrudan API E2E güvenlik kapısı. |
| “Neden yanlış?” | Var. Kaynaklı geri bildirim, rubric kırılımı ve değerlendirilmemiş cevap ayrımı var. | Gerçek modelle açık uçlu/kod yanıtlarının insan karşılaştırması. |
| CourseGPT / Exam Mentor / Class Assistant | Var ve ders ana sayfasında görünür. Her rol çalışan yüzeye gider. | Tanıtım videosunda üç rolün birer senaryosu gösterilmeli. |
| Test raporu ve kullanım kılavuzu | Var. Belgeler otomatik doğrulama kapılarıyla izleniyor. | Son production adresi, gerçek-model sonuçları ve sürüm numarası eklenmeli. |
| 10–15 dakikalık video | Kod işi değil; senaryo/runbook altyapısı var. | Canlı/staging ürün üstünden son kayıt kullanıcı tarafından alınmalı. |

## 3. Benzer ürünlerden çıkarılan kalite ilkeleri

### 3.1 Khanmigo: tek sohbet değil, görünür öğretmen araçları

Khanmigo öğretmen deneyimini tek bir konuşma kutusuna sıkıştırmıyor; ders planı, rubric, çıkış bileti, çoktan seçmeli değerlendirme, öneri ve sınıf özeti gibi ayrı araçlar sunuyor. Ayrıca öğretmen raporlarında beceri, ödev, kullanım ve sınıf etkinliği gibi farklı görünümler bulunuyor. DOU-Synapse’in blueprint, AI politikası, retrieval testi, analitik ve yeni AI kalite ekranı bu ilkeye yaklaşır. Sonraki parite adımı, öğretmenin onaylı soru/blueprint’i PDF veya CSV olarak dışa aktarabilmesidir.

Kaynaklar: [Khanmigo teacher tools](https://support.khanacademy.org/hc/en-us/articles/14799047733645-What-teacher-tools-are-available-on-Khanmigo-), [Khanmigo teacher reports](https://support.khanacademy.org/hc/en-us/articles/38554738905997-What-teacher-reports-are-available-on-the-Khanmigo-Classroom-Pilot).

Khanmigo yararlı/yararsız puanı ve ayrıntılı gerekçe topluyor. DOU-Synapse bu turda aynı kalite döngüsünü ekledi; ancak mevcut gizlilik kararını korudu: öğretmen bütün sohbetleri okuyamaz, yalnız öğrencinin açıkça paylaştığı soru-cevap çiftini görür. Bu, kalite incelemesi ile güvenli özel çalışma alanını birlikte korur.

Kaynaklar: [Khanmigo feedback](https://support.khanacademy.org/hc/en-us/articles/13983335341069-How-do-I-leave-feedback-about-Khanmigo), [Khanmigo safety features](https://support.khanacademy.org/hc/en-us/articles/14394814244365-What-safety-features-does-Khanmigo-have).

### 3.2 NotebookLM: atıf, özgün bağlama götürmeli

NotebookLM kaynak seçimiyle sınırlandırılmış sohbet ve satır içi atıf sunuyor; atıf kullanıcıyı dayandığı özgün bölüme götürüyor. DOU-Synapse’te bu artık öneri değil, mevcut ürün davranışıdır: kaynak kartı seçilen chunk’a gider, önceki/sonraki bağlamı gösterir ve seçili pasajı ayırır.

Sonraki parite adımı yeni bir citation kartı yapmak değil; öğretmenin kaynak sürümü değişince eski soruların ve yanıtların etkisini raporlamaktır. Soru tarafında `source_stale` mevcut; aynı görünürlük değerlendirme raporlarına da taşınmalıdır.

Kaynaklar: [NotebookLM chat and citations](https://support.google.com/notebooklm/answer/16164461?hl=en), [NotebookLM citation context](https://support.google.com/notebooklm/answer/16179559?hl=en).

### 3.3 Moodle AI: placement, action ve provider ayrı yönetilmeli

Moodle AI alt sistemi, sağlayıcıyı kullanıcı yüzeyinden ve yapılan eylemden ayırıyor; birden fazla sağlayıcı örneği ve eylem bazlı kullanılabilirlik destekliyor. DOU-Synapse’in ders AI politikası mod, kaynak, ipucu, eşik ve bütçe tarafını karşılıyor. Kalan parite, “sohbet”, “soru üretme” ve “açık uçlu puanlama” için ayrı model/sağlayıcı ve ayrı maliyet bütçesi seçebilmektir.

Kaynaklar: [Moodle AI settings](https://docs.moodle.org/501/en/admin/setting/ai), [Moodle AI providers](https://docs.moodle.org/501/en/AI_providers).

### 3.4 RAGFlow: retrieval görünür ve sınanabilir olmalı

RAGFlow, parçalama sonucunu görünür kılmayı ve sohbetten önce retrieval testi yapmayı ürünün parçası sayıyor. DOU-Synapse’te eğitmenin dense skor, eşik, lexical coverage, aday parçalar ve özgün kaynak bağlamını gördüğü retrieval laboratuvarı vardır. Bu nedenle eski yol haritalarındaki “chunk preview/retrieval test ekle” maddesi kapanmıştır.

Kalan parite; taranmış PDF/OCR, tablo ve görsel ağırlıklı slaytlarda multimodal parsing kalitesidir. Bu iş, gerçek ders paketinde metin çıkarma kaybı ölçülmeden başlatılmamalıdır.

Kaynaklar: [RAGFlow quickstart](https://github.com/infiniflow/ragflow/blob/main/docs/quickstart.mdx), [RAGFlow RAG basics](https://github.com/infiniflow/ragflow/blob/main/docs/basics/rag.md).

### 3.5 Harvard CS50: prompt değil, sürekli insan değerlendirmesi

CS50’nin AI öğretim çalışmaları çok turlu görevler, öğretim görevlisi değerlendirmesi ve dönemsel inceleme kullanıyor. DOU-Synapse’in yeni geri bildirim kuyruğu bu döngünün veri toplama katmanıdır; tek başına kalite kanıtı değildir. Gerçek LLM açıldığında öğretmen her hafta paylaşılan örnekleri rubric ile incelemeli, hataları kategoriye ayırmalı ve prompt/eşik değişikliklerini eval setinde karşılaştırmalıdır.

Kaynaklar: [Systematic evaluation of an AI teaching assistant](https://doi.org/10.1145/3641554.3701945), [CS50 multi-turn evaluation paper](https://cs.harvard.edu/malan/publications/fp0627-liu.pdf).

## 4. Yeni geliştirme yolu

### Aşama A — Ürün kalite döngüsü (bu dalda uygulandı)

- Her asistan yanıtında “Yararlı / Sorun var”.
- Sorun gerekçeleri: hatalı, ilgisiz, kaynak sorunu, fazla doğrudan, güvensiz, diğer.
- Öğrencinin puanını değiştirebilmesi ve geçmişte geri görebilmesi.
- Öğretmen için toplu sayılar ve gerekçe dağılımı.
- Yalnız açık izinle paylaşılan soru-cevap-inceleme kuyruğu.
- İzin geri çekilince öğretmen görünümünden ve saklanan alıntıdan düşme.
- RLS ve API’nin ayrı ayrı yetki kapısı olması.

**Çıkış ölçütü:** başka öğrenci mesajını puanlayamıyor; öğrenci kalite ekranını açamıyor; eğitmen paylaşılmamış sohbet metnini göremiyor; paylaşılan kayıt açık ve anlaşılır biçimde görünüyor.

### Aşama B — Gerçek kimlik yaşam döngüsü (bu dalda uygulandı, dış doğrulama bekliyor)

- Supabase e-posta/parola girişi.
- “Parolamı unuttum” bağlantısı.
- Hesap varlığını açıklamayan genel başarı metni.
- Kurtarma bağlantısından yeni parola belirleme.
- En az 8 karakter ve eşleşme doğrulaması.

**Dış bağımlılık:** Supabase URL/anon key, izin verilen redirect URL, custom SMTP ve gerçek e-posta teslim testi.

### Aşama C — Gerçek sağlayıcı kabul kapısı (P0)

1. Staging Supabase projesini oluştur.
2. Migration `0001`–`0013` zincirini yalnız migration ile uygula.
3. Groq ve Gemini anahtarlarını secret manager’a koy; repoya veya `NEXT_PUBLIC_*` içine koyma.
4. İşletim Sistemleri örnek paketini yükle.
5. En az 100 soru içeren holdout çalıştır:
   - kaynak sadakati,
   - atıf doğruluğu,
   - kapsam dışı doğru ret,
   - Sokratik modda doğrudan cevap sızıntısı,
   - açık uçlu puanda insan-model uyumu,
   - p95 gecikme ve istek başı maliyet.
6. Başarısız örnekleri yeni AI kalite nedenleriyle etiketle.
7. Eşik/prompt/model değişikliğini aynı sabit veri setinde tekrar ölç.

**Release hedefleri:**

- Kaynaksız akademik cevap: 0.
- Yanlış/uydurma atıf: 0 kabul edilebilir; her olay blocker.
- Kapsam dışı doğru ret: en az %90.
- Sokratik doğrudan çözüm sızıntısı: 0 kritik vaka.
- Açık uçlu puanlama: insan rubric’iyle önceden belirlenmiş kabul aralığı.
- p95: ölçülmüş ve runbook’ta yazılı; ölçülmeden sayı söylenmez.

### Aşama D — Production altyapısı (P0)

Supabase’in production önerileri doğrultusunda:

- Local, staging ve production ayrı projeler.
- RLS’nin bütün dışa açık tablolarda zorunlu ve production üstünde ayrıca testli olması.
- SSL enforcement ve network restriction.
- Custom SMTP, e-posta doğrulama ve parola kurtarma teslim testi.
- Migration-only şema değişikliği; production Dashboard’dan elle tablo değiştirmeme.
- Staging’de load/soak testi ve indeks gözlemi.
- PITR veya günlük backup planı; en az bir restore tatbikatı.
- Storage nesnelerinin veritabanı backup’ına dahil olmadığını dikkate alan ayrı dosya kurtarma planı.
- API/web hata oranı, gecikme, ingestion kuyruğu ve LLM sağlayıcı hatası için uyarılar.
- Anahtar döndürme ve olay müdahale runbook’u.

Kaynaklar: [Supabase production checklist](https://supabase.com/docs/guides/deployment/going-into-prod), [Supabase maturity model](https://supabase.com/docs/guides/deployment/maturity-model), [Supabase backups](https://supabase.com/docs/guides/platform/backups), [Supabase platform security](https://supabase.com/docs/guides/security/platform-security).

### Aşama E — Jüriye hazır uçtan uca teslim (P0)

Tek bir senaryo baştan sona kaydedilmelidir:

1. Öğretmen gerçek hesapla giriş yapar.
2. Ders açar ve PDF/PPTX/kod yükler.
3. Chunk önizleme ve retrieval testinde doğru pasajı görür.
4. Öğrenme çıktılarıyla blueprint oluşturur.
5. AI’dan taslak soru üretir, düzenler ve onaylar.
6. Sınav sürümünü yayımlar.
7. Öğrenci gerçek hesapla giriş yapar.
8. CourseGPT’ye kaynaklı soru sorar ve atıftan özgün bağlama gider.
9. Sokratik modda kendi denemesini yazar.
10. Exam Mentor ile prova çözer ve “neden yanlış” geri bildirimi görür.
11. Süreli sınav sırasında yeni sekmede asistanın kapalı olduğu gösterilir.
12. Öğrenci sorunlu bir yanıtı öğretmen incelemesine açar.
13. Öğretmen Class Assistant ve AI kalite ekranında toplu sonucu görür.

Bu senaryo staging/canlı URL’de başarısızsa ürün “production hazır” değildir; yerel testlerin yeşil olması tek başına yeterli değildir.

### Aşama F — Benzer ürün kalitesine doğru sonraki sürüm (P1/P2)

| Öncelik | Güncelleme | Neden |
|---|---|---|
| P1 | Blueprint/soru havuzu PDF ve CSV dışa aktarma | Khanmigo’daki görünür öğretmen aracı yaklaşımını teslim edilebilir çıktıya dönüştürür. |
| P1 | Eylem bazlı model/provider/bütçe | Moodle’daki action-provider ayrımına yaklaşır; pahalı modeli yalnız gerektiği yerde kullanır. |
| P1 | AI kalite kaydına eğitmen durumu: açık/incelendi/düzeltildi | Geri bildirimi liste olmaktan çıkarıp gerçek review sürecine dönüştürür. |
| P1 | Eval seti sürümleme ve önce/sonra karşılaştırması | CS50 seviyesinde periyodik insan değerlendirmesini tekrarlanabilir yapar. |
| P2 | OCR ve tablo/görsel ağırlıklı slayt kalite ölçümü | RAGFlow ile multimodal belge paritesi. Ölçüm göstermeden motor eklenmemeli. |
| P2 | Kaynak sürüm değişikliğinin değerlendirmelere etkisi | NotebookLM benzeri bağlam otoritesini sürüm değişiminde de korur. |
| P2 | Öğrenci çalışma artefaktları: çalışma rehberi/flashcard | NotebookLM’in kaynak dönüşümlerine yaklaşır; önce çekirdek sınav ürünü production olmalı. |
| P2 | Moderasyon ve güvenlik olayı iş akışı | Khanmigo safety yaklaşımı. Yaş grubu, kurum politikası ve mahremiyet kararıyla tasarlanmalı. |

## 5. LLM’e özgü production güvenliği

Klasik web güvenliğine ek olarak aşağıdaki kapılar zorunludur:

- Kaynak belgelerdeki prompt injection talimatlarını veri olarak ele alma.
- Citation ID set-membership ve kaynak/metin bağının deterministik doğrulanması.
- Farklı ders vektörlerinin, önbelleğinin ve feedback’inin RLS ile ayrılması.
- Embedding modeli/sürümü/provenance damgası ve yeniden indeksleme planı.
- Zararlı veya uygunsuz yanıt geri bildiriminin ayrı “unsafe” nedeni.
- Loglara soru/cevap serbest metni yazmama; inceleme metnini yalnız açık izinle saklama.
- Riskleri tasarım, test, kullanım ve izleme boyunca yönetme; yalnız prompt’a güvenmeme.

Kaynaklar: [OWASP Vector and Embedding Weaknesses](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/), [NIST Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence).

## 6. Gerçek bitiş tanımı

Proje ancak aşağıdaki altı koşul birlikte karşılandığında “tam end-to-end production ürün” sayılmalıdır:

- [ ] Gerçek Supabase Auth + Storage + production DB.
- [ ] Gerçek LLM ile sabit eval setinde kabul hedefleri.
- [ ] Staging ve production URL’leri, health/readiness ve gözlemleme.
- [ ] Production RLS testi, yük testi, backup/restore tatbikatı.
- [ ] Öğretmen ve öğrenciyle baştan sona gerçek ders senaryosu.
- [ ] Güncel test raporu, kullanım kılavuzu ve 10–15 dakikalık video.

İlk dört madde dış sistem veya anahtar gerektirir; depoda tek başına doğrulanamaz. Geri kalan repo içi boşluklar bu dalda kalite döngüsü, parola kurtarma ve görünür AI rolleriyle azaltılmıştır.

