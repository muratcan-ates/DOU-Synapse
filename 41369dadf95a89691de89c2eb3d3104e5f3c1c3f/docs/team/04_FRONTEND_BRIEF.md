# R4 — Frontend Brief (Muratcan)

> Bu belge sana ne yapacağını öğretmiyor; **kendi verdiğin kararları** tek yerde tutuyor.
> Üç hafta boyunca ekran ekran ilerlerken "burada neden böyle demiştik?" sorusunun cevabı
> burada. Çelişki çıkarsa sıra şudur: [Anayasa](../../.specify/memory/constitution.md) >
> [DESIGN.md](../../DESIGN.md) > [ARCHITECTURE.md](../../ARCHITECTURE.md) > bu belge.
>
> İş listesi: [`specs/001-course-assistant-mvp/tasks.md`](../../specs/001-course-assistant-mvp/tasks.md) ·
> Sahiplik: [`00_TAKIM_KOORDINASYON.md`](00_TAKIM_KOORDINASYON.md)

**Rol:** R4 — Frontend · **Görevler:** T021, T022, T023, T034, T035, T040 (+ R5'in T060'ındaki privacy sayfası alt işi ve R1'le ortak T054-T055 provaları)
**Sert kapılar:** G5 (Pzt 10 Ağu) dikey RAG demosu · G10 (Pzt 17 Ağu) özellik dondurma · Teslim 24 Ağu
**Risk kaydı:** PLAN §6'da "frontend darboğazı" ayrı bir satır. Erken işareti "H2 ortasında
ekranlar gecikmiş". Geri dönüşü ekran öncelik listesi; onu aşağıda 9. bölümde tutuyorsun.

---

## 1. Sahiplik: nereye dokunursun, nereye dokunmazsın

```
apps/web/                                          ← TAMAMI SENİN
supabase/migrations/0002_supabase_auth_bridge.sql  ← SENİN (T023 ile birlikte gelir)
DESIGN.md                                          ← Sen + Murat (yani sen)
```

Bunlar senin değil, gerekiyorsa sahibine söylersin:

- `apps/api/**` — tamamı backend rollerinin (R1/R2/R3)
- `supabase/migrations/0001_core_schema.sql` — **dondurulmuş**, değişmez
- `specs/.../contracts/openapi.json` — uç ekleyen rol günceller, sen okursun

**Sıcak dosya kuralı:** `apps/web/lib/types.ts` senin. Backend bir tipi değiştirdiğinde
**sen düzenlersin**, R1 değil. Bu yüzden R1'in "şema hazır" (T010) mesajını beklemek zorundasın;
şemayı tahminle yazıp sonra iki kere düzeltmek üç saat yakıyor.

---

## 2. Görevlerin tek bakışta

| ID | Dosya | Ne | Kimi bekler | Kapı |
|---|---|---|---|---|
| T021 | `apps/web/lib/types.ts`, `apps/web/lib/api.ts` | Chat sözleşme tipleri + istemci fonksiyonları | **R1 / T010** (cevap şeması) | G5 |
| T022 | `apps/web/app/courses/[courseId]/chat/page.tsx` | Sohbet ekranı mock'tan gerçek veriye | **R1 / T019** (chat ucu) | G5 |
| T023 | `supabase/migrations/0002_supabase_auth_bridge.sql`, `apps/web/lib/supabase.ts`, `apps/web/app/page.tsx`, `apps/web/lib/api.ts` | Supabase Auth geçişi | — (bağımsız başlar) | G8 |
| T034 | `apps/web/app/courses/[courseId]/exam/page.tsx` + `lib/{types,api}.ts` | Sınav ekranı gerçek state'e | **R3 / T032** (exams ucu) | G9-G10 |
| T035 | `apps/web/components/socratic-ladder.tsx`, YENİ `app/courses/[courseId]/questions/page.tsx` | Merdiven gerçek state'e + soru onay paneli | **R1 / T027**, **R3 / T030** | G9-G10 |
| T040 | YENİ `app/courses/[courseId]/analytics/page.tsx` + `components/course-nav.tsx` | Analitik / mastery ekranı | **R3 / T038** | G10 |
| (T060 alt işi) | YENİ `app/privacy/page.tsx` | KVKK aydınlatma sayfası — statik; metni R5 yazar, sayfayı sen koyarsın. Görevin sahibi R5'tir, sen yalnız web ayağını teslim edersin | **R5 / T060** | G14-G15 |

T023 hiçbir backend işine bağlı değil. Beklerken onu yazarsın; boş oturma sebebi yok.

---

## 3. Verdiğin tasarım kararları — hatırlatma listesi

Bunlar tartışmaya açık değil, çünkü zaten sen kapattın. Ekran yazarken sırayla geç.

**1. Token dışında ham hex yok.** Bileşen içinde `#` görürsen o satır yanlış. Token yoksa
önce `DESIGN.md`'ye eklenir, sonra `globals.css`'e, sonra kullanılır. (Anayasa VII)

**2. Kırmızı üç yerde:** birincil eylem butonu, aktif navigasyon göstergesi, kurumsal başlık.
**Kırmızı asla hata rengi değil.** Hata `--danger` token'ıdır (ham hex yazma; globals.css'te açık tema `#9f2f2d`, koyu `#f08c8a` — DESIGN.md'deki `#B91C1C` ile ayrışma §10.2'de kayıtlı). Koyu temada marka `#FF6B78`'e
döner — çünkü ham `#C50C1F`, `#1C1917` üstünde **2.87:1** veriyor, okunmuyor. Bu ölçülmüş bir
sayı, tahmin değil; raporda da böyle geçecek.

**3. Abstention hata gibi gösterilmez.** En kritik karar bu. "Materyalde bu sorunun cevabı yok"
bir **başarıdır**: sistem uydurmak yerine reddediyor. Kırmızı yok, ünlem yok, uyarı üçgeni yok.
Nötr yüzey (`--surface`), sakin ton, `--fg-muted`, ve **her zaman bir sonraki adım** ("soruyu
farklı ifade et" / "eğitmene sor"). Öğrenci bunu arıza sanırsa genel bir yapay zekâya kaçar ve
ürünün varlık sebebi çöker. `insufficient_context` ve `out_of_scope` **200 döner**, catch
bloğuna düşmez — T020 bunu testle sabitliyor.

**4. Kaynak kartı imza bileşendir.** Dipnot değil, cevapla eşit ağırlıkta. Dosya adı + sayfa
(`Sayfa 12` / `Slayt 7` / bölüm adı) **her zaman görünür**. Alıntı chunk'tan birebir gelir;
model yeniden yazmaz, sen kısaltmazsın. Mobilde gizlenmez, cevabın altında açılır kapanır
bölüme iner. Kaynağı gizlemek ürünün ana vaadini gizlemektir.

**5. Sınav ekranı:** ilerleme `3/10` biçiminde **sayısal**, ilerleme çubuğu yok. Sayaç sağ üstte,
`text-sm`, nötr; son 60 saniyede `--warning`. **Yanıp sönme yok, animasyon yok** — sınav ekranı
hareketsizdir, hareket kaygı üretir. Şıklar arasında bol boşluk (yanlış tıklama sınav kaygısını
artırır). `.rise` sınıfı bu ekranda kullanılmaz.

**6. Sokratik merdiven:** ayrık kademe noktaları, ilerleme çubuğu değil ("4 adımda biter" hissi
düşünmeyi hızlandırma baskısı yaratır). İpuçları **birikir**, silinmez. **"Cevabı ver" butonu
yoktur.** Kademe atlanmaz — ve atlanmadığını UI değil backend garanti eder; sen sadece
göstermezsin.

**7. `uppercase` yasak** (Türkçe `i → İ` dönüşümü tarayıcıya göre bozulur). **Em dash UI
metninde yok.** Metin gradyanı, dekoratif animasyon, parallax yok.

**8. Backend hata zarfı `{error:{code,message}}` olduğu gibi gösterilir.** Kendi Türkçe metnini
uydurmazsın; backend `app/core/errors.py`'de zaten anlaşılır Türkçe üretiyor. Tek istisna ağ
kopması gibi backend'in hiç cevap veremediği durum ("Bağlantı kurulamadı."). Ham stack trace
kullanıcıya asla gitmez. (Anayasa V + X)

**9. Renk tek başına bilgi taşımaz.** Her durum renk + metin (+ikon) üçlüsüyle işaretlenir.
Mastery seviyeleri, sınav sonuçları, doküman durumları — hepsi.

**10. Her ekran 375px'te ve koyu temada kontrol edilir.** İkisi de "sonra bakarım" değil, o
görevin kabul kriteri. Dokunma hedefi en az 44×44px. Öğrenci ekranları mobil öncelikli (gece
telefonla çalışma senaryosu), eğitmen paneli masaüstü öncelikli.

---

## 4. Görev görev: karar notları

### T021 — chat tipleri ve istemci (`lib/types.ts`, `lib/api.ts`)

Kaynak sözleşme ARCHITECTURE §5'teki cevap şeması:

```
status: "answered" | "insufficient_context" | "out_of_scope"
mode:   "qa" | "socratic" | "exam"
answer: string
citations: [{ chunk_id, claim }]
hints:    [{ text, chunk_id }]
```

Karar notları:

- **`chunk_id → {file_name, page_number|slide_number, snippet}` eşlemesini backend yapar** (T013).
  Sen o zenginleştirilmiş nesneyi alıp gösterirsin; frontend'de chunk metadata'sı kurgulanmaz.
- Backend alanları (`file_name`, `page_number`) ile `SourceCard`'ın arayüzü (`fileName`,
  `location`, `quote`) aynı değil. **Dönüştürücü tek yerde yaşar** (`lib/types.ts` içinde küçük
  bir `toSourceInfo()`), sayfa bileşeninin içine satır arası serpiştirilmez. `location` metnini
  üreten kural tek noktada olsun: `page_number` varsa `Sayfa N`, `slide_number` varsa `Slayt N`,
  ikisi de yoksa `section_title`.
- FR-035 iki yeni hata yolu getiriyor: **429** (istek sınırı) ve **422** (soru çok uzun).
  `ApiError` bunları zaten taşıyor; sohbet girdisinde karakter sınırını **girmeden önce** de
  göster, 422'yi kullanıcıya tek yol olarak bırakma.
- `api.ts`'e `post` var, chat için ek bir soyutlama gerekmiyor. SSE/streaming **P1**, bayrak
  arkasında, dondurmadan sonra. Şimdi yazma.

### T022 — sohbet ekranı gerçek veriye

- Sayfanın başındaki "Tasarım önizlemesi" şeridi bu görevde **silinir**. Kalırsa demo günü
  jüriye "bu ekran sahte" diye bağırır.
- `status` üç dala ayrılır: `answered` → cevap + kaynak kartları · `insufficient_context` →
  `AbstentionNotice` · `out_of_scope` → aynı nötr kalıp, farklı metin (backend'in mesajı).
  **Üçü de normal akış**, hiçbiri `catch` değil.
- Geçerli atıf kalmazsa backend zaten cevabı göndermez (fail-closed). Frontend'in görevi
  "citations boşsa cevabı yine de basmamak" değil — o durum sana `insufficient_context` olarak
  gelir. Yine de savunmacı ol: `answered` + boş `citations` gelirse cevabı gösterme, abstention
  kalıbına düş. Anayasa I'in son savunma hattı sende de dursun.
- Mesaj geçmişi `GET .../chat/sessions` ve mesaj listesi uçlarından gelir. Sayfa yenilenince
  konuşma kaybolmaz.
- Yükleniyor durumu: sahte "yazıyor…" animasyonu yok; sade bir satır yeter. p95 hedefi 10 sn,
  yani bekleme gerçek — kullanıcıyı oyalama, durumu söyle.
- Sağdaki kaynak paneli (`lg` ve üstü 360px sabit sütun) ders materyallerini listeler; mobilde
  cevabın altına iner.

### T023 — Supabase Auth geçişi

Bu görevin **en büyük parçası auth değil, rol modeli.**

- `profiles` tablosunda **sistem geneli `role` alanı yok** (data-model §2.1). Rol ders bazlıdır:
  `course_memberships.role`, API'de `Course.role`. Bugün `components/course-nav.tsx` ve ders
  detay sayfası `getStoredUser()?.role` okuyor — bu **yalnız demo girişinin uydurması**.
  Supabase Auth'a geçerken bu okumaların hepsi **ders kapsamlı role** döner. Grep listesi:
  `components/course-nav.tsx:23`, `app/courses/[courseId]/page.tsx:43`, `app/courses/page.tsx:42`, `components/app-shell.tsx:41`, `app/page.tsx:97`. (members/page.tsx'te `me` yalnız 'siz' etiketi içindir, rol kontrolü yoktur.)
- `dev:<uuid>` token'ı **silinmez**, `DEV_AUTH_ENABLED` arkasında lokal/Compose yolu olarak kalır.
  Demo C planı (tam offline) buna bağlı; sildiğin an runbook'un bir bacağı gider.
- `lib/api.ts` bugün `localStorage`'dan tek seferlik token okuyor. Supabase oturumu **yenilenir**;
  istemci her istekte **canlı oturumdan** access token alsın, giriş anında kopyalanmış bir
  snapshot'tan değil. Sınav ortasında 401 almak istemiyorsun.
- `0002_supabase_auth_bridge.sql`: `auth.users → profiles` senkron trigger'ı. **Migration ve RLS
  yapay zekâya bırakılmaz** (koordinasyon §8) — yazdır, satır satır oku, lokalde koştur.
  `0001` dondurulmuş; şema değişikliği yeni migration'la gelir.
- Ortam değişkenleri: yalnız `NEXT_PUBLIC_SUPABASE_URL` + **anon key**. Service-role anahtarı
  frontend'e, `.env.example` dışında hiçbir yere, commit'e ve AI sohbetine girmez.
- Yeni bağımlılık yalnız `@supabase/supabase-js`. Teknoloji kilidi (Anayasa) başka paket için
  plan revizyonu istiyor.

### T034 — sınav ekranı gerçek state'e

- **Süre sunucunun gerçeğidir.** İstemci yalnız geri sayımı çizer; "süre bitti" kararını backend
  verir. Bağlantı koptuğunda öğrenci **kalan süreyle** devam eder (T033/7) — yani oturuma
  dönüşte kalan saniyeyi sunucudan alırsın, `Date.now()` farkıyla kendin hesaplamazsın.
- **Cevaplanmamış soru boş sayılır, yanlış sayılmaz.** Bu kural sınav **başlamadan önce**
  ekranda yazar (spec Edge Cases + T033/4). Sonuç ekranında öğrenci bunu ilk kez öğrenmesin.
- `exam` modunda ipucu arayüzü **hiç bulunmaz** — devre dışı buton değil, yok. Politikayı backend
  zorluyor; UI'ın işi teklif etmemek. `practice` modunda ipucu açık, anında geri bildirim var,
  tekrar deneme serbest.
- Sonuç ekranı: toplam puan + soru bazlı doğru/yanlış + **"neden yanlış?"**. MCQ'da seçilen
  çeldiricinin çeliştiği kaynak bölümü (dosya + sayfa) `SourceCard` ile gösterilir. Açık uçluda
  puan + `eksik_noktalar[]` + dayanak sayfası.
- Onaylı soru havuzu boşsa sınav başlatılamaz: bu bir **hata ekranı değil**, açıklayıcı boş durum
  ("Eğitmen henüz soru onaylamadı."). Abstention ile aynı ton.
- Değerlendirme şemaya uymazsa backend uydurma puan üretmez (FR-020); sana "değerlendirme
  tamamlanamadı" mesajı gelir, sen onu olduğu gibi gösterirsin. Boş puan basma.

### T035 — merdiven gerçek state'e + soru onay paneli

- **Kademe backend'den gelir.** `chat_sessions.state` tek gerçeklik kaynağı; istemci ipucu
  saymaz. Sayfa yenilense de kademe korunur (T028/5).
- **Dikkat, sabitlenmesi gereken eşleme:** backend state machine beş durumlu
  (`DIAGNOSE → NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE`), bileşendeki
  `STEPS` dizisi dört etiketli (`DIAGNOSE` bir ipucu kademesi değil, tanı turu). Mastery
  çarpanları da beş kademeli (0→1.00 … 4→0.25). R2 ile bunu **bir kez** konuş: hangi state
  hangi noktayı yakıyor, `DIAGNOSE` gösteriliyor mu. Sonra `socratic-ladder.tsx`'in başına yaz;
  bir daha tartışılmasın.
- Israrcı öğrenci şablon ipucuna düştüğünde ekran bunu bir arıza gibi göstermez; ipucu ipucudur.
- `questions/page.tsx` — eğitmen soru onay paneli: **düz tablo**. PLAN §4 bunu "basitleştirilebilir"
  listesine koydu, yani süslemeye bütçe yok. Sütunlar: tip, soru metni (kırpılmış), kaynak
  (dosya + sayfa), durum rozeti, onayla/reddet. Detay açıldığında cevap anahtarı ve dayandığı
  chunk görünür — eğitmen körlemesine onaylamamalı (FR-023).
- Aynı panelde **minimal konu ekleme formu** (T030 `POST /courses/{id}/topics`). Konu olmadan
  soru üretimi de mastery de çalışmıyor; bu formu atlarsan T040 boş ekran verir.
- Sekmeyi `course-nav.tsx`'e `instructorOnly` olarak ekle. **Ama sekmeyi gizlemek güvenlik
  değildir** — yetki sunucuda; UI gizleme yalnız ergonomi.

### T040 — analitik ve mastery ekranı

- İki görünüm tek dosyada: öğrenci → kendi konu listesi; eğitmen → tek kart sayfası (konu bazlı
  sınıf ortalaması, en çok yanlış yapılan sorular, kapsam dışı ret istatistiği).
- Seviye eşikleri: `<0.40 Geliştirilmeli` · `0.40-0.74 Orta` · `≥0.75 İyi`. Sınır değerler tam
  eşitlikte hangi tarafa düşüyor, R3'ün T039 testiyle **aynı** olsun; iki yerde iki farklı
  yuvarlama utanç verici bir demo hatasıdır.
- Ekranda **"Bu puan resmî not değildir, çalışma önerisi göstergesidir"** ibaresi bulunur
  (FR-028, ARCHITECTURE §5, KVKK notu). Küçük punto bir dipnot değil, listenin başında.
- **Grafik çizeceksen önce token.** DESIGN.md "Known Gaps" altında kategorik analitik paleti
  **tanımlı değil**. En hızlı ve en dürüst yol: grafik yok, sayı + etiket + seviye rozeti listesi.
  Grafik istiyorsan önce DESIGN.md'ye paleti kontrast ölçümüyle ekle.
- Nav bağlantısı `course-nav.tsx`'e eklenir (öğrenci ve eğitmen için farklı etiket olabilir:
  "Gelişimim" / "Sınıf özeti").

---

## 5. KURALLAR

1. **Token disiplini.** Ham hex yok, keyfi boşluk yok. Boşluk ölçeği 4px tabanlı:
   `1(4) 2(8) 3(12) 4(16) 6(24) 8(32) 12(48) 16(64)`. Ara değer icat edilmez.
2. **Kırmızı üç yerde ve asla hata değil.** Koyu temada `#FF6B78`.
3. **Abstention nötr.** `--danger` görürsen yanlış daldasın.
4. **Kaynak her zaman görünür.** Dosya adı + sayfa, alıntı birebir.
5. **Backend metnini olduğu gibi göster.** Kendi hata cümleni yazma.
6. **`uppercase` yok, em dash UI metninde yok.**
7. **Sınav ekranında animasyon yok.** `.rise` sınıfı oraya girmez.
8. **Her ekran 375px + koyu tema.** Görev bitmeden ikisi de bakılmış olur.
9. **Bitti = tarayıcıda görüldü** (Anayasa VIII). Gerçek API'ye karşı, gerçek veriyle.
   Ekran görüntüsü almadan görevi kapatma; T056 test raporunun görselleri de oradan gelecek.
10. **Görev = commit = PR.** Branch `feat/T022-chat-real-data` biçiminde, commit mesajı
    İngilizce conventional commit, gövdede "ne" değil "neden". **`Co-Authored-By` asla.**
11. **`lib/types.ts` senin.** Backend tipi değişince R1'den haber bekle, sen düzenle.
12. **Kapsam değişikliği tek başına yapılmaz.** "Şunu da ekleyeyim" dediğin an PLAN'da bilerek
    kesilmiş bir şeyi geri getiriyor olabilirsin.

---

## 6. YAPMA listesi

- `apps/api/**` altında hiçbir şey — tip yanlışsa R1'e söyle, kendin düzeltme
- `supabase/migrations/0001_core_schema.sql`'e dokunma (dondurulmuş)
- DESIGN.md'ye eklemeden bileşen içinde yeni renk/ölçü kullanma
- **shadcn/ui'a toplu geçiş yapma.** ARCHITECTURE'da adı geçiyor ama repoda elle yazılmış
  `components/ui.tsx` var ve DESIGN.md token'larına birebir oturuyor. G10'dan önce yığın
  değiştirmek dondurma tarihini yakar; gerçekten gerekirse tek bileşen bazında al.
- Streaming (SSE), reranker arayüzü, soru kümeleme — hepsi **P1**, dondurmadan sonra, bayrak
  arkasında. Şimdi yazma.
- `@supabase/supabase-js` dışında yeni bağımlılık ekleme (teknoloji kilidi)
- Sınav sayacını yanıp söndürme, kaynak kartını mobilde gizleme, abstention'ı uyarı gibi gösterme
- Placeholder metnini etiket yerine kullanma (odaklanınca kaybolur)
- Yetkiyi UI'da çözdüğünü sanma: sekme gizlemek yetkilendirme değildir
- Gerçek `.env` içeriğini, Supabase service-role anahtarını, gerçek öğrenci verisini AI'ya verme
- Demo verisi bırakma: gerçek veriye geçen her ekrandan "Tasarım önizlemesi" şeridi silinir

---

## 7. PR öncesi çıktı kontrol listesi

Her görev için, istisnasız:

- [ ] `cd apps/web && bun run build` temiz (tsc dahil)
- [ ] Ekran **375px** genişlikte kontrol edildi (yatay kaydırma yok, dokunma hedefi ≥44px)
- [ ] Ekran **koyu temada** kontrol edildi (marka rengi `#FF6B78`, kontrast okunur)
- [ ] Bileşenlerde ham renk yok:
      `grep -rn -E "#[0-9a-fA-F]{6}|rgba\(" apps/web/app apps/web/components --exclude=globals.css`
      yalnız `globals.css` dışında **boş** dönmeli (bugün dönmüyor, bkz. §10.4)
- [ ] `uppercase` yok, UI metninde em dash yok
- [ ] Hata yolu denendi: backend'i kapat, mesaj anlaşılır Türkçe mi, stack trace sızıyor mu
- [ ] Boş durum denendi (materyal yok / soru yok / mastery yok)
- [ ] Klavye ile gezilebiliyor, odak halkası görünür
- [ ] Ekran görüntüsü alındı (kılavuzlar T058-T059 ve rapor T056 bunları kullanacak)
- [ ] Commit mesajı İngilizce, `Co-Authored-By` yok, `tasks.md`'ye tarihli DONE notu düşüldü

Göreve özel:

- **T022:** abstention `catch` bloğuna düşmüyor · citations boşken cevap basılmıyor ·
  önizleme şeridi silindi · sayfa yenilenince geçmiş duruyor
- **T023:** `dev:` yolu `DEV_AUTH_ENABLED` ile hâlâ çalışıyor · oturum yenilenince token tazeleniyor ·
  rol artık ders kapsamlı · service-role anahtarı hiçbir yerde yok · `0002` lokalde koştu
- **T034:** kalan süre sunucudan geliyor · sayfa yenilenince süre korunuyor · exam modunda ipucu
  arayüzü yok · "boş sayılır" ibaresi sınav öncesi görünüyor · boş havuz nazik boş durum veriyor
- **T035:** kademe backend state'inden · ipuçları birikiyor · "cevabı ver" butonu yok ·
  onay panelinde cevap anahtarı ve kaynak görünüyor · konu ekleme formu çalışıyor
- **T040:** "resmî not değil" ibaresi var · seviye eşikleri T039 ile aynı · renk tek başına bilgi
  taşımıyor · nav bağlantısı eklendi

---

## 8. Bekleyeceklerin ve haber vereceklerin

**Bekleyeceklerin:**

| Kimden | Ne | Sensiz olmaz |
|---|---|---|
| R1 | **T010** cevap şeması | T021 |
| R1 | **T019** chat ucu + `openapi.json` güncellemesi | T022 |
| R1/R2 | **T027** Sokratik state alanları | T035 |
| R3 | **T030** questions + topics uçları | T035 |
| R3 | **T032** exams uçları | T034 |
| R3 | **T038** analytics ucu | T040 |

**Haber vereceklerin:** T023 bitince gruba yaz — dev-token'dan Supabase Auth'a geçiş herkesin
lokal akışını etkiler, sessizce merge edilirse takım sabah bozuk giriş ekranıyla uyanır.

**30 dakika kuralı:** bir şeye 30 dakikadan fazla takılırsan gruba yaz. Bu kuralı sen koydun,
kendine de uygula.

---

## 9. Feda sırası (panik anında karar verme, şimdi verdin)

PLAN §4'teki liste:

- **Feda edilemez demo yolu:** giriş → ders → yükleme + durum → **kaynaklı sohbet** → Sokratik → sınav
- **Basitleştirilebilir:** soru onay paneli (düz tablo yeter), analitik (tek kart sayfası),
  mastery görünümü (düz liste)

Yani zaman daralırsa sırasıyla: T040 sadeleşir → T035'in onay paneli çıplaklaşır → T034'ün sonuç
ekranı kısalır. **T021/T022 asla feda edilmez** — G5 kapısı onlar.

---

## 10. DESIGN.md'de kapatman gereken açıklar

DESIGN.md "arayüzün tek otoritesi" diyor; şu an kodla üç yerde ayrışıyor. Otorite iddiasının
doğru olması için birini seçip diğerini güncelle (ikisi de senin dosyan):

1. **Tipografi:** DESIGN.md "Inter" diyor, `app/layout.tsx` Geist yüklüyor (gerekçesi kod
   yorumunda: taste-skill'in Inter yasağı + latin-ext Türkçe glifleri + `next/font` ile
   çevrimdışı demo bağımsızlığı). Karar koddaki; DESIGN.md'yi güncelle.
2. **Renk değerleri:** DESIGN.md tablosu (`--bg: #FFFFFF`, `--surface: #FAFAF9`,
   `--brand-subtle: #FEF2F3`, `--success: #15803D` …) ile `globals.css` (sıcak monokrom kanvas:
   `#fbfbfa` / `#ffffff` / `#fdebec` / `#346538` …) aynı değil. Kodda bilinçli bir kayma var;
   DESIGN.md'ye taşı ve **kontrast oranlarını yeniden ölç** — Anayasa III gereği bu sayılar
   tahmin edilemez, rapora giriyor.
3. **Known Gaps:** ikon seti (Lucide "muhtemelen", doğrulanmadı), analitik kategorik palet,
   hareket süreleri. T040'a başlamadan en az ikincisini kapat.
4. **Mevcut ham renk borcu — 4 satır.** "Bileşende ham hex yok" kuralı bugün dört yerde ihlal:

   ```
   apps/web/components/ui.tsx:18   dark:text-[#191715]
   apps/web/components/ui.tsx:50   shadow-[0_1px_2px_rgba(28,25,23,0.03)]
   apps/web/app/page.tsx:87        hover:shadow-[0_2px_8px_rgba(28,25,23,0.04)]
   apps/web/app/courses/page.tsx:67 hover:shadow-[0_2px_8px_rgba(28,25,23,0.04)]
   ```

   DESIGN.md'de zaten bir gölge tablosu var (seviye 0-3) ama token'lanmamış. `--shadow-1/2/3`
   ve marka butonunun koyu tema metin rengi için bir token ekle, bu dört satırı token'a çevir.
   Küçük bir temizlik commit'i; T022'ye başlamadan halledilirse kontrol listesi bir daha
   yalan söylemez.

Bunlar toplamda yarım saatlik iş ama teslimde "tasarım sisteminiz belgeyle uyuşmuyor"
sorusunu tek cümleyle kapatıyor.

---

## 11. Takıldığında

- Next.js 16 **eğitim verisinden farklı olabilir**: API'yi tahmin etme, `apps/web/AGENTS.md`'nin
  dediğini yap ve `node_modules/next/dist/docs/` altındaki ilgili rehberi oku.
- Backend cevabı beklediğin gibi gelmiyorsa önce `specs/001-course-assistant-mvp/contracts/openapi.json`
  ile karşılaştır. Sözleşme ile kod ayrışmışsa bu bir backend hatasıdır, sen etrafından dolanma.
- Yerel kurulum gerçekleri (Postgres 16 keg-only PATH, pgvector kaynaktan derleme, migration
  sırası, `bun install && bun run dev`) `specs/001-course-assistant-mvp/quickstart.md`'de.
- AI asistanıyla çalışırken küçük, kabul kriterli görev ver. RLS, migration, yetkilendirme ve
  anahtar işleri insan gözünden geçer (koordinasyon §8).

---

## Son söz

Bu projede frontend, guardrail zincirinin **görünen yüzü**. Backend "kaynak yoksa cevap yok"
diyor; jüri bunu ancak senin ekranında görüyor. Kaynak kartı okunmuyorsa iddia yok. Abstention
kırmızıysa iddia tersine dönüyor: "sistem bozuk" diye okunuyor.

**Üç şey demoyu taşıyor:** kaynak kartındaki sayfa numarası, abstention'ın sakinliği, Sokratik
modda görünmeyen "cevabı ver" butonu. Gerisi cila.

**Hız değil tutarlılık. Ekran değil sözleşme. Mock değil gerçek veri.**
