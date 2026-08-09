# Şerit 5 — Analitik + değerlendirme altyapısı

> **Önce `00_OKU_ONCE.md` dosyasını oku.** Bu belge yalnız senin şeridini anlatır.
> Branch: `feat/analytics-eval` · Görevler: T038, T041-T047
> Bağımlılık: **yok — hemen tam hız** · Migration: **`0005` senin** (gerekirse)

---

## Neden bu şerit projeyi savunulabilir kılıyor

Diğer dört şerit ürünü **yapıyor.** Sen ürünün iyi olduğunu **kanıtlıyorsun.**

Projenin tezi ölçülebilir iddialarla dolu: "Recall@5 ≥ %80", "atıf hassasiyeti
≥ %90", "Sokratik sızıntı 0", "kapsam dışı doğru ret ≥ %90". Bugün bu sayıların
hiçbiri ölçülmüş değil ve Anayasa III net: **koşturulmayan deney için sonuç
yazılmaz.** Ölçüm altyapısı olmadan bu iddiaların hepsi raporda boş kalır.

Ayrıca en acil iş sende: **gold set birikmeli.** Günde 5-8 soru, ve toplam ≥50
gerekiyor. Son güne bırakılırsa yetişmez.

## Sahiplendiğin dosyalar

```
evaluation/gold_set/calibration.json             YENİ
evaluation/gold_set/holdout.json                 YENİ
evaluation/evaluate.py                           YENİ
evaluation/calibration.md                        YENİ
evaluation/faithfulness/sample_template.md       YENİ
apps/api/app/api/analytics.py                    iskelet hazır, gövdeyi sen yaz
apps/api/tests/test_analytics.py                 YENİ
supabase/tests/rls_assessment.sql                YENİ  (aşağıda anlatılıyor)
supabase/migrations/0005_*.sql                   gerekirse — numara SENİN
docs/test-report.md                              YENİ (T056, en son)
specs/001-course-assistant-mvp/tasks.md          yalnız T038, T041-T047 satırları
```

## ÖNCE OKU — biten şeritlerden iki bulgu görevlerini değiştiriyor

Tam bağlam: [`07_SERIT_RAPORLARI.md`](07_SERIT_RAPORLARI.md). Özet:

**1. Kanıt kapısı bugün fiilen açık (T043'ü doğrudan etkiler).** Şerit 1'in
ölçümü: `evidence_threshold=0.35` ile konu dışı 10 sorgunun **10'u da geçiyor**
("makarna nasıl pişirilir" → 0.766). Sinyal sağlam, değer yanlış: en iyi kesim
**0.7963**'te doğruluk **0.96** (n=24, yön göstergesi). Kalibrasyonun başlangıç
noktası bu; sıfırdan aramana gerek yok.

Eşik `dense_score`'a uygulanır, `fused_score`'a DEĞİL — RRF skoru sıralamadan
üretilir ve üst sınırı ~0.033'tür, 0.35 ile karşılaştırılamaz. İki şerit bu
tuzağa ayrı ayrı düştü.

**2. SC-005 bu haliyle yanlış ölçer.** Şerit 3'ün bulgusu: müfredat dışı sorular
çoğunlukla kanıt eşiğine takılıyor, yani `out_of_scope` değil
`insufficient_context` etiketi alıyorlar. FR-011 sıralaması gereği bu davranış
**doğru**, ama SC-005 yalnız `out_of_scope`'u sayıyor — metrik iyi çalışan bir
sistemde bile düşük çıkar.

Karar senin: ya SC-005'i "doğru ret" olarak yeniden tanımla (iki durumu birden
say), ya kapsam sınıflandırmasını kanıt kapısından önce koştur. Gerekçesini yaz;
bu bir ölçüm tasarımı kararıdır ve raporda savunulacak.

**3. Injection vakaları hazır.** `evaluation/gold_set/injection_cases.json` —
Şerit 2'nin bonusu: 19 injection (yedi kalıp ailesi) + 12 sızıntı senaryosu,
3'ü yanlış pozitif kontrolü. Gold set senin dosyan, **birleştirme sende**.
Rapor dili uyarısı dosyanın içinde.

**4. `request_logs` yazma-yalnız.** SELECT politikası yok. Satır bazlı okuma
istersen `0005`'te açman gerekiyor (migration numarası zaten senin).

## Öncelik sırası — bu sıra önemli

### 1. Gold set (T041) — BUGÜN BAŞLA, her gün devam

`docs/team/05_DATA_EVAL_BRIEF.md` tam formatı ve kategorileri anlatıyor. Özet:

| Kategori | Etiket | Adet |
|---|---|---|
| Doğrudan | `direct` | 20 |
| Çok-chunk | `multi_chunk` | 10 |
| Teknik terim / kod | `technical_term` | 10 |
| Kapsam dışı | `out_of_scope` | 10 |
| Prompt injection | `injection` | ≥15 |
| Kod inceleme | `code_review` | ≥5 |
| Sokratik sızıntı | `socratic_leak` | senaryolar |

**Kalibrasyon seti önce** (~15 soru: 6 direct, 3 multi_chunk, 3 out_of_scope,
3 technical_term) → `calibration.json`. Sonra günlük birikimle `holdout.json`.

**İkisi asla karışmaz.** Eşikler kalibrasyonla ayarlanır, metrikler holdout'ta
raporlanır. Karışırsa rapor edilen her sayı geçersiz olur.

**Kritik kural (koordinasyon §8):** soruları asistan taslak üretebilir, ama
`expected_sources` eşlemesini **materyali açıp sen doğrulayacaksın.** Gold set
sistemin cetvelidir; cetvel yanlışsa ölçüm de yanlış.

Sayfa numaralarını gerçek PDF'lerden al (ingest edilen PDF, `.md` değil).
Materyal `sample_data/isletim-sistemleri/` altında, `main`'de hazır.

**Dikkat:** `04-synchronization` dosyasındaki `bug_hunt` cevap anahtarı 7 Ağustos'ta
düzeltildi. `code_review` sorusu yazarken **güncel metni** kullan: bu koddaki
hatanın tek doğrulanmış sonucu **deadlock**'tur, taşma/taşınma değil.

### 2. RLS kanıt boşluğu (`supabase/tests/rls_assessment.sql`) — en yüksek değerli tek iş

PR incelemesinde ölçüldü: `0004`'ün **15 RLS politikasının hiçbirinin otomatik
kanıtı yok.** `questions_read` politikasından `AND status = 'approved'`
düşürüldüğünde 92 test yeşil kalıyor, `rls_isolation.sql` 8/8 PASS veriyor ve
CI'daki `grep -q FAIL` kapısı geçiyor — aynı anda psql'de öğrenci taslak sınav
sorusunu görüyor.

Yani ölçme katmanının **tüm** politikaları `USING(true)` yapılsa bile CI yeşil.
Projenin tezi "iki katmanlı izolasyon, **kanıtlı**" iken bu, tezin en zayıf noktası.

`supabase/tests/rls_isolation.sql` desenini izleyerek yeni bir dosya yaz. En az:

- Öğrenci `draft` soruyu görmez, eğitmen görür
- Öğrenci başkasının `exam_sessions` satırını görmez
- `answers`'a sahte `course_id` ile satır yazılamaz
- Sınav oturumu yabancı bir derse taşınamaz
- Mastery, üye olunmayan derse yazılamaz

Sonra `.github/workflows/ci.yml`'ye ekle. **Not:** `ci.yml` liderin dosyası —
SQL'i yaz, gruba haber ver, ekleme işini lider yapar.

**Her testin kırmızı yanabildiğini de kanıtla:** politikayı bilerek boz, testin
FAIL verdiğini gör, geri al. Yanmayan test hiçbir şey kanıtlamaz.

### 3. Analitik ucu (T038 — `api/analytics.py`)

İki görünüm:

- **Öğrenci:** konu bazlı mastery listesi
- **Eğitmen:** konu bazlı sınıf ortalaması, en çok yanlış yapılan sorular, kapsam
  dışı ret oranı

Frontend **zaten hazır** ve tasarım önizlemesi olarak duruyor
(`apps/web/app/courses/[courseId]/analytics/page.tsx`). Sözleşmeyi ona bakarak
kur; hangi alanların beklendiği orada görünüyor. `apps/web`'e **dokunma**, lider
bağlayacak.

`mastery` tablosu ve EWMA servisi hazır ve testli. Sen okuyorsun, yazmıyorsun.

Seviye eşikleri (FR-027): `<0.40` Geliştirilmeli · `0.40-0.74` Orta · `≥0.75` İyi.
Bu eşikler frontend'de `lib/labels.ts`'de de var — **sayıları değiştirme**, iki
taraf ayrışır.

### 4. Değerlendirme harness'ı (T042 — `evaluate.py`)

**G9'a kadar iskeleti yaz. G12'ye bırakma** — brief bunu açıkça uyarıyor; ilk kez
o gün yazarsan gece koşusu yetişmez.

Metrikler: Recall@5 **ve** Recall@8, MRR, citation precision, ret F1.

Katmanlı koş: `--layer retrieval` (LLM'siz, ucuz, hızlı) önce çalışsın; `--layer e2e`
sonra. Retrieval katmanı Şerit 1 iner inmez koşturulabilir.

Rate-limit farkındalıklı kuyruk + sonuç cache'i şart: ücretsiz katmanda kota
sınırlı ve aynı soruyu iki kez sormak parayı ve zamanı boşa harcar.

### 5. Kalibrasyon ve karşılaştırma (T043-T044)

`evidence_threshold` **kalibrasyon setiyle** ayarlanır. Şu an `config.py`'de
`0.35` yazıyor ve yorumunda "KALİBRE EDİLMEMİŞTİR" notu var — o notu ancak sen
kaldırabilirsin. Seçilen değeri ve **gerekçesini** `evaluation/calibration.md`'ye
yaz.

T044: baseline (dense-only) vs hybrid, aynı holdout üzerinde, **eşleştirilmiş
anlamlılık** kaydıyla (bootstrap veya McNemar, en azından güven aralığı).

**Metodoloji notu zorunlu:** n≈50 yön göstericidir, kesin hüküm değildir. Bu
cümle raporda geçmezse sayılar olduğundan güçlü okunur.

### 6. Negatif testler (T046-T047)

T046: ≥15 injection vakası + Sokratik sızıntı senaryoları guardrail zincirinden
geçirilir. Şerit 2 ile koordine ol — o da injection vakaları hazırlıyor olabilir,
ikinizin listesi birleşmeli.

T047: 20-30 gerçek cevap, **iki kişi bağımsız etiketler**, uyum oranı raporlanır.
Tek etiketleyicili faithfulness ölçümü zayıftır.

## Bitti sayılma ölçütü

- [ ] `calibration.json` ~15 soru, `expected_sources` **elle doğrulanmış**
- [ ] `holdout.json` ≥50 soru, kategori dağılımı tabloya uygun, kalibrasyonla
      **kesişimi sıfır**
- [ ] `rls_assessment.sql` yazıldı ve her testin kırmızı yanabildiği kanıtlandı
- [ ] `analytics.py` uçları çalışıyor, testli
- [ ] `evaluate.py --layer retrieval` gerçek materyalde koştu ve sayı üretti
- [ ] `evidence_threshold` kalibre edildi, gerekçe `calibration.md`'de
- [ ] Raporlanan her sayının hangi sette ölçüldüğü yazılı
- [ ] `tasks.md`'de T038, T041-T047 `[x]` + tarihli DONE notu

## Uyarı — en sık yapılan hata

**Koşturmadığın deneyin sonucunu yazma.** Bir sayının yerine tahmin koymak,
bitirme projesinde yakalanması en kolay ve en pahalı hatadır. Ölçemediysen
`[ÖLÇÜLMEDİ]` yaz ve nedenini belirt; jüri bunu saygıyla karşılar, uydurma sayıyı
karşılamaz.

## Bittiğinde

`docs/test-report.md` (T056) senin nihai çıktın: ölçülen her sayı, hangi sette
ölçüldüğü, metodoloji notu ve sınırlar. Bu belge projenin savunmasıdır.
